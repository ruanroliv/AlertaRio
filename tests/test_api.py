import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Import against a temporary database: running tests must not modify the user's instance.
_boot = tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH'] = str(Path(_boot.name) / 'boot.db')
os.environ['LAKE_PATH'] = str(Path(_boot.name) / 'lake')
os.environ['APP_ENV'] = 'development'
os.environ['DEMO_DATA'] = 'false'
os.environ['APP_ORIGIN'] = 'http://localhost:8080'
from fastapi.testclient import TestClient
from backend import db
from backend.main import app, Reading, store_reading
from backend.security import hash_password, verify_password, digest


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'Teste#seguro-2026'
        cls.hashed = hash_password(cls.password)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        os.environ['DATABASE_PATH'] = str(Path(self.directory.name) / 'test.db')
        os.environ['LAKE_PATH'] = str(Path(self.directory.name) / 'lake')
        os.environ['ENABLE_REAL_MESSAGES'] = 'false'
        db.init_db()
        with db.connect() as conn:
            for email, role in [('gestor@example.com', 'manager'), ('morador@example.com', 'resident')]:
                conn.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)', (email, self.hashed, role))
            conn.execute('UPDATE devices SET key_hash=? WHERE id=?', (digest('device-test-key'), 'AR-001'))
        self.client = TestClient(app, base_url='http://localhost:8080')
        self.addCleanup(self.client.close)

    def test_demo_data_once_and_all_points(self):
        from backend.demo_data import seed_demo
        self.assertEqual(seed_demo(),245)
        self.assertEqual(seed_demo(),0)
        headers=self.login()
        result=self.client.get('/api/analytics').json()
        self.assertEqual(result['readings_count'],245)
        self.assertEqual(result['points_with_data'],5)
        self.assertEqual(result['simulated_count'],245)
        state=self.client.get('/api/state').json()
        self.assertTrue(all(s['has_reading'] for s in state['sensors']))
        self.assertEqual(len(state['occurrences']),5)
        self.assertTrue(state['alerts'])
        self.assertEqual(self.client.get('/api/analytics?origin=device').json()['readings_count'],0)

    def test_demo_history_preserves_existing_latest_reading(self):
        from backend.demo_data import seed_demo
        self.login()
        current=store_reading(Reading(**self.reading(water=177)), 'device')
        seed_demo()
        state=self.client.get('/api/state').json()
        point=next(s for s in state['sensors'] if s['id']=='AR-001')
        self.assertEqual(point['water'],177)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],2)


    def login(self, role='manager'):
        response = self.client.post('/api/auth/login', json={
            'email': 'gestor@example.com' if role == 'manager' else 'morador@example.com',
            'password': self.password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'X-CSRF-Token': response.json()['csrf_token']}

    def reading(self, water=170, **extra):
        return {'sensor_id': 'AR-001', 'water_level_cm': water, 'soil_moisture_pct': 70,
                'rainfall_mm': 20, 'measured_at': datetime.now(timezone.utc).isoformat(),
                'simulated': True, **extra}

    def test_password_hash_salted_and_verified(self):
        self.assertNotEqual(hash_password(self.password), self.hashed)
        self.assertTrue(verify_password(self.password, self.hashed))
        self.assertFalse(verify_password('incorrect', self.hashed))
        self.assertNotIn(self.password, self.hashed)

    def test_login_cookie_logout_and_revocation(self):
        headers = self.login()
        cookie = self.client.cookies.get('alertario_session')
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.json()['profile'], 'manager')
        self.assertNotIn('password_hash', response.text)
        with db.connect() as conn:
            self.assertNotEqual(conn.execute('SELECT token_hash FROM sessions').fetchone()[0], cookie)
        response = self.client.post('/api/auth/logout', json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.client.cookies.set('alertario_session', cookie)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_cookie_flags_and_headers(self):
        r = self.client.post('/api/auth/login', json={'email': 'gestor@example.com', 'password': self.password})
        self.assertIn('HttpOnly', r.headers['set-cookie'])
        self.assertIn('SameSite=strict', r.headers['set-cookie'])
        self.assertIn("frame-ancestors 'none'", r.headers['content-security-policy'])
        self.assertEqual(r.headers['cache-control'], 'no-store')

    def test_bad_login_generic_and_rate_limited(self):
        for _ in range(8):
            r = self.client.post('/api/auth/login', json={'email': 'unknown@example.com', 'password': 'incorrect'})
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json()['detail'], 'E-mail ou senha inválidos')
        r = self.client.post('/api/auth/login', json={'email': 'unknown@example.com', 'password': 'incorrect'})
        self.assertEqual(r.status_code, 429)

    def test_no_role_escalation_from_login(self):
        r = self.client.post('/api/auth/login', json={'email': 'morador@example.com', 'password': self.password, 'role': 'manager'})
        self.assertEqual(r.status_code, 422)
        headers = self.login('resident')
        self.assertEqual(self.client.get('/gestao.html').status_code, 403)
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading(), headers=headers).status_code, 403)

    def test_csrf_and_cross_origin_rejected(self):
        headers = self.login()
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading()).status_code, 403)
        headers['Origin'] = 'https://attacker.example'
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading(), headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/login', data={'email': 'x'}).status_code, 415)

    def test_expired_session_rejected(self):
        self.login()
        with db.connect() as conn:
            conn.execute('UPDATE sessions SET expires_at=0')
        self.assertEqual(self.client.get('/api/state').status_code, 401)

    def test_anonymous_data_protected(self):
        for endpoint in ['/api/state', '/api/analytics', '/api/readings.csv', '/api/ai/AR-001']:
            self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.assertEqual(self.client.get('/mapa.html', follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get('/config.js').status_code, 200)
        self.assertIn("'backend'", self.client.get('/config.js').text)

    def test_no_telemetry_is_not_reported_as_normal(self):
        self.login()
        state = self.client.get('/api/state').json()
        self.assertFalse(state['sensors'][0]['has_reading'])
        self.assertEqual(state['sensors'][0]['risk']['label'], 'Sem dados')
        self.assertEqual(self.client.get('/api/ai/AR-001').status_code, 404)

    def test_ingestion_persistence_alert_and_lake(self):
        r = self.client.post('/api/iot/readings', json=self.reading(), headers={'X-Device-Key': 'device-test-key'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['risk']['label'], 'Alto')
        self.login()
        state = self.client.get('/api/state').json()
        self.assertEqual(state['sensors'][0]['water'], 170)
        self.assertTrue(state['alerts'])
        files = list(Path(os.environ['LAKE_PATH']).glob('*.jsonl'))
        self.assertEqual(len(files), 1)
        self.assertIn('"simulated": true', files[0].read_text())
        analytics = self.client.get('/api/analytics').json()
        self.assertEqual(analytics['readings_count'], 1)
        self.assertEqual(analytics['max_water_cm'], 170)

    def test_wrong_device_key_and_invalid_reading(self):
        self.assertEqual(self.client.post('/api/iot/readings', json=self.reading(), headers={'X-Device-Key': 'wrong'}).status_code, 401)
        headers = self.login()
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading(water=-5), headers=headers).status_code, 422)
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading(measured_at='2000-01-01T00:00:00Z'), headers=headers).status_code, 422)
        self.assertEqual(self.client.post('/api/readings/simulate', json=self.reading(measured_at='2026-11-16T00:00:00'), headers=headers).status_code, 422)

    def test_simulation_cannot_claim_to_be_physical(self):
        headers = self.login()
        r = self.client.post('/api/readings/simulate', json=self.reading(simulated=False), headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['simulated'])

    def test_call_permissions_and_transitions(self):
        headers = self.login('resident')
        self.assertEqual(self.client.post('/api/calls', json={'community_id': 'AR-002', 'text': 'Solicitação de vistoria'}, headers=headers).status_code, 403)
        r = self.client.post('/api/calls', json={'community_id': 'AR-001', 'text': '<img src=x onerror=alert(1)>'}, headers=headers)
        call_id = r.json()['id']
        self.assertEqual(self.client.patch(f'/api/calls/{call_id}', json={'status': 'Em análise'}, headers=headers).status_code, 403)
        headers = self.login()
        self.assertEqual(self.client.patch(f'/api/calls/{call_id}', json={'status': 'Concluído'}, headers=headers).status_code, 409)
        for status in ['Em análise', 'Concluído']:
            self.assertEqual(self.client.patch(f'/api/calls/{call_id}', json={'status': status}, headers=headers).status_code, 200)

    def test_notifications_dry_run_and_real_send_blocked(self):
        headers = self.login()
        self.client.post('/api/readings/simulate', json=self.reading(), headers=headers)
        alert_id = self.client.get('/api/state').json()['alerts'][0]['id']
        endpoint = f'/api/alerts/{alert_id}/notify'
        body = {'phone': '+5511999999999', 'channel': 'sms'}
        with patch('backend.integrations.send_twilio', new_callable=AsyncMock) as provider:
            response = self.client.post(endpoint, json=body, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['sent'])
            self.assertEqual(self.client.post(endpoint, json={**body, 'dry_run': False, 'confirm_send': True}, headers=headers).status_code, 403)
            provider.assert_not_called()

    def test_forecast_crosses_real_provider_contract_and_is_cached(self):
        headers = self.login()
        self.client.post('/api/readings/simulate', json=self.reading(water=25, soil_moisture_pct=25, rainfall_mm=0), headers=headers)
        example = {'provider': 'Open-Meteo', 'simulated': False, 'next_3h_mm': 40, 'time_utc': [], 'hourly_mm': [10, 10, 20]}
        with patch('backend.integrations.weather', new_callable=AsyncMock, return_value=example) as provider:
            r = self.client.post('/api/analysis/AR-001/refresh',json={},headers=headers)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()['forecast_next_3h_mm'], 40)
            self.assertFalse(r.json()['validated_for_emergencies'])
            self.assertEqual(self.client.get('/api/weather/AR-001').status_code, 200)
            self.assertEqual(provider.await_count, 1)

    def test_no_silent_fake_weather_on_provider_failure(self):
        import httpx
        self.login()
        with patch('backend.integrations.weather', new_callable=AsyncMock, side_effect=httpx.ConnectError('offline')):
            self.assertEqual(self.client.get('/api/weather/AR-001').status_code, 502)

    def test_acknowledgment_is_persisted(self):
        headers = self.login()
        self.client.post('/api/readings/simulate', json=self.reading(), headers=headers)
        alert_id = self.client.get('/api/state').json()['alerts'][0]['id']
        self.assertEqual(self.client.post(f'/api/alerts/{alert_id}/ack', json={}, headers=headers).status_code, 200)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM acknowledgments').fetchone()[0], 1)

    def test_replayed_and_future_telemetry_rejected(self):
        from datetime import timedelta
        headers = self.login()
        body = self.reading()
        self.assertEqual(self.client.post('/api/readings/simulate', json=body, headers=headers).status_code, 200)
        self.assertEqual(self.client.post('/api/readings/simulate', json=body, headers=headers).status_code, 409)
        body['measured_at'] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        self.assertEqual(self.client.post('/api/readings/simulate', json=body, headers=headers).status_code, 422)

    def test_production_requires_https_and_sets_secure_cookie(self):
        import subprocess, sys
        env = dict(os.environ, APP_ENV='production', APP_ORIGIN='http://localhost:8080')
        invalid = subprocess.run([sys.executable, '-c', 'import backend.main'], env=env, capture_output=True)
        self.assertNotEqual(invalid.returncode, 0)
        env['APP_ORIGIN'] = 'https://example.test'
        script = """
from fastapi.testclient import TestClient
from backend.main import app
with TestClient(app,base_url='https://example.test') as client:
 response=client.post('/api/auth/login',json={'email':'gestor@example.com','password':'Teste#seguro-2026'})
 assert response.status_code==200,response.text
 cookie=response.headers['set-cookie']
 assert '__Host-alertario=' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie,cookie
 assert client.get('/api/auth/me').status_code==200
"""
        valid = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True)
        self.assertEqual(valid.returncode, 0, valid.stderr.decode())

    def test_stale_reading_is_not_current_risk(self):
        headers=self.login()
        self.client.post('/api/readings/simulate',json=self.reading(),headers=headers)
        with db.connect() as conn:
            conn.execute("UPDATE readings SET measured_at='2000-01-01T00:00:00+00:00'")
        sensor=self.client.get('/api/state').json()['sensors'][0]
        self.assertTrue(sensor['stale'])
        self.assertEqual(sensor['risk']['label'],'Desatualizado')
        self.assertEqual(self.client.get('/api/ai/AR-001').status_code,409)

    def test_empty_history_has_no_fabricated_samples(self):
        self.login()
        sensor=self.client.get('/api/state').json()['sensors'][0]
        self.assertEqual(sensor['samples'],[])
        self.assertEqual(sensor['history'],[])
        self.assertIsNone(sensor['water'])

    def test_forecast_refresh_updates_same_analysis_in_map_and_alert(self):
        headers=self.login()
        self.client.post('/api/readings/simulate',json=self.reading(water=55,soil_moisture_pct=35,rainfall_mm=0),headers=headers)
        forecast={'provider':'Open-Meteo','simulated':False,'next_3h_mm':40}
        with patch('backend.integrations.weather',new_callable=AsyncMock,return_value=forecast):
            answer=self.client.post('/api/analysis/AR-001/refresh',json={},headers=headers)
        self.assertEqual(answer.status_code,200,answer.text)
        result=answer.json();state=self.client.get('/api/state').json()
        self.assertEqual(result['label'],'Atenção')
        self.assertEqual(state['sensors'][0]['risk']['analysis_id'],result['analysis_id'])
        self.assertEqual(state['alerts'][0]['analysis_id'],result['analysis_id'])
        self.assertEqual(state['alerts'][0]['risk'],result['label'])

    def test_resident_receives_and_acknowledges_exact_alert(self):
        manager=self.login()
        self.client.post('/api/readings/simulate',json=self.reading(),headers=manager)
        self.client.post('/api/readings/simulate',json=self.reading(sensor_id='AR-002'),headers=manager)
        all_alerts=self.client.get('/api/state').json()['alerts']
        other=next(a for a in all_alerts if a['sensor_id']=='AR-002')
        resident=self.login('resident')
        inbox=self.client.get('/api/state').json()['alerts']
        self.assertTrue(inbox)
        self.assertTrue(all(a['sensor_id']=='AR-001' for a in inbox))
        alert=inbox[0]
        self.assertEqual(self.client.post(f"/api/alerts/{other['id']}/ack",json={},headers=resident).status_code,403)
        self.assertEqual(self.client.post(f"/api/alerts/{alert['id']}/ack",json={},headers=resident).status_code,200)
        updated=self.client.get('/api/state').json()['alerts']
        self.assertEqual(next(a for a in updated if a['id']==alert['id'])['acknowledged'],1)

    def test_equivalent_timezones_share_utc_hour(self):
        from datetime import timedelta
        headers=self.login();stamp=datetime.now(timezone.utc)
        for sensor,moment in [('AR-001',stamp),('AR-002',stamp.astimezone(timezone(timedelta(hours=-3))))]:
            self.assertEqual(self.client.post('/api/readings/simulate',json=self.reading(sensor_id=sensor,measured_at=moment.isoformat()),headers=headers).status_code,200)
        analytics=self.client.get('/api/analytics').json()
        self.assertEqual(len(analytics['hourly']),1)
        self.assertEqual(analytics['hourly'][0]['samples'],2)

    def test_dashboard_filters_apply_to_series_and_csv(self):
        import csv,io
        headers=self.login()
        self.client.post('/api/readings/simulate',json=self.reading(water=50,soil_moisture_pct=30),headers=headers)
        self.client.post('/api/readings/simulate',json=self.reading(sensor_id='AR-002',water=180,soil_moisture_pct=90),headers=headers)
        query='community=AR-001&origin=simulated'
        result=self.client.get('/api/analytics?'+query).json()
        self.assertEqual(result['readings_count'],1)
        self.assertEqual(result['max_water_cm'],50)
        self.assertEqual(result['avg_soil_pct'],30)
        self.assertEqual(len(result['series']),1)
        rows=list(csv.DictReader(io.StringIO(self.client.get('/api/readings.csv?'+query).text.lstrip('\ufeff'))))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['sensor_id'],'AR-001')
        self.assertEqual(self.client.get('/api/analytics?origin=device').json()['readings_count'],0)

    def test_old_measurement_is_stale_even_when_just_received(self):
        from datetime import timedelta
        headers=self.login()
        body=self.reading(measured_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
        self.assertEqual(self.client.post('/api/readings/simulate',json=body,headers=headers).status_code,200)
        sensor=self.client.get('/api/state').json()['sensors'][0]
        self.assertTrue(sensor['stale']);self.assertEqual(sensor['risk']['label'],'Desatualizado')
        self.assertEqual(self.client.post('/api/ai/AR-001/explain',json={},headers=headers).status_code,409)

    def test_authenticated_invalid_telemetry_preserved_as_rejected_bronze(self):
        import json
        response=self.client.post('/api/iot/readings',json=self.reading(soil_moisture_pct=150),headers={'X-Device-Key':'device-test-key'})
        self.assertEqual(response.status_code,422)
        events=[json.loads(line) for path in Path(os.environ['LAKE_PATH']).glob('*.jsonl') for line in path.read_text().splitlines()]
        self.assertEqual(events[0]['raw_payload']['soil_moisture_pct'],150)
        self.assertEqual(events[-1]['status'],'rejected')
        self.assertEqual(events[0]['receipt_id'],events[-1]['receipt_id'])
        with db.connect() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM readings').fetchone()[0],0)

    def test_replay_event_id_is_idempotent(self):
        headers=self.login()
        for attempt,expected in [(0,200),(1,409)]:
            response=self.client.post('/api/readings/simulate',json=self.reading(event_id='same-run:1'),headers=headers)
            self.assertEqual(response.status_code,expected,response.text)
        with db.connect() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM readings').fetchone()[0],1)

    def test_frontend_pages_and_shared_assets_are_served(self):
        self.login()
        for route in ['/','/mapa.html','/sensores.html','/morador.html','/gestao.html','/styles.css','/app.js','/charts.js']:
            response=self.client.get(route)
            self.assertEqual(response.status_code,200,route)
        self.assertIn('charts.js',self.client.get('/sensores.html').text)

    def test_migration_preserves_existing_users_and_is_repeatable(self):
        db.init_db();db.init_db()
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM users').fetchone()[0],2)
            self.assertIn('analysis_id',[r[1] for r in conn.execute('PRAGMA table_info(alerts)')])

    def test_invalid_dashboard_filter_rejected(self):
        self.login()
        for query in ['origin=unknown','community=bad','start=not-a-date','start=2026-01-02T00:00:00Z&end=2026-01-01T00:00:00Z']:
            self.assertEqual(self.client.get('/api/analytics?'+query).status_code,422,query)

    def test_file_replay_preserves_virtual_time_intervals(self):
        import json
        from iot.bridge import file_events
        path=Path(self.directory.name)/'samples.jsonl'
        path.write_text('\n'.join(json.dumps({'sensor_id':'AR-001','water_level_cm':v,'soil_moisture_pct':35,'uptime_ms':u}) for v,u in [(55,1000),(80,3000),(180,11000)]))
        events=list(file_events(path))
        self.assertEqual((events[1][1]-events[0][1]).total_seconds(),2)
        self.assertEqual((events[2][1]-events[0][1]).total_seconds(),10)
        self.assertEqual(events[0][2],list(file_events(path))[0][2])

    def test_historical_alert_keeps_its_original_class(self):
        headers=self.login()
        self.client.post('/api/readings/simulate',json=self.reading(water=180,soil_moisture_pct=90),headers=headers)
        self.client.post('/api/readings/simulate',json=self.reading(water=55,soil_moisture_pct=35,rainfall_mm=0),headers=headers)
        state=self.client.get('/api/state').json()
        self.assertEqual(state['sensors'][0]['risk']['label'],'Normal')
        self.assertTrue(any(a['risk']=='Alto' for a in state['alerts']))



    def test_service_monitor_requires_manager_and_returns_live_counters(self):
        self.assertEqual(self.client.get('/api/monitoring').status_code,401)
        self.login('resident')
        self.assertEqual(self.client.get('/api/monitoring').status_code,403)
        self.login();self.client.get('/api/health')
        result=self.client.get('/api/monitoring')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['database'],'ok')
        self.assertGreater(result.json()['requests_total'],0)
        self.assertIn('analyses',result.json()['records'])



if __name__ == '__main__':
    unittest.main()

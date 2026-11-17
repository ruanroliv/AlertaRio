"""Persistent, explicitly synthetic teaching dataset; no accounts or external sends."""
import math
from datetime import datetime, timedelta, timezone
from .db import connect
from . import engine, lake

VERSION = 'dashboard-demo-v1'


def seed_demo():
    """Load once. Existing samples/accounts stay intact; each point gains history."""
    count = 0
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS demo_seeds (version TEXT PRIMARY KEY, created_at TEXT NOT NULL)')
        if db.execute('SELECT 1 FROM demo_seeds WHERE version=?', (VERSION,)).fetchone():
            return 0
        now = datetime.now(timezone.utc)
        profiles = [(45, 35, 0), (105, 72, 14), (165, 89, 32), (125, 57, 18), (65, 48, 5)]
        for index, device in enumerate(db.execute('SELECT id FROM devices ORDER BY id').fetchall()):
            sensor = device['id']
            earliest = db.execute('SELECT measured_at FROM readings WHERE sensor_id=? ORDER BY julianday(measured_at) LIMIT 1', (sensor,)).fetchone()
            # Existing Arduino data remains the latest measurement.
            end = (datetime.fromisoformat(earliest['measured_at'].replace('Z', '+00:00')) - timedelta(minutes=30)) if earliest else now
            water, soil, rain = profiles[index % len(profiles)]
            for step in range(49):
                measured = (end - timedelta(minutes=30 * (48-step))).isoformat()
                phase = math.sin(step / 5 + index)
                payload = {'sensor_id':sensor, 'water_level_cm':round(water + phase*18 + step/8, 1),
                           'soil_moisture_pct':round(min(99, soil + phase*6), 1),
                           'rainfall_mm':round(max(0, rain + phase*4), 1),
                           'measured_at':measured, 'simulated':True,
                           'event_id':f'{VERSION}:{sensor}:{step}', 'dataset':'DEMONSTRACAO FICTICIA'}
                receipt = lake.record(payload, 'demo-seed', 'received')
                cursor = db.execute('''INSERT INTO readings(sensor_id,measured_at,received_at,water,soil,rain,simulated,source,event_id,receipt_id)
                    VALUES(?,?,?,?,?,?,1,'demo-seed',?,?)''',
                    (sensor,measured,now.isoformat(),payload['water_level_cm'],payload['soil_moisture_pct'],payload['rainfall_mm'],payload['event_id'],receipt))
                row = db.execute('SELECT * FROM readings WHERE id=?',(cursor.lastrowid,)).fetchone()
                # Historical fixtures do not announce new operational alerts.
                before = db.execute('SELECT COALESCE(MAX(id),0) FROM alerts').fetchone()[0]
                result = engine.analyze(db,row)
                db.execute('UPDATE analyses SET created_at=? WHERE id=?',(measured,result['analysis_id']))
                db.execute("UPDATE alerts SET created_at=?, text='[DEMONSTRAÇÃO FICTÍCIA] ' || text WHERE id>?",(measured,before))
                lake.record(payload,'demo-seed','processed',receipt,reading_id=row['id'],analysis_id=result['analysis_id'])
                count += 1
            db.execute('INSERT INTO calls(community_id,text,status,user_id) VALUES(?,?,?,NULL)',
                       (sensor,'[DEMONSTRAÇÃO FICTÍCIA] '+['Acúmulo de água na rua de acesso.','Solo encharcado próximo à escadaria.','Relato simulado de movimentação de terra.','Bueiro com obstrução simulada.','Solicitação simulada de vistoria.'][index % 5],
                        ['Aberto','Em análise','Concluído','Aberto','Em análise'][index % 5]))
        db.execute('INSERT INTO demo_seeds VALUES(?,?)',(VERSION,now.isoformat()))
    return count

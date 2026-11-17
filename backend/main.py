"""AlertaRio API and same-origin frontend. Run with one worker for this SQLite MVP."""
import csv
import io
import json
import logging
import os
import secrets
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, ConfigDict, ValidationError

from .db import ROOT, connect, init_db
from .security import digest, hash_password, verify_password
from .risk import RiskModel
from . import integrations, engine, analytics as analytics_service, lake, monitoring

PRODUCTION = os.environ.get('APP_ENV', 'development') == 'production'
ORIGIN = os.environ.get('APP_ORIGIN', 'http://localhost:8080').rstrip('/')
COOKIE = '__Host-alertario' if PRODUCTION else 'alertario_session'
if PRODUCTION and not ORIGIN.startswith('https://'):
    raise RuntimeError('Production requires APP_ORIGIN=https://...')
app = FastAPI(title='AlertaRio', docs_url=None, redoc_url=None, openapi_url=None)
init_db()
# Academic defaults: populate dashboard history once, never create a default login.
if not PRODUCTION and os.environ.get('DEMO_DATA', 'true').lower() == 'true':
    from .demo_data import seed_demo
    seed_demo()
MODEL = RiskModel()
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(24))
PASSWORD_SLOTS = threading.BoundedSemaphore(2)


def now():
    return datetime.now(timezone.utc).isoformat()


def audit(actor, action, target):
    with connect() as db:
        db.execute('INSERT INTO audit(created_at,actor,action,target) VALUES(?,?,?,?)',
                   (now(), str(actor), action, str(target)))


def user_for(request, manager=False, csrf=False):
    token = request.cookies.get(COOKIE, '')
    with connect() as db:
        row = db.execute('''SELECT users.id,users.role,users.community_id,sessions.csrf_hash,sessions.csrf_token
            FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE token_hash=? AND expires_at>? AND active=1''', (digest(token), time.time())).fetchone()
    if not row:
        raise HTTPException(401, 'Sessão inválida ou expirada')
    user = dict(row)
    if manager and user['role'] != 'manager':
        raise HTTPException(403, 'Acesso exclusivo de gestor')
    if csrf and not secrets.compare_digest(digest(request.headers.get('X-CSRF-Token', '')), user['csrf_hash']):
        raise HTTPException(403, 'Token CSRF inválido')
    return user


@app.middleware('http')
async def security_headers(request: Request, call_next):
    request_started=time.perf_counter()
    # JSON-only mutations plus exact Origin checking protect login and cookie-auth endpoints.
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        origin = request.headers.get('origin')
        if origin and origin != ORIGIN:
            return JSONResponse({'detail': 'Origem não autorizada'}, status_code=403)
        if not request.headers.get('content-type', '').startswith('application/json'):
            return JSONResponse({'detail': 'Use application/json'}, status_code=415)
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > 16384):
            return JSONResponse({'detail': 'Requisição excede o limite'}, status_code=413)
    try:
        response = await call_next(request)
    except Exception:
        logging.exception("Unhandled request failure")
        response = JSONResponse({"detail": "Erro interno. Consulte o log do servidor."}, status_code=500)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith('/api/') or request.url.path.endswith('.html') or request.url.path == '/':
        response.headers['Cache-Control'] = 'no-store'
    if PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    monitoring.observe(response.status_code,(time.perf_counter()-request_started)*1000)
    return response


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Login(StrictBody):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class Reading(StrictBody):
    sensor_id: str = Field(pattern=r'^AR-00[1-5]$')
    water_level_cm: float = Field(ge=0, le=200)
    soil_moisture_pct: float = Field(ge=0, le=100)
    rainfall_mm: float = Field(ge=0, le=300)
    measured_at: datetime
    simulated: bool = True
    event_id: str | None = Field(default=None, max_length=160)
    device_uptime_ms: int | None = Field(default=None, ge=0)
    raw_sensor: dict | None = None


class NewCall(StrictBody):
    community_id: str = Field(pattern=r'^AR-00[1-5]$')
    text: str = Field(min_length=8, max_length=500)


class CallStatus(StrictBody):
    status: Literal['Em análise', 'Concluído']


class Notification(StrictBody):
    phone: str = Field(pattern=r'^\+[1-9][0-9]{7,14}$')
    channel: Literal['sms', 'whatsapp']
    dry_run: bool = True
    confirm_send: bool = False


@app.get('/api/monitoring')
def service_monitor(request: Request):
    user_for(request,manager=True)
    with connect() as db:
        counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('readings','analyses','alerts')}
    return {**monitoring.snapshot(),'database':'ok','records':counts,'checked_at':now()}


@app.get('/api/health')
def health():
    with connect() as db:db.execute('SELECT 1').fetchone()
    return {'status': 'ok', 'mode': 'backend', 'model': 'knn-synthetic-v1', 'emergency_validated': False}


@app.post('/api/auth/login')
def login(body: Login, request: Request, response: Response):
    email = body.email.strip().lower()
    # Do not trust client X-Forwarded-For; configure a trusted reverse proxy explicitly.
    ip = request.client.host if request.client else 'unknown'
    keys = [digest('account:' + email), digest('ip:' + ip)]
    with connect() as db:
        db.execute('DELETE FROM login_attempts WHERE created_at<?', (time.time() - 900,))
        for key, limit in zip(keys, [8, 40]):
            count = db.execute('SELECT count(*) FROM login_attempts WHERE key=?', (key,)).fetchone()[0]
            if count >= limit:
                raise HTTPException(429, 'Muitas tentativas; tente novamente em 15 minutos')
        # Count before password verification, including successful calls, to bound hash work.
        for key in keys:
            db.execute('INSERT INTO login_attempts VALUES(?,?)', (key, time.time()))
        user = db.execute('SELECT * FROM users WHERE email=? AND active=1', (email,)).fetchone()
    if not PASSWORD_SLOTS.acquire(blocking=False):
        raise HTTPException(429, 'Servidor ocupado; tente novamente em instantes')
    try:
        valid = verify_password(body.password, user['password_hash'] if user else DUMMY_PASSWORD_HASH)
    finally:
        PASSWORD_SLOTS.release()
    if not user or not valid:
        raise HTTPException(401, 'E-mail ou senha inválidos')
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with connect() as db:
        db.execute('DELETE FROM sessions WHERE expires_at<? OR token_hash=?',
                   (time.time(), digest(request.cookies.get(COOKIE, ''))))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',
                   (digest(token), user['id'], digest(csrf), csrf, time.time() + 28800))
    response.set_cookie(COOKIE, token, httponly=True, secure=PRODUCTION, samesite='strict', max_age=28800, path='/')
    audit(user['id'], 'login', user['id'])
    return {'id': user['id'], 'profile': user['role'], 'community_id': user['community_id'], 'csrf_token': csrf}


@app.get('/api/auth/me')
def me(request: Request):
    user = user_for(request)
    return {'id': user['id'], 'profile': user['role'], 'community_id': user['community_id'], 'csrf_token': user['csrf_token']}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    user = user_for(request, csrf=True)
    with connect() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(request.cookies.get(COOKIE, '')),))
    response.delete_cookie(COOKIE, path='/', secure=PRODUCTION, httponly=True, samesite='strict')
    audit(user['id'], 'logout', user['id'])
    return {'ok': True}


def latest(db, device_id):
    return db.execute('SELECT * FROM readings WHERE sensor_id=? ORDER BY julianday(measured_at) DESC,id DESC LIMIT 1', (device_id,)).fetchone()


def assessment(row):
    return MODEL.predict(row['water'], row['soil'], row['rain'])


def state_for(user):
    with connect() as db:
        sensors=[]
        for raw in db.execute('SELECT id,name,area,type,x,y FROM devices ORDER BY id'):
            item=dict(raw);row=latest(db,item['id'])
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['measured_at'])).total_seconds() if row else None
            item.update({'water':row['water'] if row else None,'soil':row['soil'] if row else None,
                         'rain':row['rain'] if row else None,'received_at':row['received_at'] if row else None,
                         'measured_at':analytics_service.normalized_time(row['measured_at']) if row else None,
                         'has_reading':row is not None,'simulated':bool(row['simulated']) if row else True,
                         'reading_age_seconds':round(age) if age is not None else None,
                         'stale':age is None or age>300})
            item['last_risk']=engine.get_analysis(db,row) if row else None
            item['risk']=({'label':'Desatualizado','cls':'amber','score':None} if item['stale'] else item['last_risk']) if row else {'label':'Sem dados','cls':'amber','score':None}
            samples=[dict(r) for r in db.execute('SELECT id,measured_at,received_at,water,soil,simulated FROM readings WHERE sensor_id=? ORDER BY julianday(measured_at) DESC,id DESC LIMIT 120',(item['id'],))][::-1]
            for sample in samples:sample['measured_at']=analytics_service.normalized_time(sample['measured_at'])
            item['samples']=samples
            item['history']=[r['water'] if item['type']=='Nível de água' else r['soil'] for r in samples[-8:]]
            sensors.append(item)
        params=[user['id']]
        where=''
        if user['role']!='manager':where=' WHERE a.sensor_id=?';params.append(user['community_id'])
        alerts=[dict(row) for row in db.execute('''SELECT a.*,d.name AS community,
            CASE WHEN ack.alert_id IS NULL THEN 0 ELSE 1 END AS acknowledged
            FROM alerts a JOIN devices d ON d.id=a.sensor_id
            LEFT JOIN acknowledgments ack ON ack.alert_id=a.id AND ack.user_id=?'''+where+' ORDER BY a.id DESC LIMIT 100',params)]
        ids={item['id']:i for i,item in enumerate(sensors)}
        for alert in alerts:
            alert['sensor']=ids[alert['sensor_id']]
            alert['time']=alert['created_at'][:16].replace('T',' ')+' UTC'
        query='SELECT calls.*,devices.name AS place FROM calls JOIN devices ON devices.id=calls.community_id'
        values=()
        if user['role']!='manager':query+=' WHERE calls.user_id=?';values=(user['id'],)
        calls=[dict(c) for c in db.execute(query+' ORDER BY calls.id DESC LIMIT 100',values)]
    return {'sensors':sensors,'alerts':alerts,'occurrences':calls,'source':'sqlite','server_time':now()}


@app.get('/api/state')
def state(request: Request):
    return state_for(user_for(request))


def _store_reading(body,source,receipt_id):
    measured=body.measured_at
    if measured.tzinfo is None:raise HTTPException(422,'measured_at precisa conter fuso horário')
    measured=measured.astimezone(timezone.utc)
    age=(datetime.now(timezone.utc)-measured).total_seconds()
    if age>86400 or age < -300:raise HTTPException(422,'Leitura deve ter até 24h e no máximo 5 minutos no futuro')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT id FROM devices WHERE id=?',(body.sensor_id,)).fetchone():raise HTTPException(404,'Sensor não encontrado')
        if body.event_id and db.execute('SELECT id FROM readings WHERE sensor_id=? AND event_id=?',(body.sensor_id,body.event_id)).fetchone():
            raise HTTPException(409,'Evento já importado. Use --new-run somente para um novo exercício explícito.')
        previous=latest(db,body.sensor_id)
        if previous and measured<=datetime.fromisoformat(previous['measured_at']):raise HTTPException(409,'Leitura duplicada ou anterior à última amostra')
        stamp=now()
        cursor=db.execute('''INSERT INTO readings(sensor_id,measured_at,received_at,water,soil,rain,simulated,source,event_id,device_uptime_ms,receipt_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(body.sensor_id,measured.isoformat(),stamp,body.water_level_cm,body.soil_moisture_pct,
            body.rainfall_mm,int(body.simulated),source,body.event_id,body.device_uptime_ms,receipt_id))
        row=db.execute('SELECT * FROM readings WHERE id=?',(cursor.lastrowid,)).fetchone()
        result=engine.analyze(db,row,engine.cached_weather(db,body.sensor_id))
    return {'id':row['id'],'risk':result,'analysis_id':result['analysis_id'],'receipt_id':receipt_id,'simulated':body.simulated}


def store_reading(body,source,raw_payload=None,receipt_id=None):
    raw=raw_payload if raw_payload is not None else body.model_dump(mode='json')
    receipt_id=receipt_id or lake.record(raw,source,'received')
    try:
        result=_store_reading(body,source,receipt_id)
    except HTTPException as error:
        lake.record(raw,source,'rejected',receipt_id,reason=str(error.detail))
        raise
    lake.record(raw,source,'processed',receipt_id,reading_id=result['id'],analysis_id=result['analysis_id'])
    return result


@app.post('/api/readings/simulate')
def simulate(body: Reading, request: Request):
    user = user_for(request, manager=True, csrf=True)
    body.simulated = True
    result = store_reading(body, 'web-simulator')
    audit(user['id'], 'simulate_reading', result['id'])
    return result


@app.post('/api/iot/readings')
async def ingest(request: Request):
    try:raw=await request.json()
    except ValueError:raise HTTPException(422,'JSON inválido')
    if not isinstance(raw,dict):raise HTTPException(422,'Envie um objeto JSON')
    sensor_id=raw.get('sensor_id')
    if not isinstance(sensor_id,str):raise HTTPException(422,'sensor_id ausente')
    key=request.headers.get('X-Device-Key','')
    with connect() as db:
        device=db.execute('SELECT key_hash FROM devices WHERE id=?',(sensor_id,)).fetchone()
        if not device or not device['key_hash'] or not secrets.compare_digest(device['key_hash'],digest(key)):
            raise HTTPException(401,'Credencial de dispositivo inválida')
        limit_key='device:'+sensor_id
        old=db.execute('SELECT last_used FROM integration_limits WHERE name=?',(limit_key,)).fetchone()
        if old and time.time()-old['last_used']<1:raise HTTPException(429,'Limite de uma leitura por segundo por sensor')
        db.execute('INSERT OR REPLACE INTO integration_limits VALUES(?,?)',(limit_key,time.time()))
    # Bronze retains the original authenticated payload, including its uptime and invalid values.
    try:receipt_id=lake.record(raw,'device-bridge','received')
    except (ValueError,TypeError):raise HTTPException(422,'JSON contém valor inválido')
    try:body=Reading.model_validate(raw)
    except ValidationError as error:
        lake.record(raw,'device-bridge','rejected',receipt_id,reason='validation',errors=error.errors(include_context=False,include_input=False))
        raise HTTPException(422,'Campos da leitura inválidos; motivo registrado na Bronze')
    return store_reading(body,'device-bridge',raw,receipt_id)


@app.post('/api/calls')
def create_call(body: NewCall, request: Request):
    user = user_for(request, csrf=True)
    if user['role'] == 'resident' and body.community_id != user['community_id']:
        raise HTTPException(403, 'Registre chamados somente na sua comunidade')
    with connect() as db:
        cur = db.execute('INSERT INTO calls(community_id,text,user_id) VALUES(?,?,?)',
                         (body.community_id, body.text, user['id']))
    return {'id': cur.lastrowid}


@app.patch('/api/calls/{call_id}')
def update_call(call_id: int, body: CallStatus, request: Request):
    user = user_for(request, manager=True, csrf=True)
    with connect() as db:
        row = db.execute('SELECT status FROM calls WHERE id=?', (call_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Chamado não encontrado')
        expected = {'Aberto': 'Em análise', 'Em análise': 'Concluído'}.get(row['status'])
        if body.status != expected:
            raise HTTPException(409, 'Transição de status inválida')
        db.execute('UPDATE calls SET status=? WHERE id=?', (body.status, call_id))
    audit(user['id'], 'update_call', call_id)
    return {'ok': True}


@app.post('/api/alerts/{alert_id}/ack')
def acknowledge(alert_id: int, request: Request):
    user = user_for(request, csrf=True)
    with connect() as db:
        alert=db.execute('SELECT sensor_id FROM alerts WHERE id=?',(alert_id,)).fetchone()
        if not alert:raise HTTPException(404,'Alerta não encontrado')
        if user['role']!='manager' and alert['sensor_id']!=user['community_id']:raise HTTPException(403,'Alerta de outra comunidade')
        db.execute('INSERT OR IGNORE INTO acknowledgments VALUES(?,?,?)', (user['id'], alert_id, now()))
    return {'ok': True}


def integration_limit(name, seconds):
    with connect() as db:
        old = db.execute('SELECT last_used FROM integration_limits WHERE name=?', (name,)).fetchone()
        if old and time.time() - old['last_used'] < seconds:
            raise HTTPException(429, 'Aguarde antes de consultar novamente')
        db.execute('INSERT OR REPLACE INTO integration_limits VALUES(?,?)', (name, time.time()))


async def forecast_for(sensor_id):
    with connect() as db:
        device = db.execute('SELECT latitude,longitude FROM devices WHERE id=?', (sensor_id,)).fetchone()
        cached = db.execute('SELECT payload,fetched_at FROM weather_cache WHERE sensor_id=?', (sensor_id,)).fetchone()
    if not device:
        raise HTTPException(404, 'Sensor não encontrado')
    if cached and time.time() - cached['fetched_at'] < 600:
        return {**json.loads(cached['payload']), 'cached': True}
    integration_limit('weather:' + sensor_id, 30)
    try:
        result = await integrations.weather(device['latitude'], device['longitude'])
        result.update({'fetched_at': now(), 'coordinates_kind': 'approximate_community_center'})
        with connect() as db:
            db.execute('INSERT OR REPLACE INTO weather_cache VALUES(?,?,?)', (sensor_id, json.dumps(result), time.time()))
        return {**result, 'cached': False}
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, 'Previsão indisponível; nenhum valor fictício foi substituído')


@app.get('/api/weather/{sensor_id}')
async def get_weather(sensor_id: str, request: Request):
    user_for(request)
    return await forecast_for(sensor_id)


def fresh_reading(db,sensor_id):
    row=latest(db,sensor_id)
    if not row:raise HTTPException(404,'Sensor sem leitura')
    if (datetime.now(timezone.utc)-datetime.fromisoformat(row['measured_at'])).total_seconds()>300:
        raise HTTPException(409,'Leitura desatualizada; envie uma amostra recente antes de classificar')
    return row


@app.get('/api/ai/{sensor_id}')
def predict(sensor_id: str,request: Request,use_forecast: bool=False):
    user_for(request)
    if use_forecast:raise HTTPException(409,'Atualize a análise pelo POST /api/analysis/{sensor_id}/refresh')
    with connect() as db:
        row=fresh_reading(db,sensor_id)
        return engine.get_analysis(db,row)


@app.post('/api/analysis/{sensor_id}/refresh')
async def refresh_analysis(sensor_id: str,request: Request):
    user=user_for(request,manager=True,csrf=True)
    with connect() as db:reading=fresh_reading(db,sensor_id)
    forecast=await forecast_for(sensor_id)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current=fresh_reading(db,sensor_id)
        result=engine.analyze(db,current,forecast)
    audit(user['id'],'refresh_analysis',result['analysis_id'])
    return result


@app.post('/api/ai/{sensor_id}/explain')
async def explain(sensor_id: str,request: Request):
    user=user_for(request,manager=True,csrf=True)
    integration_limit('ollama:'+str(user['id']),30)
    with connect() as db:result=engine.get_analysis(db,fresh_reading(db,sensor_id))
    try:
        answer=await integrations.explain_with_ollama(result)
        return {**answer,'analysis_id':result['analysis_id']}
    except (httpx.HTTPError,KeyError,ValueError):raise HTTPException(503,'Ollama indisponível; a análise local continua funcionando')


@app.post('/api/alerts/{alert_id}/notify')
async def notify(alert_id: int, body: Notification, request: Request):
    user = user_for(request, manager=True, csrf=True)
    with connect() as db:
        alert = db.execute('SELECT alerts.*,devices.name FROM alerts JOIN devices ON devices.id=alerts.sensor_id WHERE alerts.id=?', (alert_id,)).fetchone()
    if not alert:
        raise HTTPException(404, 'Alerta não encontrado')
    text = f"[EXERCÍCIO ACADÊMICO — NÃO É AVISO OFICIAL] AlertaRio: {alert['name']}. Classificação experimental {alert['risk']}. Dados sem validação para emergências."
    if body.dry_run:
        return {'sent': False, 'dry_run': True, 'text': text, 'channel': body.channel}
    if not body.confirm_send or os.environ.get('ENABLE_REAL_MESSAGES') != 'true':
        raise HTTPException(403, 'Envio real requer ENABLE_REAL_MESSAGES=true e confirm_send=true')
    allowed = {phone.strip() for phone in os.environ.get('MESSAGE_TEST_RECIPIENTS', '').split(',') if phone.strip()}
    if body.phone not in allowed:
        raise HTTPException(403, 'Destinatário fora da lista de testes autorizados')
    required = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_FROM' if body.channel == 'whatsapp' else 'TWILIO_SMS_FROM']
    if not all(os.environ.get(name) for name in required):
        raise HTTPException(503, 'Configure as credenciais e o remetente do provedor antes do envio')
    # Claim once before calling the provider. Ambiguous failures stay unknown to prevent duplicate sends.
    with connect() as db:
        try:
            cur = db.execute('INSERT INTO deliveries(alert_id,recipient_hash,channel,state,created_at) VALUES(?,?,?,?,?)',
                             (alert_id, digest(body.phone), body.channel, 'pending', now()))
            delivery_id = cur.lastrowid
        except __import__('sqlite3').IntegrityError:
            raise HTTPException(409, 'Já existe tentativa para este alerta, destinatário e canal')
    try:
        result = await integrations.send_twilio(body.phone, text, body.channel)
    except (httpx.HTTPError, ValueError, KeyError):
        with connect() as db:
            db.execute("UPDATE deliveries SET state='unknown' WHERE id=?", (delivery_id,))
        raise HTTPException(502, 'Falha ou resultado incerto no provedor; verifique antes de tentar outro envio')
    with connect() as db:
        db.execute("UPDATE deliveries SET state='accepted',provider_id=? WHERE id=?", (result['provider_id'], delivery_id))
    audit(user['id'], 'message_accepted', delivery_id)
    return {'sent': True, 'delivery_confirmed': False, **result}


def filtered_dashboard(community=None,start=None,end=None,origin='all'):
    if community and community not in {f'AR-00{i}' for i in range(1,6)}:raise HTTPException(422,'Comunidade inválida')
    if origin not in ('all','simulated','device'):raise HTTPException(422,'Origem inválida')
    try:
        if start and end and datetime.fromisoformat(analytics_service.normalized_time(start))>datetime.fromisoformat(analytics_service.normalized_time(end)):
            raise ValueError('Início posterior ao fim')
        return analytics_service.dashboard(community,start,end,origin)
    except ValueError as error:raise HTTPException(422,str(error))


@app.get('/api/analytics')
def analytics(request: Request,community: str|None=None,start: str|None=None,end: str|None=None,origin: str='all'):
    user_for(request)
    return filtered_dashboard(community,start,end,origin)


@app.get('/api/readings.csv')
def export(request: Request,community: str|None=None,start: str|None=None,end: str|None=None,origin: str='all'):
    user_for(request)
    filtered_dashboard(community,start,end,origin)
    rows=analytics_service.rows_for(community,start,end,origin)
    fields=['id','sensor_id','measured_at','received_at','water','soil','rain','simulated','source']
    output=io.StringIO();writer=csv.writer(output);writer.writerow(fields+['analysis_id','risk'])
    for row in rows:writer.writerow([row[k] for k in fields]+[row['analysis']['analysis_id'],row['analysis']['label']])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=alertario-leituras.csv'})


@app.get('/config.js')
def frontend_config():
    return Response("window.ALERTARIO_CONFIG = Object.freeze({mode: 'backend'});", media_type='application/javascript', headers={'Cache-Control':'no-store'})


@app.get('/')
def root():
    return FileResponse(ROOT / 'frontend' / 'index.html')


@app.get('/{filename}')
def frontend(filename: str, request: Request):
    allowed = {'index.html', 'mapa.html', 'sensores.html', 'morador.html', 'gestao.html', 'styles.css', 'app.js', 'charts.js'}
    if filename not in allowed:
        raise HTTPException(404)
    if filename.endswith('.html') and filename != 'index.html':
        try:
            user_for(request, manager=filename == 'gestao.html')
        except HTTPException as error:
            if error.status_code == 401:
                from fastapi.responses import RedirectResponse
                return RedirectResponse('/index.html', status_code=303)
            raise
    return FileResponse(ROOT / 'frontend' / filename)

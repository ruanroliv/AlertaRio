"""One persisted analysis drives the map, dashboard and citizen alert."""
import json
from datetime import datetime, timezone
from .risk import RiskModel

MODEL = RiskModel()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_analysis(db, reading):
    row = db.execute('SELECT id,result,created_at FROM analyses WHERE reading_id=? ORDER BY id DESC LIMIT 1',
                     (reading['id'],)).fetchone()
    if row:
        return {**json.loads(row['result']), 'analysis_id': row['id'], 'analyzed_at': row['created_at']}
    # Legacy reads are displayed with a deterministic result, but no invented analysis ID.
    return {**MODEL.predict(reading['water'], reading['soil'], reading['rain']),
            'analysis_id': None, 'analyzed_at': None, 'legacy': True}


def cached_weather(db, sensor_id):
    import time
    row=db.execute('SELECT payload,fetched_at FROM weather_cache WHERE sensor_id=?',(sensor_id,)).fetchone()
    return json.loads(row['payload']) if row and time.time()-row['fetched_at'] < 600 else None


def analyze(db, reading, forecast=None):
    previous = db.execute('''SELECT a.result FROM analyses a JOIN readings r ON r.id=a.reading_id
        WHERE r.sensor_id=? ORDER BY julianday(r.measured_at) DESC,a.id DESC LIMIT 1''',(reading['sensor_id'],)).fetchone()
    result=MODEL.predict(reading['water'],reading['soil'],reading['rain'],
                         forecast['next_3h_mm'] if forecast else None)
    result.update({'weather': forecast, 'reading_id': reading['id'],
                   'reading_measured_at': reading['measured_at'],
                   'reading_simulated': bool(reading['simulated']),
                   'version': 'analysis-v2', 'automatic': True})
    stamp=utc_now()
    cursor=db.execute('INSERT INTO analyses(reading_id,created_at,result) VALUES(?,?,?)',
                      (reading['id'],stamp,json.dumps(result,ensure_ascii=False)))
    result.update({'analysis_id':cursor.lastrowid,'analyzed_at':stamp})
    if previous is None or json.loads(previous['result'])['label'] != result['label']:
        text=(f"Exercício AlertaRio: classificação {result['label']}. "
              f"Água {reading['water']:g} cm e umidade {reading['soil']:g}%. "
              "Informação experimental; acompanhe os canais oficiais.")
        db.execute('''INSERT INTO alerts(sensor_id,created_at,risk,text,simulated,analysis_id,reading_id)
                      VALUES(?,?,?,?,?,?,?)''',
                   (reading['sensor_id'],stamp,result['label'],text,reading['simulated'],
                    result['analysis_id'],reading['id']))
    return result

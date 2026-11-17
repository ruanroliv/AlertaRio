import json
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def connect():
    path = Path(
        os.environ.get(
            'DATABASE_PATH',
            str(ROOT / 'data' / 'alertario.db')
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(path, timeout=15)

    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')

        with db:
            yield db
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('resident','manager')),
            community_id TEXT NOT NULL DEFAULT 'AR-001', active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            csrf_hash TEXT NOT NULL, csrf_token TEXT NOT NULL, expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (key TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS attempts_key ON login_attempts(key,created_at);
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL,
            type TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL, key_hash TEXT,
            latitude REAL NOT NULL, longitude REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY, sensor_id TEXT NOT NULL REFERENCES devices(id),
            measured_at TEXT NOT NULL, received_at TEXT NOT NULL,
            water REAL NOT NULL, soil REAL NOT NULL, rain REAL NOT NULL,
            simulated INTEGER NOT NULL, source TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS readings_sensor ON readings(sensor_id,id);
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY, sensor_id TEXT NOT NULL REFERENCES devices(id),
            created_at TEXT NOT NULL, risk TEXT NOT NULL, text TEXT NOT NULL,
            simulated INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY, community_id TEXT NOT NULL REFERENCES devices(id),
            text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aberto', user_id INTEGER REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS acknowledgments (
            user_id INTEGER REFERENCES users(id), alert_id INTEGER REFERENCES alerts(id),
            created_at TEXT NOT NULL, PRIMARY KEY(user_id,alert_id));
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL,
            action TEXT NOT NULL, target TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY, alert_id INTEGER NOT NULL REFERENCES alerts(id),
            recipient_hash TEXT NOT NULL, channel TEXT NOT NULL, state TEXT NOT NULL,
            provider_id TEXT, created_at TEXT NOT NULL,
            UNIQUE(alert_id,recipient_hash,channel));
        CREATE TABLE IF NOT EXISTS weather_cache (sensor_id TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS integration_limits (name TEXT PRIMARY KEY, last_used REAL NOT NULL);
        ''')
        # Additive migration: existing accounts, readings and acknowledgments are preserved.
        for table, column, definition in [
            ('readings','event_id','TEXT'),
            ('readings','device_uptime_ms','INTEGER'),
            ('readings','receipt_id','TEXT'),
            ('alerts','analysis_id','INTEGER'),
            ('alerts','reading_id','INTEGER')
        ]:
            names={row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if column not in names:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        db.executescript('''
        CREATE UNIQUE INDEX IF NOT EXISTS readings_event ON readings(sensor_id,event_id) WHERE event_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY, reading_id INTEGER NOT NULL REFERENCES readings(id),
            created_at TEXT NOT NULL, result TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS analyses_reading ON analyses(reading_id,id);
        ''')
        items = [
            ('AR-001','Rio das Pedras','Canal principal','Nível de água',61,62,-22.98,-43.33),
            ('AR-002','Rocinha','Encosta · setor 03','Umidade do solo',39,70,-22.99,-43.25),
            ('AR-003','Complexo do Alemão','Encosta · setor 01','Umidade do solo',65,27,-22.86,-43.27),
            ('AR-004','Tijuca','Rio Maracanã','Nível de água',37,37,-22.92,-43.23),
            ('AR-005','Santa Teresa','Encosta · setor 02','Umidade do solo',50,47,-22.92,-43.19),
        ]
        for row in items:
            db.execute('INSERT OR IGNORE INTO devices(id,name,area,type,x,y,latitude,longitude) VALUES(?,?,?,?,?,?,?,?)', row)

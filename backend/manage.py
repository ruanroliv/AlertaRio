"""Administrative commands. Passwords are requested via getpass, never CLI arguments."""
import argparse
import getpass
import secrets
from datetime import datetime, timezone
from .db import connect, init_db
from .security import hash_password, digest


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create-user')
    create.add_argument('--email', required=True)
    create.add_argument('--role', choices=['resident', 'manager'], default='resident')
    create.add_argument('--community', choices=[f'AR-00{i}' for i in range(1, 6)], default='AR-001')
    device = sub.add_parser('device-key')
    device.add_argument('--sensor', required=True, choices=[f'AR-00{i}' for i in range(1, 6)])
    sub.add_parser('seed-demo')
    args = parser.parse_args()
    init_db()
    if args.command == 'create-user':
        email = args.email.strip().lower()
        if '@' not in email or len(email) > 254:
            parser.error('E-mail inválido')
        password = getpass.getpass('Senha (mínimo 12 caracteres): ')
        confirm = getpass.getpass('Confirme a senha: ')
        if password != confirm or not 12 <= len(password) <= 128:
            parser.error('Senhas diferentes ou comprimento inválido')
        with connect() as db:
            try:
                db.execute('INSERT INTO users(email,password_hash,role,community_id) VALUES(?,?,?,?)',
                           (email, hash_password(password), args.role, args.community))
            except __import__('sqlite3').IntegrityError:
                parser.error('Usuário já cadastrado')
        print('Usuário criado. Nenhuma senha padrão foi configurada.')
    elif args.command == 'device-key':
        key = secrets.token_urlsafe(32)
        with connect() as db:
            cur = db.execute('UPDATE devices SET key_hash=? WHERE id=?', (digest(key), args.sensor))
        if cur.rowcount != 1:
            parser.error('Dispositivo não encontrado')
        print('Chave exibida uma única vez; salve em variável de ambiente local:')
        print(key)
    else:
        from .main import Reading, store_reading
        values = [(142,62,38),(45,70,38),(32,44,8),(64,48,12),(28,51,9)]
        with connect() as db:
            if db.execute('SELECT count(*) FROM readings').fetchone()[0]:
                parser.error('Banco já tem leituras. Seed cancelado para preservar os dados.')
        for i,(water,soil,rain) in enumerate(values, 1):
            store_reading(Reading(sensor_id=f'AR-00{i}', water_level_cm=water,
                                 soil_moisture_pct=soil, rainfall_mm=rain,
                                 measured_at=datetime.now(timezone.utc), simulated=True), 'demo-seed')
        print('Cinco leituras sintéticas inseridas e identificadas como simulação.')


if __name__ == '__main__':
    main()

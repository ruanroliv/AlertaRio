"""Preview an academic test notification; real send requires an explicit interactive confirmation."""
import argparse
import getpass
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://localhost:8080')
    parser.add_argument('--alert-id', type=int, required=True)
    parser.add_argument('--channel', choices=['sms', 'whatsapp'], default='sms')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    email = input('E-mail do gestor: ')
    password = getpass.getpass('Senha: ')
    phone = input('Seu telefone de teste autorizado (E.164): ')
    try:
        with httpx.Client(base_url=args.api.rstrip('/'), timeout=30) as client:
            response = client.post('/api/auth/login', json={'email': email, 'password': password})
            response.raise_for_status()
            headers = {'X-CSRF-Token': response.json()['csrf_token']}
            path = f'/api/alerts/{args.alert_id}/notify'
            body = {'phone': phone, 'channel': args.channel, 'dry_run': True}
            preview = client.post(path, json=body, headers=headers)
            preview.raise_for_status()
            print(preview.json()['text'])
            if args.send:
                print('Envio real pode gerar cobrança. Use apenas um destinatário autorizado.')
                if input('Digite ENVIAR para confirmar: ') == 'ENVIAR':
                    response = client.post(path, json={**body, 'dry_run': False, 'confirm_send': True}, headers=headers)
                    response.raise_for_status()
                    print('Aceito pelo provedor; entrega ainda não confirmada.')
            client.post('/api/auth/logout', json={}, headers=headers)
    except (httpx.HTTPError, KeyError):
        print('Operação não concluída. Confira acesso, configuração e logs do servidor/provedor.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()

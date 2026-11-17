"""Explicit external integrations. No credentials are returned to the browser."""
import os
import re
import httpx


async def weather(latitude, longitude):
    async with httpx.AsyncClient(timeout=12, trust_env=True) as client:
        response = await client.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': latitude, 'longitude': longitude,
            'hourly': 'precipitation', 'forecast_hours': 4, 'timezone': 'UTC',
        })
        response.raise_for_status()
        body = response.json()
    hourly = body['hourly']
    # Index 0 is the current hourly period; indices 1..3 are the next three periods.
    values = hourly['precipitation'][1:4]
    if len(values) != 3 or any(v is None for v in values):
        raise ValueError('Previsão incompleta')
    return {'provider': 'Open-Meteo', 'simulated': False, 'next_3h_mm': sum(values),
            'time_utc': hourly['time'][1:4], 'hourly_mm': values,
            'attribution_url': 'https://open-meteo.com/', 'kind': 'forecast_not_sensor_measurement'}


async def explain_with_ollama(assessment):
    base = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    model = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
    prompt = (
        'Você explica um exercício acadêmico de monitoramento. Dados e modelo são sintéticos, '
        'sem validação para emergências. Explique em português em até 100 palavras os fatores '
        'da classificação abaixo. Não invente dados, locais, horários ou probabilidades. '
        'Não emita ordem de evacuação nem recomendação operacional. Mencione que é experimental. '
        f'Dados estruturados: {assessment}'
    )
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(base + '/api/generate', json={
            'model': model, 'prompt': prompt, 'stream': False,
            'options': {'temperature': 0, 'num_predict': 180},
        })
        response.raise_for_status()
        answer = response.json()['response']
    return {'text': answer, 'provider': 'Ollama', 'model': model, 'experimental': True}


async def send_twilio(phone, text, channel):
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone):
        raise ValueError('Telefone deve usar formato E.164')
    sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    sender = os.environ.get('TWILIO_WHATSAPP_FROM' if channel == 'whatsapp' else 'TWILIO_SMS_FROM', '')
    if not sid or not token or not sender:
        raise ValueError('Credenciais do provedor não configuradas')
    to = ('whatsapp:' if channel == 'whatsapp' else '') + phone
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
                                     auth=(sid, token), data={'To': to, 'From': sender, 'Body': text})
        response.raise_for_status()
        body = response.json()
    return {'provider_id': body['sid'], 'provider_status': body['status']}

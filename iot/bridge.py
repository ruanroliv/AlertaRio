"""Replay Wokwi/Tinkercad JSONL or forward physical USB serial to the same API."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import httpx


def payload(raw,simulated,rain,measured,event_id):
    if 'error' in raw:raise ValueError('Falha do sensor; leitura descartada')
    return {'sensor_id':raw['sensor_id'],'water_level_cm':float(raw['water_level_cm']),
            'soil_moisture_pct':float(raw['soil_moisture_pct']),'rainfall_mm':rain,
            'measured_at':measured.isoformat(),'simulated':simulated,
            'device_uptime_ms':raw.get('uptime_ms'),'event_id':event_id,'raw_sensor':raw}


def file_events(path,new_run=False):
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    run=uuid.uuid4().hex if new_run else digest
    rows=[]
    for index,line in enumerate(data.decode('utf-8-sig').splitlines()):
        if not line.strip():continue
        try:
            raw=json.loads(line)
            if not isinstance(raw,dict) or 'error' in raw:raise ValueError('Falha de sensor')
            rows.append((index,raw))
        except ValueError:print(f'Linha {index+1} inválida ou com falha; descartada.')
    uptimes=[r.get('uptime_ms') for _,r in rows]
    if not rows:return
    if any(not isinstance(x,int) or x<0 for x in uptimes):
        raise ValueError('O replay exige uptime_ms em todas as linhas. Copie a saída completa do sketch.')
    if any(b<=a for a,b in zip(uptimes,uptimes[1:])):
        raise ValueError('uptime_ms deve crescer; não misture sessões reiniciadas no mesmo arquivo.')
    anchor=datetime.now(timezone.utc)
    for (index,raw),uptime in zip(rows,uptimes):
        # Keep the virtual interval. The final sample is anchored at the replay start.
        measured=anchor-timedelta(milliseconds=uptimes[-1]-uptime)
        yield raw,measured,f'replay:{run}:{index}'


def main():
    parser=argparse.ArgumentParser()
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--file',type=Path);source.add_argument('--port')
    parser.add_argument('--api',default='http://localhost:8080')
    parser.add_argument('--rain-mm',type=float,required=True)
    parser.add_argument('--new-run',action='store_true',help='Novo exercício explícito com o mesmo arquivo')
    args=parser.parse_args();key=os.environ.get('DEVICE_API_KEY')
    if not key:parser.error('Configure DEVICE_API_KEY no ambiente local')
    def send(client,raw,measured,event_id,simulated):
        try:
            body=payload(raw,simulated,args.rain_mm,measured,event_id)
            response=client.post(args.api.rstrip('/')+'/api/iot/readings',json=body,headers={'X-Device-Key':key})
            if response.is_error:
                print(f'Rejeitado ({response.status_code}): {response.json().get("detail","erro da API")}');return
            result=response.json()
            print(json.dumps({k:result[k] for k in ['id','analysis_id','receipt_id','simulated']}))
        except (ValueError,KeyError,httpx.HTTPError) as error:print('Leitura não enviada:',str(error))
    with httpx.Client(timeout=15) as client:
        if args.file:
            try:
                for raw,measured,event_id in file_events(args.file,args.new_run):
                    send(client,raw,measured,event_id,True);time.sleep(1.1)
            except (OSError,ValueError) as error:parser.error(str(error))
        else:
            import serial
            with serial.Serial(args.port,9600,timeout=5) as port:
                time.sleep(2);run=uuid.uuid4().hex
                while True:
                    try:
                        line=port.readline()
                        if not line:continue
                        raw=json.loads(line)
                        send(client,raw,datetime.now(timezone.utc),f'usb:{run}:{raw.get("uptime_ms")}',False)
                    except (ValueError,KeyError):print('Saída serial inválida; descartada.')
                    except KeyboardInterrupt:break


if __name__=='__main__':main()

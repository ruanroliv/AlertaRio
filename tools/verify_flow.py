"""Reproducible local benchmark of analysis->inbox->ACK, isolated from application data."""
import argparse,json,os,sys,tempfile,time,statistics
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='output/evidence/flow.json');args=parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        os.environ.update(DATABASE_PATH=str(Path(directory)/'test.db'),LAKE_PATH=str(Path(directory)/'bronze'),APP_ENV='development',APP_ORIGIN='http://localhost:8080')
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.db import connect
        from backend.security import hash_password
        password='LocalBenchmark#2026'
        with connect() as db:
            hashed=hash_password(password)
            for email,role in [('manager@example.invalid','manager'),('resident@example.invalid','resident')]:
                db.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(email,hashed,role))
        manager=TestClient(app,base_url='http://localhost:8080');resident=TestClient(app,base_url='http://localhost:8080')
        def login(client,email):
            result=client.post('/api/auth/login',json={'email':email,'password':password});assert result.status_code==200,result.text
            return {'X-CSRF-Token':result.json()['csrf_token']}
        mh=login(manager,'manager@example.invalid');rh=login(resident,'resident@example.invalid')
        measurements=[]
        for i in range(20):
            water,soil,expected=(55,35,'Normal') if i%2==0 else (180,90,'Alto')
            begin=time.perf_counter()
            response=manager.post('/api/readings/simulate',headers=mh,json={'sensor_id':'AR-001','water_level_cm':water,
                'soil_moisture_pct':soil,'rainfall_mm':0,'measured_at':datetime.now(timezone.utc).isoformat(),'simulated':True})
            assert response.status_code==200,response.text
            reading=response.json();inbox=resident.get('/api/state').json();alert=inbox['alerts'][0]
            milliseconds=(time.perf_counter()-begin)*1000
            assert alert['analysis_id']==reading['analysis_id'] and alert['risk']==expected
            ack=resident.post(f"/api/alerts/{alert['id']}/ack",json={},headers=rh);assert ack.status_code==200
            measurements.append({'scenario':i+1,'water_cm':water,'soil_pct':soil,'expected':expected,'actual':alert['risk'],
                'analysis_id':reading['analysis_id'],'alert_id':alert['id'],'availability_ms':round(milliseconds,3),'ack_status':ack.status_code})
        result={'executed_at':datetime.now(timezone.utc).isoformat(),'environment':sys.version.split()[0],
          'scenarios':len(measurements),'successful':len(measurements),
          'median_backend_availability_ms':round(statistics.median(m['availability_ms'] for m in measurements),3),
          'p95_backend_availability_ms':round(sorted(m['availability_ms'] for m in measurements)[18],3),
          'ui_poll_interval_seconds':5,
          'design_comparison':{'scope':'Aviso em página já aberta após ingestão; comparação de passos, não estudo de tempo humano',
             'before_manual_actions':2,'before':['Recarregar painel','Clicar em simular recebimento'],
             'after_manual_actions':0,'basis':'Código anterior 30652cf e fluxo atual; confirmação de leitura não contada'},
          'limitations':['Ambiente local de teste, não inclui navegador ou rede externa na latência medida',
             'Roteiro sintético; aderência ao roteiro não é acurácia de previsão de desastre',
             'Nenhum SMS/WhatsApp ou consulta paga efetuada'], 'measurements':measurements,'monitoring':manager.get('/api/monitoring').json()}
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='measurements'},ensure_ascii=False,indent=2))
        manager.close();resident.close()


if __name__=='__main__':main()

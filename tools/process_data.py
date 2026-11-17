"""Materialize Silver CSV and Gold JSON from the authoritative database. No PII exported."""
import argparse,csv,json,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.db import ROOT,init_db
from backend.analytics import rows_for,dashboard


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--community');parser.add_argument('--start');parser.add_argument('--end')
    parser.add_argument('--origin',default='all',choices=['all','simulated','device'])
    args=parser.parse_args();init_db()
    lake=Path(os.environ.get('DATA_LAKE_ROOT',str(ROOT/'data/lake')))
    silver=lake/'silver';gold=lake/'gold';silver.mkdir(parents=True,exist_ok=True);gold.mkdir(parents=True,exist_ok=True)
    rows=rows_for(args.community,args.start,args.end,args.origin)
    fields=['id','sensor_id','measured_at','received_at','water','soil','rain','simulated','source','receipt_id']
    with (silver/'readings.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(fields+['analysis_id','risk'])
        for row in rows:writer.writerow([row[k] for k in fields]+[row['analysis']['analysis_id'],row['analysis']['label']])
    result=dashboard(args.community,args.start,args.end,args.origin)
    (gold/'indicators.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'silver':str(silver/'readings.csv'),'gold':str(gold/'indicators.json'),'readings':len(rows)},ensure_ascii=False))


if __name__=='__main__':main()

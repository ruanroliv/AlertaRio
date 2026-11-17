"""Silver query and Gold aggregates. All series, cards and exports share one filter."""
from datetime import datetime, timezone
import json
from .db import connect
from .engine import get_analysis


def normalized_time(value):
    moment=datetime.fromisoformat(value.replace('Z','+00:00'))
    if moment.tzinfo is None:
        raise ValueError('Horário deve conter fuso')
    return moment.astimezone(timezone.utc).isoformat()


def rows_for(community=None, start=None, end=None, origin='all'):
    clauses=[];values=[]
    if community:clauses.append('r.sensor_id=?');values.append(community)
    if start:clauses.append('julianday(r.measured_at)>=julianday(?)');values.append(normalized_time(start))
    if end:clauses.append('julianday(r.measured_at)<=julianday(?)');values.append(normalized_time(end))
    if origin in ('simulated','device'):
        clauses.append('r.simulated=?');values.append(1 if origin=='simulated' else 0)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    with connect() as db:
        rows=[]
        for raw in db.execute('''SELECT r.*,d.name,a.id AS selected_analysis_id,a.result AS analysis_result,a.created_at AS analysis_at
            FROM readings r JOIN devices d ON d.id=r.sensor_id LEFT JOIN analyses a ON a.id=(SELECT MAX(a2.id) FROM analyses a2 WHERE a2.reading_id=r.id)'''+where+
                              ' ORDER BY julianday(r.measured_at),r.id',values):
            row=dict(raw);row['measured_at']=normalized_time(row['measured_at'])
            row['analysis']=({**json.loads(row['analysis_result']),'analysis_id':row['selected_analysis_id'],'analyzed_at':row['analysis_at']} if row['analysis_result'] else get_analysis(db,row));rows.append(row)
    return rows


def dashboard(community=None,start=None,end=None,origin='all'):
    rows=rows_for(community,start,end,origin)
    groups={};hourly={}
    for row in rows:
        groups.setdefault(row['sensor_id'],[]).append(row)
        key=row['measured_at'][:13]
        hourly.setdefault(key,[]).append(row)
    series=[]
    for sensor_id,readings in groups.items():
        first,last=readings[0],readings[-1]
        seconds=(datetime.fromisoformat(last['measured_at'])-datetime.fromisoformat(first['measured_at'])).total_seconds()
        slope=(last['water']-first['water'])/(seconds/60) if seconds>0 else None
        series.append({'sensor_id':sensor_id,'name':last['name'],'last_risk':last['analysis']['label'],
                       'max_water_cm':max(r['water'] for r in readings),'rise_cm_min':slope,
                       'samples':[{'id':r['id'],'measured_at':r['measured_at'],'received_at':r['received_at'],
                                   'water':r['water'],'soil':r['soil'],'simulated':bool(r['simulated'])}
                                  for r in readings]})
    count=len(rows)
    return {'filters':{'community':community,'start':start,'end':end,'origin':origin},
            'readings_count':count,'simulated_count':sum(r['simulated'] for r in rows),
            'avg_soil_pct':sum(r['soil'] for r in rows)/count if count else None,
            'max_water_cm':max((r['water'] for r in rows),default=None),
            'high_risk_points':sum(s['last_risk']=='Alto' for s in series),
            'max_rise_cm_min':max((s['rise_cm_min'] for s in series if s['rise_cm_min'] is not None),default=None),
            'points_with_data':len(series),'series':series,
            'hourly':[{'hour_utc':key,'samples':len(items),
                       'avg_water_cm':sum(r['water'] for r in items)/len(items),
                       'avg_soil_pct':sum(r['soil'] for r in items)/len(items)}
                      for key,items in sorted(hourly.items())],
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Última classificação e amostras dentro do recorte; não é previsão validada',
            'not_a_big_data_scale_claim':True}

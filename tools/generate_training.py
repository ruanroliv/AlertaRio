"""Reproducible synthetic examples, NOT observations of floods or landslides."""
import csv
import random
from pathlib import Path

random.seed(92)
target=Path(__file__).resolve().parent.parent/'data/training/risk_synthetic.csv'
with target.open('w',newline='',encoding='utf-8') as stream:
    writer=csv.writer(stream)
    writer.writerow(['water_cm','soil_pct','rain_mm','label','source'])
    for _ in range(300):
        water=random.randint(0,200)
        soil=random.randint(0,100)
        rain=random.randint(0,100)
        score=max(water/2,soil)+max(0,rain-20)*.25
        label='Alto' if score>=80 else 'Atenção' if score>=60 else 'Normal'
        writer.writerow([water,soil,rain,label,'synthetic-rule-generated'])
print('300 exemplos sintéticos reproduzidos com semente 92. Não são dados de campo.')

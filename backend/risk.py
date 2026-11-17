"""Educational k-nearest-neighbors model. Training data are synthetic, not field observations."""
import csv
import math
from pathlib import Path

LABELS = ['Normal', 'Atenção', 'Alto']


class RiskModel:
    def __init__(self, path=None):
        path = path or Path(__file__).resolve().parent.parent / 'data/training/risk_synthetic.csv'
        with open(path, encoding='utf-8') as file:
            self.rows = list(csv.DictReader(file))
        if len(self.rows) < 5:
            raise ValueError('Training dataset requires at least five samples')

    def predict(self, water, soil, rain, forecast=None):
        # Forecast is optional and is NEVER silently substituted with a real measurement.
        vector = [water / 200, soil / 100, rain / 100]
        nearest = sorted(self.rows, key=lambda row: sum(
            (a - float(row[key]) / scale) ** 2
            for a, key, scale in zip(vector, ['water_cm', 'soil_pct', 'rain_mm'], [200, 100, 100])
        ))[:5]
        votes = {label: sum(r['label'] == label for r in nearest) for label in LABELS}
        label = max(LABELS, key=lambda name: (votes[name], LABELS.index(name)))
        # A transparent floor prevents the toy model from downgrading extreme readings.
        floor = 'Alto' if water >= 160 or soil >= 85 else 'Atenção' if water >= 100 or soil >= 65 else 'Normal'
        if forecast is not None and forecast >= 30:
            floor = LABELS[min(2, LABELS.index(floor) + 1)]
        final = LABELS[max(LABELS.index(label), LABELS.index(floor))]
        return {
            'label': final, 'cls': {'Normal': 'green', 'Atenção': 'amber', 'Alto': 'red'}[final],
            'score': {'Normal': 25, 'Atenção': 60, 'Alto': 90}[final],
            'model_vote': label, 'votes': votes, 'neighbors': 5,
            'model': 'knn-synthetic-v1', 'training_source': 'synthetic',
            'forecast_next_3h_mm': forecast,
            'validated_for_emergencies': False,
            'explanation': f'Classificação experimental: {final}. Água {water:g} cm; solo {soil:g}%; chuva {rain:g} mm. Modelo kNN com dados sintéticos e limites didáticos.',
        }

"""Bronze receipt journal: raw authenticated telemetry and its processing outcome."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .db import ROOT


def record(payload, source, status, receipt_id=None, **outcome):
    stamp = datetime.now(timezone.utc).isoformat()
    receipt_id = receipt_id or uuid.uuid4().hex
    directory = Path(os.environ.get('LAKE_PATH', str(ROOT / 'data/lake/bronze')))
    directory.mkdir(parents=True, exist_ok=True)
    event = {'receipt_id': receipt_id, 'received_at': stamp, 'source': source,
             'status': status, 'raw_payload': payload, **outcome}
    with (directory / (stamp[:10] + '.jsonl')).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
    return receipt_id

"""Development entrypoint; accepts the preview runner's host/port arguments."""
import logging
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import uvicorn
parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=8080)
parser.add_argument('--strictPort', action='store_true')
args = parser.parse_args()
os.environ.setdefault('APP_ORIGIN', f'http://{args.host}:{args.port}')
logging.basicConfig(level=logging.WARNING)
uvicorn.run('backend.main:app', host=args.host, port=args.port, proxy_headers=False)

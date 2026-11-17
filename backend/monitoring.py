"""Small in-process service monitor; counters reset at process restart."""
from collections import deque
from threading import Lock
import statistics,time
_started=time.monotonic();_lock=Lock();_latencies=deque(maxlen=1000);_requests=0;_errors=0

def observe(status,elapsed_ms):
    global _requests,_errors
    with _lock:
        _requests+=1;_errors+=status>=500;_latencies.append(elapsed_ms)

def snapshot():
    with _lock:
        return {'uptime_seconds':round(time.monotonic()-_started,1),'requests_total':_requests,
                'server_errors_total':_errors,'median_request_ms':round(statistics.median(_latencies),3) if _latencies else None,
                'sampled_requests':len(_latencies),'scope':'Um processo; contadores reiniciam no restart'}

import hashlib,json
from urllib.parse import urlparse
from urllib.request import urlopen
BASE='http://127.0.0.1:8080'
def fetch_json(path):
    with urlopen(BASE+path,timeout=20) as r:return json.loads(r.read().decode())
def stable_id(prefix,*parts):
    return prefix+'-'+hashlib.sha256('|'.join(str(p or '') for p in parts).encode()).hexdigest()[:16]
def parse_endpoint(endpoint):
    p=urlparse(endpoint or '');return p.hostname or '',p.port

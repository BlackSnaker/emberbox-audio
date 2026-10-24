"""Cancellable local HTTP helper. Requests and auth stay in its private pipe."""
import json,sys,urllib.request
from urllib.parse import urlsplit


def request(value):
    url=str(value.get('url',''));parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.username or parsed.password:
        raise ValueError('Only local inference is supported')
    if parsed.path not in ('/api/chat','/v1/chat/completions'):raise ValueError('Unsupported inference endpoint')
    headers={'Content-Type':'application/json'}
    if value.get('token'):headers['Authorization']='Bearer '+str(value['token'])
    req=urllib.request.Request(url,data=json.dumps(value['data']).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=12) as response:raw=response.read(500001)
    if len(raw)>500000:raise ValueError('Model response too large')
    return json.loads(raw)


if __name__=='__main__':
    try:
        raw=sys.stdin.buffer.read(32001)
        if len(raw)>32000:raise ValueError('Request too large')
        print(json.dumps(request(json.loads(raw))),flush=True)
    except Exception:sys.exit(1)

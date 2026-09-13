import json
from urllib import request
BASE='https://north-star-uat-r4-production.up.railway.app'
payload=json.dumps({'question':'How should governance and risk be handled in enterprise technology decisions?','max_evidence':6}).encode()
req=request.Request(BASE+'/api/ai/ask',data=payload,method='POST',headers={'Content-Type':'application/json'})
with request.urlopen(req,timeout=30) as r:
    body=json.loads(r.read().decode())
    print('HTTP',r.status,'provider',body.get('provider'),'answer_class',body.get('answer_class'),'grounded',body.get('grounded'),'citations',len(body.get('citations',[])))
    assert r.status==200
    assert body.get('provider')=='LOCAL_EVIDENCE'
    assert body.get('grounded') is True

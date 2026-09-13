import json, time, uuid
from urllib import request, error
from http.cookiejar import CookieJar
BASE='https://north-star-uat-r4-production.up.railway.app'
jar=CookieJar(); opener=request.build_opener(request.HTTPCookieProcessor(jar))
def call(method,path,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=request.Request(BASE+path,data=data,method=method)
    if data is not None: req.add_header('Content-Type','application/json')
    try:
        with opener.open(req,timeout=30) as r: return r.status,r.read().decode()
    except error.HTTPError as e: return e.code,e.read().decode()

s,b=call('GET','/api/entitlements/me'); print('unauth_entitlements',s,b[:120]); assert s==401
email=f"uat-r4-{int(time.time())}-{uuid.uuid4().hex[:8]}@example.test"
s,b=call('POST','/api/auth/dev-login',{'email':email,'display_name':'R4 External UAT'})
j=json.loads(b); print('login',s,j.get('authenticated'),j.get('provider'),j.get('user_id')); assert s==200 and j.get('authenticated') is True
s,b=call('GET','/api/entitlements/me'); j=json.loads(b); e=j.get('effective',{}); print('pre_entitlement',s,e); assert s==200 and e.get('full_portal') is False

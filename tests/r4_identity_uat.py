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

key=f"r4-{int(time.time())}-{uuid.uuid4().hex[:8]}"
s,b=call('POST','/api/commerce/paypal/create-order',{'plan_code':'full','idempotency_key':key})
j=json.loads(b); oid=j.get('provider_order_id'); print('order',s,j.get('provider_runtime'),j.get('status'),oid); assert s==200 and j.get('provider_runtime')=='PAYPAL_SIMULATOR' and j.get('status')=='CREATED' and oid
s,b=call('POST','/api/commerce/paypal/dev-capture',{'provider_order_id':oid})
j=json.loads(b); e=j.get('effective_entitlements',{}); print('capture',s,j.get('provider_runtime'),j.get('status'),e.get('full_portal')); assert s==200 and j.get('status')=='COMPLETED' and e.get('full_portal') is True
s,b=call('GET','/api/entitlements/me'); j=json.loads(b); e=j.get('effective',{}); items=e.get('items',[]); match=[x for x in items if x.get('entitlement_type')=='full_portal' and x.get('status')=='active' and x.get('source_ref')==oid]; print('post_entitlement',s,e.get('full_portal'),len(match)); assert s==200 and e.get('full_portal') is True and match

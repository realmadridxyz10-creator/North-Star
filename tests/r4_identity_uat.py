import json, time, uuid
from urllib import request, error
from http.cookiejar import CookieJar

BASE='https://north-star-uat-r4-production.up.railway.app'

def client():
    jar=CookieJar()
    return jar,request.build_opener(request.HTTPCookieProcessor(jar))

def call(opener,method,path,payload=None,headers=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=request.Request(BASE+path,data=data,method=method,headers=headers or {})
    if data is not None: req.add_header('Content-Type','application/json')
    try:
        with opener.open(req,timeout=30) as r: return r.status,r.read().decode(),dict(r.headers)
    except error.HTTPError as e: return e.code,e.read().decode(),dict(e.headers)

def login(opener,label):
    email=f"uat-r4-{label}-{int(time.time())}-{uuid.uuid4().hex[:8]}@example.test"
    s,b,h=call(opener,'POST','/api/auth/dev-login',{'email':email,'display_name':f'R4 {label}'})
    j=json.loads(b); print('login',label,s,j.get('authenticated'),j.get('provider'))
    assert s==200 and j.get('authenticated') is True
    return j

# Unauthenticated and malformed-session boundaries.
_,anon=client()
s,b,h=call(anon,'GET','/api/entitlements/me'); print('unauth_entitlements',s); assert s==401
req=request.Request(BASE+'/api/entitlements/me',method='GET',headers={'Cookie':'ns_session=malformed.invalid'})
try:
    anon.open(req,timeout=30); raise AssertionError('malformed session unexpectedly authorized')
except error.HTTPError as e:
    print('malformed_session',e.code); assert e.code==401

# User A login; cookie must be hardened on external HTTPS UAT.
jar_a,a=client(); user_a=login(a,'User-A')
cookies=list(jar_a)
assert cookies, 'session cookie missing'
session=[c for c in cookies if c.name=='ns_session']
assert session, 'ns_session cookie missing'
assert session[0].secure is True
print('cookie_secure',session[0].secure)

s,b,h=call(a,'GET','/api/entitlements/me'); e=json.loads(b).get('effective',{}); assert s==200 and e.get('full_portal') is False

# Invalid plan must fail without granting access.
s,b,h=call(a,'POST','/api/commerce/paypal/create-order',{'plan_code':'invalid','idempotency_key':'invalid-'+uuid.uuid4().hex})
print('invalid_plan',s); assert s==400

# Create order alone must not grant entitlement.
key='r4-sec-'+uuid.uuid4().hex
a_s,a_b,a_h=call(a,'POST','/api/commerce/paypal/create-order',{'plan_code':'full','idempotency_key':key})
a_order=json.loads(a_b); oid=a_order.get('provider_order_id')
print('order_created',a_s,a_order.get('status'),oid); assert a_s==200 and a_order.get('status')=='CREATED' and oid
s,b,h=call(a,'GET','/api/entitlements/me'); assert json.loads(b).get('effective',{}).get('full_portal') is False

# User B must not be able to capture User A's order.
jar_b,bop=client(); login(bop,'User-B')
s,b,h=call(bop,'POST','/api/commerce/paypal/dev-capture',{'provider_order_id':oid})
print('wrong_user_capture',s); assert s in (403,404)
s,b,h=call(bop,'GET','/api/entitlements/me'); assert json.loads(b).get('effective',{}).get('full_portal') is False

# Nonexistent capture is controlled denial.
s,b,h=call(a,'POST','/api/commerce/paypal/dev-capture',{'provider_order_id':'NONEXISTENT-'+uuid.uuid4().hex})
print('nonexistent_capture',s); assert s==404

# Owner capture grants entitlement; duplicate capture remains idempotent.
s,b,h=call(a,'POST','/api/commerce/paypal/dev-capture',{'provider_order_id':oid})
j=json.loads(b); e=j.get('effective_entitlements',{})
print('owner_capture',s,j.get('status'),e.get('full_portal')); assert s==200 and j.get('status')=='COMPLETED' and e.get('full_portal') is True
s,b,h=call(a,'POST','/api/commerce/paypal/dev-capture',{'provider_order_id':oid})
j2=json.loads(b); print('duplicate_capture',s,j2.get('status')); assert s==200 and j2.get('status')=='COMPLETED'

# Entitlement remains user-scoped.
s,b,h=call(a,'GET','/api/entitlements/me'); ea=json.loads(b).get('effective',{}); assert ea.get('full_portal') is True
s,b,h=call(bop,'GET','/api/entitlements/me'); eb=json.loads(b).get('effective',{}); assert eb.get('full_portal') is False

# Logout invalidates browser session access.
s,b,h=call(a,'POST','/api/auth/logout'); print('logout',s); assert s==200
s,b,h=call(a,'GET','/api/entitlements/me'); print('post_logout',s); assert s==401

print('R4 identity/commerce defensive UAT PASS')

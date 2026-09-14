import json
from urllib import request, error

BASE = "https://north-star-uat-r4-production.up.railway.app"
checks = [
    ("Health", "/api/health"),
    ("Portal", "/"),
    ("Search", "/api/search?q=governance"),
    ("Compass", "/api/compass?dimension=BUILD"),
    ("Assistant", "/assistant"),
    ("Account", "/account"),
    ("Auth Status", "/api/auth/status"),
    ("Plans", "/api/commerce/plans"),
    ("PayPal Status", "/api/commerce/paypal/status"),
    ("Entitlements Boundary", "/api/entitlements/me"),
]

failed = []
health_headers = {}
for name, path in checks:
    req = request.Request(BASE + path, method="GET")
    try:
        with request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
            headers = dict(r.headers)
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
        headers = dict(e.headers)
    if name == "Health": health_headers = {k.lower():v for k,v in headers.items()}
    ok = status == 200
    if name == "Entitlements Boundary":
        ok = status == 401 and "authentication_required" in body
    evidence = f"HTTP {status}"
    try:
        j = json.loads(body)
        if name == "Health":
            evidence += f" status={j.get('status')} release={j.get('release')} search_records={j.get('search_records')} retrieval_chunks={j.get('retrieval_chunks')} production_authorized={j.get('production_authorized')}"
        elif name == "Search":
            evidence += f" count={j.get('count')}"
        elif name == "Compass":
            evidence += f" nodes={len(j.get('nodes', []))} edges={len(j.get('edges', []))}"
        elif name == "Auth Status":
            evidence += f" provider={j.get('provider')} authenticated={j.get('authenticated')}"
        elif name == "PayPal Status":
            evidence += f" runtime={j.get('runtime')} sandbox_connected={j.get('sandbox_connected')}"
    except Exception:
        evidence += f" bytes={len(body)}"
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {evidence}")
    if not ok: failed.append(name)

# Hardened response-header assurance.
required_headers = {
    'strict-transport-security': 'max-age=',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'strict-origin-when-cross-origin',
    'permissions-policy': 'camera=()',
    'cross-origin-opener-policy': 'same-origin',
    'cross-origin-resource-policy': 'same-origin',
    'x-permitted-cross-domain-policies': 'none',
}
for key,expected in required_headers.items():
    val=health_headers.get(key,'')
    ok=expected.lower() in val.lower()
    print(f"[{'PASS' if ok else 'FAIL'}] Header {key}: {val}")
    if not ok: failed.append('header:'+key)

csp=health_headers.get('content-security-policy','')
csp_requirements=["object-src 'none'","connect-src 'self'","frame-ancestors 'none'","base-uri 'self'","upgrade-insecure-requests"]
for directive in csp_requirements:
    ok=directive.lower() in csp.lower()
    print(f"[{'PASS' if ok else 'FAIL'}] CSP {directive}")
    if not ok: failed.append('csp:'+directive)

# Controlled error handling / method and parameter validation.
def status_for(req):
    try:
        with request.urlopen(req,timeout=30) as r: return r.status,r.read().decode('utf-8','replace')
    except error.HTTPError as e: return e.code,e.read().decode('utf-8','replace')

cases=[]
cases.append(('Unknown Dimension',request.Request(BASE+'/api/compass?dimension=NOT_A_DIMENSION',method='GET'),400))
cases.append(('Search Limit Validation',request.Request(BASE+'/api/search?q=governance&limit=101',method='GET'),422))
cases.append(('Method Misuse',request.Request(BASE+'/api/health',data=b'{}',method='POST',headers={'Content-Type':'application/json'}),405))
cases.append(('Malformed JSON',request.Request(BASE+'/api/ai/ask',data=b'{bad-json',method='POST',headers={'Content-Type':'application/json'}),422))
for name,req,expected in cases:
    status,body=status_for(req)
    ok=status==expected
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: HTTP {status} expected={expected}")
    if not ok: failed.append(name)

print('R4 HTTP/security boundary UAT', 'PASS' if not failed else f'FAIL {failed}')
raise SystemExit(1 if failed else 0)

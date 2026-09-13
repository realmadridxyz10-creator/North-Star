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
for name, path in checks:
    req = request.Request(BASE + path, method="GET")
    try:
        with request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    ok = status == 200
    if name == "Entitlements Boundary":
        ok = status == 401 and "authentication_required" in body
    evidence = f"HTTP {status}"
    try:
        j = json.loads(body)
        if name == "Health":
            evidence += f" status={j.get('status')} release={j.get('release')} search_records={j.get('search_records')} retrieval_chunks={j.get('retrieval_chunks')}"
        elif name == "Search":
            evidence += f" count={j.get('count')}"
        elif name == "Compass":
            evidence += f" dimension={j.get('dimension')} nodes={len(j.get('nodes', []))} edges={len(j.get('edges', []))}"
        elif name == "Auth Status":
            evidence += f" provider={j.get('provider')} authenticated={j.get('authenticated')}"
        elif name == "PayPal Status":
            evidence += f" runtime={j.get('runtime')} sandbox_connected={j.get('sandbox_connected')}"
    except Exception:
        evidence += f" bytes={len(body)}"
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {evidence}")
    if not ok:
        failed.append(name)

raise SystemExit(1 if failed else 0)

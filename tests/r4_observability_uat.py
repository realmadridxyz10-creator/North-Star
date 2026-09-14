import json
from urllib import request

BASE = "https://north-star-uat-r4-production.up.railway.app"

with request.urlopen(BASE + "/api/observability/status", timeout=30) as r:
    body = json.loads(r.read().decode("utf-8"))
    headers = {k.lower(): v for k, v in r.headers.items()}

assert body.get("status") == "ok"
assert body.get("runtime_overlay") == "R4_HARDENED_OBSERVABILITY"
assert body.get("production_authorized") is False
controls = body.get("controls", {})
assert controls.get("request_id") is True
assert controls.get("server_timing") is True
assert controls.get("structured_request_log") is True
assert controls.get("railway_resource_metrics") is True
assert controls.get("railway_deploy_logs") is True
assert controls.get("alert_delivery_proven") is False
assert headers.get("x-request-id")
assert "app;dur=" in headers.get("server-timing", "")
assert headers.get("x-north-star-release") == "NS-DP-MVP-RUNTIME-DEV-006"

print("R4 observability UAT PASS")
print(json.dumps({"status": body.get("status"), "runtime_overlay": body.get("runtime_overlay"), "controls": controls}, sort_keys=True))

from __future__ import annotations

import json
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app import main as baseline
from app.hardened import app as hardened_app
from app.paypal_sandbox_client import PayPalSandboxClient, PayPalSandboxConfig, PayPalSandboxError, sandbox_status


app = FastAPI(title="North Star R4 PayPal Sandbox UAT", version=baseline.RELEASE)


class SandboxCreateOrderRequest(BaseModel):
    plan_code: str
    idempotency_key: str = Field(min_length=8, max_length=120)


class SandboxCaptureRequest(BaseModel):
    provider_order_id: str
    idempotency_key: str = Field(min_length=8, max_length=120)


def _client() -> PayPalSandboxClient:
    cfg = PayPalSandboxConfig.from_env()
    if not cfg:
        raise HTTPException(503, "paypal_sandbox_credentials_not_configured")
    return PayPalSandboxClient(cfg)


def _approval_url(order: dict) -> str | None:
    for link in order.get("links", []) or []:
        if link.get("rel") in ("payer-action", "approve"):
            return link.get("href")
    return None


@app.get("/api/commerce/paypal/sandbox/status")
def paypal_sandbox_status():
    s = sandbox_status()
    s.update({
        "live_connected": False,
        "sandbox_connected": bool(s["sandbox_credentials_configured"]),
        "webhook_verified": False,
        "authority_rule": "Entitlement is granted only after server-side COMPLETED capture evidence or a verified PayPal webhook.",
    })
    return s


@app.post("/api/commerce/paypal/sandbox/create-order")
def paypal_sandbox_create_order(req: SandboxCreateOrderRequest, request: Request):
    user = baseline.require_user(request)
    if req.plan_code not in baseline.PLANS or req.plan_code == "preview":
        raise HTTPException(400, "invalid_paid_plan")

    c = baseline.db()
    existing = c.execute("SELECT * FROM orders WHERE idempotency_key=?", (req.idempotency_key,)).fetchone()
    if existing:
        c.close()
        return {"idempotent": True, "order": dict(existing), "provider_runtime": "PAYPAL_SANDBOX"}
    c.close()

    plan = baseline.PLANS[req.plan_code]
    try:
        order = _client().create_order(
            amount=plan["price"],
            currency=plan["currency"],
            request_id=req.idempotency_key,
            description=f"North Star {plan['name']}",
        )
    except PayPalSandboxError as exc:
        baseline.audit("commerce.paypal_sandbox_create_failed", {"status": exc.status, "message": str(exc)}, user["user_id"])
        raise HTTPException(502, "paypal_sandbox_create_failed") from exc

    provider_order_id = order.get("id")
    if not provider_order_id:
        raise HTTPException(502, "paypal_sandbox_missing_order_id")

    now = int(time.time())
    internal_order_id = "NSO-" + uuid.uuid4().hex[:14].upper()
    c = baseline.db()
    c.execute(
        "INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            internal_order_id,
            user["user_id"],
            "PAYPAL_SANDBOX",
            provider_order_id,
            req.plan_code,
            plan["price"],
            plan["currency"],
            order.get("status") or "CREATED",
            req.idempotency_key,
            now,
            None,
        ),
    )
    c.commit()
    c.close()
    baseline.audit("commerce.paypal_sandbox_order_created", {"provider_order_id": provider_order_id, "plan": req.plan_code}, user["user_id"])
    return {
        "idempotent": False,
        "provider": "PayPal",
        "provider_runtime": "PAYPAL_SANDBOX",
        "provider_order_id": provider_order_id,
        "status": order.get("status"),
        "plan": req.plan_code,
        "amount": plan["price"],
        "currency": plan["currency"],
        "approval_url": _approval_url(order),
        "production_authorized": False,
    }


@app.post("/api/commerce/paypal/sandbox/capture")
def paypal_sandbox_capture(req: SandboxCaptureRequest, request: Request):
    user = baseline.require_user(request)
    c = baseline.db()
    row = c.execute("SELECT * FROM orders WHERE provider_order_id=?", (req.provider_order_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "order_not_found")
    if row["user_id"] != user["user_id"]:
        c.close()
        raise HTTPException(403, "order_owner_mismatch")
    if row["status"] == "COMPLETED":
        c.close()
        return {
            "idempotent": True,
            "provider_order_id": req.provider_order_id,
            "status": "COMPLETED",
            "effective_entitlements": baseline.effective_entitlements(user["user_id"]),
        }
    c.close()

    try:
        capture = _client().capture_order(req.provider_order_id, req.idempotency_key)
    except PayPalSandboxError as exc:
        baseline.audit("commerce.paypal_sandbox_capture_failed", {"provider_order_id": req.provider_order_id, "status": exc.status, "message": str(exc)}, user["user_id"])
        raise HTTPException(502, "paypal_sandbox_capture_failed") from exc

    status = capture.get("status")
    if status != "COMPLETED":
        baseline.audit("commerce.paypal_sandbox_capture_not_completed", {"provider_order_id": req.provider_order_id, "status": status}, user["user_id"])
        return {"provider_order_id": req.provider_order_id, "status": status, "entitlement_granted": False}

    now = int(time.time())
    c = baseline.db()
    c.execute("UPDATE orders SET status='COMPLETED',captured_at=? WHERE provider_order_id=?", (now, req.provider_order_id))
    c.commit()
    plan_code = row["plan_code"]
    c.close()
    baseline.grant_entitlement(user["user_id"], plan_code, req.provider_order_id)
    baseline.audit("commerce.paypal_sandbox_payment_completed", {"provider_order_id": req.provider_order_id, "plan": plan_code}, user["user_id"])
    return {
        "idempotent": False,
        "provider": "PayPal",
        "provider_runtime": "PAYPAL_SANDBOX",
        "provider_order_id": req.provider_order_id,
        "status": "COMPLETED",
        "entitlement_granted": True,
        "effective_entitlements": baseline.effective_entitlements(user["user_id"]),
        "production_authorized": False,
    }


@app.post("/api/commerce/paypal/sandbox/webhook")
async def paypal_sandbox_webhook(request: Request):
    raw = await request.body()
    try:
        event = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, "invalid_json") from exc
    try:
        verified = _client().verify_webhook(headers=dict(request.headers), event=event)
    except PayPalSandboxError as exc:
        raise HTTPException(400, "paypal_webhook_verification_failed") from exc
    if not verified:
        raise HTTPException(400, "paypal_webhook_not_verified")
    baseline.audit("commerce.paypal_sandbox_webhook_verified", {"event_id": event.get("id"), "event_type": event.get("event_type")})
    return {"received": True, "verified": True, "event_id": event.get("id"), "event_type": event.get("event_type")}


@app.middleware("http")
async def r4_wrapper_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("Server-Timing", f"app;dur={duration_ms}")
    response.headers.setdefault("X-North-Star-Release", baseline.RELEASE)
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


# Preserve all existing R4 hardened routes as the fallback/default application.
app.mount("/", hardened_app)

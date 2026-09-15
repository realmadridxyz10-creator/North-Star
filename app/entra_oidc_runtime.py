from __future__ import annotations

import json
import os
import time

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app import main as baseline
from app.hardened import app
from app.entra_oidc import (
    EntraOIDCClient,
    EntraOIDCConfig,
    EntraOIDCConfigurationError,
    managed_oidc_status,
)

MANAGED_IDENTITY_PROVIDER = "MICROSOFT_ENTRA_EXTERNAL_ID"
OIDC_FLOW_COOKIE = "ns_oidc_flow"
OIDC_FLOW_MAX_AGE = 600


def _config() -> EntraOIDCConfig:
    try:
        cfg = EntraOIDCConfig.from_env()
    except EntraOIDCConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    if cfg is None:
        raise HTTPException(503, "entra_oidc_not_configured")
    return cfg


def _flow_secret() -> str:
    # Use a dedicated secret when configured; otherwise reuse the existing
    # North Star server-side session secret for UAT flow-state protection.
    return os.environ.get("ENTRA_FLOW_SECRET", "").strip() or baseline.SESSION_SECRET


def _sign_flow(flow: dict) -> str:
    payload = {
        "flow": flow,
        "iat": int(time.time()),
        "exp": int(time.time()) + OIDC_FLOW_MAX_AGE,
        "purpose": "entra_oidc_auth_code_flow",
    }
    original = baseline.SESSION_SECRET
    try:
        baseline.SESSION_SECRET = _flow_secret()
        return baseline.sign_session(payload)
    finally:
        baseline.SESSION_SECRET = original


def _read_flow(token: str | None) -> dict:
    if not token:
        raise HTTPException(400, "entra_oidc_flow_missing")
    original = baseline.SESSION_SECRET
    try:
        baseline.SESSION_SECRET = _flow_secret()
        payload = baseline.read_session(token)
    finally:
        baseline.SESSION_SECRET = original
    if not payload or payload.get("purpose") != "entra_oidc_auth_code_flow":
        raise HTTPException(400, "entra_oidc_flow_invalid_or_expired")
    flow = payload.get("flow")
    if not isinstance(flow, dict):
        raise HTTPException(400, "entra_oidc_flow_invalid")
    return flow


def _upsert_managed_user(identity: dict) -> dict:
    subject = str(identity.get("subject") or "").strip()
    email = str(identity.get("email") or "").strip().lower()
    display_name = str(identity.get("display_name") or "North Star Reader").strip()
    tenant_id = str(identity.get("tenant_id") or "").strip()
    if not subject:
        raise HTTPException(401, "entra_oidc_subject_missing")
    if not email:
        raise HTTPException(401, "entra_oidc_email_missing")

    # Stable North Star identity key is derived from the managed IdP subject,
    # not from browser input. Email is retained as an account attribute.
    import hashlib
    stable = f"{tenant_id}:{subject}" if tenant_id else subject
    user_id = "usr_entra_" + hashlib.sha256(stable.encode()).hexdigest()[:20]
    now = int(time.time())

    c = baseline.db()
    existing_subject = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    existing_email = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if existing_subject:
        c.execute(
            "UPDATE users SET email=?,display_name=?,provider=? WHERE user_id=?",
            (email, display_name, MANAGED_IDENTITY_PROVIDER, user_id),
        )
    elif existing_email:
        # Preserve the existing North Star user_id so any existing server-side
        # entitlements remain bound to the same account after managed sign-in.
        user_id = existing_email["user_id"]
        c.execute(
            "UPDATE users SET display_name=?,provider=? WHERE user_id=?",
            (display_name, MANAGED_IDENTITY_PROVIDER, user_id),
        )
    else:
        c.execute(
            "INSERT INTO users VALUES(?,?,?,?,?)",
            (user_id, email, display_name, MANAGED_IDENTITY_PROVIDER, now),
        )
    c.commit()
    row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return dict(row)


@app.get("/api/auth/entra/status")
def entra_status():
    status = managed_oidc_status()
    status["fallback_provider"] = baseline.IDENTITY_PROVIDER
    status["entitlement_authority"] = "SERVER_SIDE_ENTITLEMENT_DB"
    status["production_authorized"] = False
    return status


@app.get("/api/auth/entra/login")
def entra_login():
    cfg = _config()
    flow = EntraOIDCClient(cfg).begin_login()
    auth_uri = flow.get("auth_uri")
    if not auth_uri:
        raise HTTPException(503, "entra_oidc_authorization_uri_missing")
    response = RedirectResponse(auth_uri, status_code=302)
    response.set_cookie(
        OIDC_FLOW_COOKIE,
        _sign_flow(flow),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=OIDC_FLOW_MAX_AGE,
        path="/",
    )
    return response


@app.get("/api/auth/entra/callback")
def entra_callback(request: Request):
    cfg = _config()
    flow = _read_flow(request.cookies.get(OIDC_FLOW_COOKIE))
    auth_response = {k: v for k, v in request.query_params.items()}
    try:
        identity = EntraOIDCClient(cfg).complete_login(flow, auth_response)
    except (RuntimeError, ValueError) as exc:
        baseline.audit("identity.entra_login_failed", {"error": str(exc)[:500]})
        raise HTTPException(401, "entra_oidc_authentication_failed") from exc

    user = _upsert_managed_user(identity)
    now = int(time.time())
    token = baseline.sign_session(
        {
            "sub": user["user_id"],
            "email": user["email"],
            "iat": now,
            "exp": now + 28800,
            "provider": MANAGED_IDENTITY_PROVIDER,
        }
    )
    baseline.audit(
        "identity.entra_login",
        {"provider": MANAGED_IDENTITY_PROVIDER, "managed_external_idp": True},
        user["user_id"],
    )
    response = RedirectResponse("/account", status_code=302)
    response.set_cookie(
        baseline.SESSION_COOKIE,
        token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=28800,
        path="/",
    )
    response.delete_cookie(OIDC_FLOW_COOKIE, path="/")
    return response


@app.post("/api/auth/entra/logout")
def entra_logout():
    # Local North Star session invalidation is immediate. Federated Entra
    # logout/session behavior is a separate Stage 5.3 UAT verification gate.
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(baseline.SESSION_COOKIE, path="/")
    response.delete_cookie(OIDC_FLOW_COOKIE, path="/")
    return response


@app.get("/api/auth/managed-status")
def managed_auth_status(request: Request):
    user = baseline.current_user(request)
    return {
        "managed_provider": MANAGED_IDENTITY_PROVIDER,
        "managed_configuration": managed_oidc_status(),
        "fallback_provider": baseline.IDENTITY_PROVIDER,
        "authenticated": bool(user),
        "user": user,
        "entitlement_authority": "SERVER_SIDE_ENTITLEMENT_DB",
        "production_authorized": False,
    }

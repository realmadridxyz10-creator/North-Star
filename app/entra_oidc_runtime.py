from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

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
SESSION_MAX_AGE = 28800
MANAGED_SESSION_PREFIX = "m1"


def _config() -> EntraOIDCConfig:
    try:
        cfg = EntraOIDCConfig.from_env()
    except EntraOIDCConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    if cfg is None:
        raise HTTPException(503, "entra_oidc_not_configured")
    return cfg


def _flow_secret() -> str:
    return os.environ.get("ENTRA_FLOW_SECRET", "").strip() or baseline.SESSION_SECRET


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sign_value(value: str, secret: str) -> str:
    sig = _b64u(hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest())
    return f"{value}.{sig}"


def _verify_value(token: str | None, secret: str) -> str | None:
    if not token:
        return None
    try:
        value, sig = token.rsplit(".", 1)
        expected = _b64u(hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest())
        return value if hmac.compare_digest(sig, expected) else None
    except Exception:
        return None


def _sign_flow(flow: dict) -> str:
    payload = {
        "flow": flow,
        "iat": int(time.time()),
        "exp": int(time.time()) + OIDC_FLOW_MAX_AGE,
        "purpose": "entra_oidc_auth_code_flow",
    }
    body = _b64u(json.dumps(payload, separators=(",", ":")).encode())
    return _sign_value(body, _flow_secret())


def _read_flow(token: str | None) -> dict:
    body = _verify_value(token, _flow_secret())
    if not body:
        raise HTTPException(400, "entra_oidc_flow_invalid_or_expired")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception as exc:
        raise HTTPException(400, "entra_oidc_flow_invalid") from exc
    now = int(time.time())
    if payload.get("purpose") != "entra_oidc_auth_code_flow" or payload.get("exp", 0) < now:
        raise HTTPException(400, "entra_oidc_flow_invalid_or_expired")
    flow = payload.get("flow")
    if not isinstance(flow, dict):
        raise HTTPException(400, "entra_oidc_flow_invalid")
    return flow


def _init_managed_sessions() -> None:
    c = baseline.db()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS managed_sessions(
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_managed_sessions_user ON managed_sessions(user_id)")
    c.commit()
    c.close()


_init_managed_sessions()
_ORIGINAL_CURRENT_USER = baseline.current_user


def _managed_session_cookie(session_id: str) -> str:
    signed = _sign_value(session_id, baseline.SESSION_SECRET)
    return f"{MANAGED_SESSION_PREFIX}.{signed}"


def _managed_session_id(token: str | None) -> str | None:
    if not token or not token.startswith(MANAGED_SESSION_PREFIX + "."):
        return None
    return _verify_value(token[len(MANAGED_SESSION_PREFIX) + 1 :], baseline.SESSION_SECRET)


def _create_managed_session(user_id: str) -> str:
    now = int(time.time())
    session_id = secrets.token_urlsafe(32)
    c = baseline.db()
    c.execute(
        "INSERT INTO managed_sessions(session_id,user_id,provider,created_at,expires_at,revoked_at) VALUES(?,?,?,?,?,NULL)",
        (session_id, user_id, MANAGED_IDENTITY_PROVIDER, now, now + SESSION_MAX_AGE),
    )
    c.commit()
    c.close()
    return _managed_session_cookie(session_id)


def _managed_user_from_request(request: Request):
    session_id = _managed_session_id(request.cookies.get(baseline.SESSION_COOKIE))
    if not session_id:
        return None
    now = int(time.time())
    c = baseline.db()
    row = c.execute(
        "SELECT user_id FROM managed_sessions WHERE session_id=? AND revoked_at IS NULL AND expires_at>?",
        (session_id, now),
    ).fetchone()
    if not row:
        c.close()
        return None
    user = c.execute("SELECT * FROM users WHERE user_id=?", (row["user_id"],)).fetchone()
    c.close()
    return dict(user) if user else None


def _current_user(request: Request):
    token = request.cookies.get(baseline.SESSION_COOKIE)
    if token and token.startswith(MANAGED_SESSION_PREFIX + "."):
        return _managed_user_from_request(request)
    return _ORIGINAL_CURRENT_USER(request)


# Make all baseline entitlement/commerce authorization use the revocation-aware resolver.
baseline.current_user = _current_user


def _revoke_request_session(request: Request) -> bool:
    session_id = _managed_session_id(request.cookies.get(baseline.SESSION_COOKIE))
    if not session_id:
        return False
    c = baseline.db()
    cur = c.execute(
        "UPDATE managed_sessions SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL",
        (int(time.time()), session_id),
    )
    c.commit()
    changed = cur.rowcount > 0
    c.close()
    return changed


def _upsert_managed_user(identity: dict) -> dict:
    subject = str(identity.get("subject") or "").strip()
    email = str(identity.get("email") or "").strip().lower()
    display_name = str(identity.get("display_name") or "North Star Reader").strip()
    tenant_id = str(identity.get("tenant_id") or "").strip()
    if not subject:
        raise HTTPException(401, "entra_oidc_subject_missing")
    if not email:
        raise HTTPException(401, "entra_oidc_email_missing")

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
        # Temporary UAT migration behavior retained for this gate. Identity-binding
        # hardening remains a separate pre-PASS item before Stage 5.3 closure.
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


def _remove_route(path: str, methods: set[str] | None = None) -> None:
    kept = []
    for route in app.router.routes:
        route_methods = set(getattr(route, "methods", set()) or set())
        if getattr(route, "path", None) == path and (methods is None or bool(route_methods & methods)):
            continue
        kept.append(route)
    app.router.routes[:] = kept


# Replace baseline status/account/logout routes in this isolated managed-Entra runtime only.
_remove_route("/api/auth/status", {"GET"})
_remove_route("/api/auth/logout", {"POST"})
_remove_route("/account", {"GET"})


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
    token = _create_managed_session(user["user_id"])
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
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    response.delete_cookie(OIDC_FLOW_COOKIE, path="/")
    return response


@app.get("/api/auth/status")
def auth_status(request: Request):
    user = baseline.current_user(request)
    managed = bool(user and user.get("provider") == MANAGED_IDENTITY_PROVIDER)
    return {
        "provider": MANAGED_IDENTITY_PROVIDER if managed else baseline.IDENTITY_PROVIDER,
        "authenticated": bool(user),
        "user": user,
        "managed_external_idp": managed,
        "session_authority": "SERVER_SIDE_MANAGED_SESSION_DB" if managed else "LOCAL_FALLBACK",
        "production_authorized": False,
    }


@app.post("/api/auth/entra/logout")
def entra_logout(request: Request):
    user = baseline.current_user(request)
    revoked = _revoke_request_session(request)
    if user:
        baseline.audit("identity.entra_logout", {"server_session_revoked": revoked}, user["user_id"])
    response = RedirectResponse("/account", status_code=303)
    response.delete_cookie(baseline.SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    response.delete_cookie(OIDC_FLOW_COOKIE, path="/")
    return response


@app.post("/api/auth/logout")
def logout(request: Request):
    user = baseline.current_user(request)
    managed = bool(user and user.get("provider") == MANAGED_IDENTITY_PROVIDER)
    revoked = _revoke_request_session(request) if managed else False
    if managed:
        baseline.audit("identity.logout", {"server_session_revoked": revoked}, user["user_id"])
    response = RedirectResponse("/account", status_code=303)
    response.delete_cookie(baseline.SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
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
        "session_authority": "SERVER_SIDE_MANAGED_SESSION_DB",
        "production_authorized": False,
    }


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    user = baseline.current_user(request)
    if user and user.get("provider") == MANAGED_IDENTITY_PROVIDER:
        ent = baseline.effective_entitlements(user["user_id"])
        body = f'''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">Identity · Commerce · Access</div><h1 style="font-family:Georgia,serif;margin:.2em 0">North Star Account</h1><p style="color:#c4d2dc">Authentication proves identity. Entitlement authorizes access. Only server-verified commercial evidence establishes paid state.</p></div></section><section class="section"><div class="shell account-grid"><aside class="account-panel"><div class="eyebrow">Managed identity</div><h2>Signed in</h2><span class="status-pill">Microsoft Entra External ID</span><p><b>{baseline.escape(user.get('display_name') or 'North Star Reader')}</b><br>{baseline.escape(user.get('email') or '')}</p><form method="post" action="/api/auth/entra/logout"><button class="btn" type="submit">Sign out</button></form><hr><h3>Effective entitlement</h3><pre>{baseline.escape(json.dumps(ent, indent=2))}</pre></aside><section><div class="eyebrow">Access authority</div><h2>North Star Entitlements</h2><p>Identity is managed by Microsoft Entra External ID. Product access remains controlled by the North Star server-side entitlement authority.</p><p class="notice">Managed session: server-side, revocation-aware · production_authorized=false</p></section></div></section></main>'''
        return baseline.layout("Account", body)

    body = '''<main id="main"><section class="module-hero"><div class="shell"><div class="eyebrow">Identity · Commerce · Access</div><h1 style="font-family:Georgia,serif;margin:.2em 0">North Star Account</h1><p style="color:#c4d2dc">Authentication proves identity. Entitlement authorizes access. Only server-verified commercial evidence establishes paid state.</p></div></section><section class="section"><div class="shell"><div class="account-panel" style="max-width:520px"><div class="eyebrow">Managed identity</div><h2>Sign in</h2><p>Use Microsoft Entra External ID to access your North Star account.</p><a class="btn" href="/api/auth/entra/login">Sign in with Microsoft Entra</a><p class="notice" style="margin-top:18px">LOCAL_OIDC_SIMULATOR remains available as a controlled fallback during Stage 5.3, but it is not presented as the managed customer sign-in experience.</p></div></div></section></main>'''
    return baseline.layout("Account", body)

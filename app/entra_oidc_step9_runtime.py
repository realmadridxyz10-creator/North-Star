from __future__ import annotations

"""Stage 5.3 Step 9 + Step 11 UAT overlay.

Preserves managed Entra identity/session hardening and adds fail-closed,
server-side entitlement enforcement for protected content and Premium AI.
Production authorization remains false.
"""

import hashlib
import os
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app import entra_oidc_runtime as entra_runtime
from app.entra_oidc_runtime import app, baseline
from app.step11_entitlement_guard import require_portal_access, require_premium_ai

_ORIGINAL_LAYOUT = baseline.layout
SESSION_IDLE_MAX_AGE = 1800


def _init_managed_session_activity() -> None:
    c = baseline.db()
    columns = {row["name"] for row in c.execute("PRAGMA table_info(managed_sessions)").fetchall()}
    if "last_activity_at" not in columns:
        c.execute("ALTER TABLE managed_sessions ADD COLUMN last_activity_at INTEGER")
    c.execute("UPDATE managed_sessions SET last_activity_at=? WHERE revoked_at IS NULL AND last_activity_at IS NULL", (int(time.time()),))
    c.commit(); c.close()


_init_managed_session_activity()


def _stable_entra_user_id(tenant_id: str, subject: str) -> str:
    return "usr_entra_" + hashlib.sha256(f"{tenant_id}:{subject}".encode()).hexdigest()[:20]


def _hardened_upsert_managed_user(identity: dict) -> dict:
    subject = str(identity.get("subject") or "").strip()
    tenant_id = str(identity.get("tenant_id") or "").strip()
    email = str(identity.get("email") or "").strip().lower()
    display_name = str(identity.get("display_name") or "North Star Reader").strip()
    if not subject: raise HTTPException(401, "entra_oidc_subject_missing")
    if not tenant_id: raise HTTPException(401, "entra_oidc_tenant_missing")
    if not email: raise HTTPException(401, "entra_oidc_email_missing")
    user_id = _stable_entra_user_id(tenant_id, subject)
    now = int(time.time()); c = baseline.db()
    existing_subject = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    existing_email = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if existing_subject:
        if existing_email and existing_email["user_id"] != user_id:
            c.close(); baseline.audit("identity.entra_binding_conflict", {"reason":"email_owned_by_different_user"}, user_id)
            raise HTTPException(409, "entra_identity_binding_conflict")
        c.execute("UPDATE users SET email=?,display_name=?,provider=? WHERE user_id=?", (email,display_name,entra_runtime.MANAGED_IDENTITY_PROVIDER,user_id))
    else:
        if existing_email:
            c.close(); baseline.audit("identity.entra_binding_conflict", {"reason":"email_preexists_without_stable_subject_binding"})
            raise HTTPException(409, "entra_identity_binding_conflict")
        c.execute("INSERT INTO users VALUES(?,?,?,?,?)", (user_id,email,display_name,entra_runtime.MANAGED_IDENTITY_PROVIDER,now))
    c.commit(); row=c.execute("SELECT * FROM users WHERE user_id=?",(user_id,)).fetchone(); c.close(); return dict(row)


entra_runtime._upsert_managed_user = _hardened_upsert_managed_user

# Step 11.7C-3C R1: B1 chapter registry is authoritative as a module-keyed
# dictionary, while legacy runtime handlers expect a flat list of chapter rows.
# Normalize only the runtime view; do not alter the governed registry artifact.
if isinstance(baseline.CHAPTER_REGISTRY, dict):
    normalized_registry=[]
    for module_name, module_data in baseline.CHAPTER_REGISTRY.items():
        for chapter in (module_data or {}).get("chapters", []):
            row=dict(chapter); row.setdefault("module", module_name); normalized_registry.append(row)
    baseline.CHAPTER_REGISTRY=normalized_registry

_AUTH_UX_STYLE="""<style>.ns-auth-state{display:inline-flex;align-items:center;margin-left:18px;padding:5px 10px;border:1px solid #5d7484;border-radius:18px;color:#d9e2e8;font-size:.78rem;white-space:nowrap}.ns-auth-state.authenticated{border-color:#c7a45a;color:#f0d58f}.ns-auth-state a{color:inherit;text-decoration:none;margin:0}.ns-access-status{margin-top:14px;padding:14px 16px;border:1px solid #d8d1c4;border-radius:8px;background:#fbfaf7}.ns-access-status strong{display:block;margin-bottom:4px;color:#09263a}.ns-access-status span{color:#52616b;font-size:.92rem;line-height:1.45}</style>"""
_AUTH_UX_SCRIPT="""<script>(function(){const state=document.getElementById('ns-auth-state');function esc(v){return String(v).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c];});}function setState(d){if(!state)return;if(d&&d.authenticated){const u=d.user||{};state.className='ns-auth-state authenticated';state.innerHTML='<a href=\"/account\">'+esc(u.display_name||u.email||'Signed in')+' ▾</a>';}else{state.className='ns-auth-state anonymous';state.innerHTML='<a href=\"/account\">Sign in</a>';}}document.querySelectorAll('.account-panel h3').forEach(function(h){if(h.textContent.trim()!=='Effective entitlement')return;const raw=h.nextElementSibling;if(!raw||raw.tagName!=='PRE')return;try{const e=JSON.parse(raw.textContent||'{}');h.textContent='Access status';const box=document.createElement('div');box.className='ns-access-status';if(e.full_portal||e.module||e.premium_ai)box.innerHTML='<strong>Access enabled</strong><span>Your North Star access is active according to the server-verified entitlement record.</span>';else if(e.preview)box.innerHTML='<strong>Preview access</strong><span>You currently have preview access. Additional content becomes available when the corresponding entitlement is activated.</span>';else box.innerHTML='<strong>No active product access</strong>';raw.replaceWith(box);}catch(e){}});fetch('/api/auth/status',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json()).then(setState);})();</script>"""


def _step9_layout(title, body):
    html=_ORIGINAL_LAYOUT(title,body).replace('</head>',_AUTH_UX_STYLE+'</head>',1)
    if '</nav>' in html: html=html.replace('</nav>','<span id="ns-auth-state" class="ns-auth-state">Checking…</span></nav>',1)
    return html.replace('</body>',_AUTH_UX_SCRIPT+'</body>',1)


baseline.layout=_step9_layout


def _enforce_managed_idle_timeout(request: Request) -> bool:
    session_id=entra_runtime._managed_session_id(request.cookies.get(baseline.SESSION_COOKIE))
    if not session_id:return False
    now=int(time.time()); c=baseline.db(); row=c.execute("SELECT user_id,created_at,expires_at,revoked_at,last_activity_at FROM managed_sessions WHERE session_id=?",(session_id,)).fetchone()
    if not row or row["revoked_at"] is not None or row["expires_at"]<=now:c.close();return False
    last=row["last_activity_at"]
    if last is not None and now-last>=SESSION_IDLE_MAX_AGE:
        cur=c.execute("UPDATE managed_sessions SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL",(now,session_id));c.commit();revoked=cur.rowcount>0;uid=row["user_id"];c.close()
        if revoked:baseline.audit("identity.managed_session_idle_timeout",{"idle_timeout_seconds":SESSION_IDLE_MAX_AGE,"absolute_timeout_seconds":entra_runtime.SESSION_MAX_AGE,"server_session_revoked":True},uid)
        return revoked
    c.execute("UPDATE managed_sessions SET last_activity_at=? WHERE session_id=? AND revoked_at IS NULL",(now,session_id));c.commit();c.close();return False


@app.middleware("http")
async def step9_session_security_and_logout_csp(request: Request, call_next):
    idle_expired=_enforce_managed_idle_timeout(request); response=await call_next(request)
    if idle_expired: response.delete_cookie(baseline.SESSION_COOKIE,path="/",secure=True,httponly=True,samesite="strict")
    csp=response.headers.get("Content-Security-Policy",""); sub=os.environ.get("ENTRA_TENANT_SUBDOMAIN","").strip()
    if csp and sub: response.headers["Content-Security-Policy"]=csp.replace("form-action 'self';",f"form-action 'self' https://{sub}.ciamlogin.com;")
    return response


def _requested_module_from_path(path: str) -> str | None:
    parts=[p for p in path.split('/') if p]
    if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'chapters':
        return parts[2].lower()
    if len(parts) >= 2 and parts[0] == 'modules':
        return parts[1].lower()
    return None


@app.middleware("http")
async def step11_entitlement_authorization(request: Request, call_next):
    """Fail closed with controlled 401/403 responses before protected handlers."""
    path=request.url.path
    try:
        if path.startswith('/api/ai/ask'):
            require_premium_ai(baseline, request)
        elif path.startswith('/api/chapters/') or path.startswith('/modules/'):
            require_portal_access(baseline, request, _requested_module_from_path(path))
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)

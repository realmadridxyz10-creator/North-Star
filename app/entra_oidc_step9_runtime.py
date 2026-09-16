from __future__ import annotations

"""Stage 5.3 Step 9 UAT overlay.

Adds portal-wide authentication-state visibility, immediate logout feedback,
customer-readable entitlement presentation, managed-session idle timeout, and
stable Entra identity-binding hardening without changing the entitlement or
production-authorization contracts in the underlying Entra runtime.
"""

import hashlib
import os
import time

from fastapi import HTTPException, Request

from app import entra_oidc_runtime as entra_runtime
from app.entra_oidc_runtime import app, baseline

_ORIGINAL_LAYOUT = baseline.layout
SESSION_IDLE_MAX_AGE = 1800  # 30 minutes


def _init_managed_session_activity() -> None:
    """Add activity tracking to the existing managed-session store safely."""
    c = baseline.db()
    columns = {row["name"] for row in c.execute("PRAGMA table_info(managed_sessions)").fetchall()}
    if "last_activity_at" not in columns:
        c.execute("ALTER TABLE managed_sessions ADD COLUMN last_activity_at INTEGER")
    c.execute(
        "UPDATE managed_sessions SET last_activity_at=? WHERE revoked_at IS NULL AND last_activity_at IS NULL",
        (int(time.time()),),
    )
    c.commit()
    c.close()


_init_managed_session_activity()


def _stable_entra_user_id(tenant_id: str, subject: str) -> str:
    """Derive the North Star managed user key only from verified Entra identity claims."""
    stable = f"{tenant_id}:{subject}"
    return "usr_entra_" + hashlib.sha256(stable.encode()).hexdigest()[:20]


def _hardened_upsert_managed_user(identity: dict) -> dict:
    """Bind managed users exclusively to verified Entra tenant + subject.

    Email remains profile metadata and may change, but it can never select or
    re-bind a North Star managed identity. A conflicting pre-existing email is
    rejected instead of being adopted as the authenticated identity.
    """
    subject = str(identity.get("subject") or "").strip()
    tenant_id = str(identity.get("tenant_id") or "").strip()
    email = str(identity.get("email") or "").strip().lower()
    display_name = str(identity.get("display_name") or "North Star Reader").strip()

    if not subject:
        raise HTTPException(401, "entra_oidc_subject_missing")
    if not tenant_id:
        raise HTTPException(401, "entra_oidc_tenant_missing")
    if not email:
        raise HTTPException(401, "entra_oidc_email_missing")

    user_id = _stable_entra_user_id(tenant_id, subject)
    now = int(time.time())
    c = baseline.db()
    existing_subject = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    existing_email = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if existing_subject:
        # The stable external identity is authoritative. Prevent its profile
        # email from colliding with any different North Star identity.
        if existing_email and existing_email["user_id"] != user_id:
            c.close()
            baseline.audit(
                "identity.entra_binding_conflict",
                {"reason": "email_owned_by_different_user"},
                user_id,
            )
            raise HTTPException(409, "entra_identity_binding_conflict")
        c.execute(
            "UPDATE users SET email=?,display_name=?,provider=? WHERE user_id=?",
            (email, display_name, entra_runtime.MANAGED_IDENTITY_PROVIDER, user_id),
        )
    else:
        # Never use email as an identity key. If the email already belongs to a
        # different record, fail closed rather than silently migrating/rebinding.
        if existing_email:
            c.close()
            baseline.audit(
                "identity.entra_binding_conflict",
                {"reason": "email_preexists_without_stable_subject_binding"},
            )
            raise HTTPException(409, "entra_identity_binding_conflict")
        c.execute(
            "INSERT INTO users VALUES(?,?,?,?,?)",
            (user_id, email, display_name, entra_runtime.MANAGED_IDENTITY_PROVIDER, now),
        )

    c.commit()
    row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    return dict(row)


# Replace the temporary email-adoption behavior in the isolated Stage 5.3
# runtime. The callback resolves this module attribute at request time.
entra_runtime._upsert_managed_user = _hardened_upsert_managed_user

_AUTH_UX_STYLE = """
<style>
.ns-auth-state{display:inline-flex;align-items:center;margin-left:18px;padding:5px 10px;border:1px solid #5d7484;border-radius:18px;color:#d9e2e8;font-size:.78rem;white-space:nowrap}
.ns-auth-state.authenticated{border-color:#c7a45a;color:#f0d58f}
.ns-auth-state.anonymous{color:#d9e2e8}
.ns-auth-state a{color:inherit;text-decoration:none;margin:0}
.ns-access-status{margin-top:14px;padding:14px 16px;border:1px solid #d8d1c4;border-radius:8px;background:#fbfaf7}
.ns-access-status strong{display:block;margin-bottom:4px;color:#09263a}
.ns-access-status span{color:#52616b;font-size:.92rem;line-height:1.45}
@media(max-width:900px){.ns-auth-state{margin-left:10px}}
</style>
"""

_AUTH_UX_SCRIPT = """
<script>
(function(){
  const state=document.getElementById('ns-auth-state');
  function setState(d){
    if(!state) return;
    if(d && d.authenticated){
      const u=d.user||{};
      const name=(u.display_name||u.email||'Signed in');
      state.className='ns-auth-state authenticated';
      state.innerHTML='<a href="/account" aria-label="Signed in account">'+escapeHtml(name)+' ▾</a>';
    }else{
      state.className='ns-auth-state anonymous';
      state.innerHTML='<a href="/account">Sign in</a>';
    }
  }
  function escapeHtml(v){
    return String(v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});
  }

  document.querySelectorAll('.account-panel h3').forEach(function(heading){
    if(heading.textContent.trim()!=='Effective entitlement') return;
    const raw=heading.nextElementSibling;
    if(!raw || raw.tagName!=='PRE') return;
    try{
      const ent=JSON.parse(raw.textContent||'{}');
      const paid=Boolean(ent.full_portal || ent.module || ent.premium_ai);
      const preview=Boolean(ent.preview);
      heading.textContent='Access status';
      const box=document.createElement('div');
      box.className='ns-access-status';
      if(paid){
        box.innerHTML='<strong>Access enabled</strong><span>Your North Star access is active according to the server-verified entitlement record.</span>';
      }else if(preview){
        box.innerHTML='<strong>Preview access</strong><span>You currently have preview access. Additional content becomes available when the corresponding entitlement is activated.</span>';
      }else{
        box.innerHTML='<strong>No active product access</strong><span>Your identity is verified, but no product entitlement is currently active.</span>';
      }
      raw.replaceWith(box);
    }catch(e){
      heading.textContent='Access status';
      raw.textContent='Access information is temporarily unavailable.';
    }
  });

  fetch('/api/auth/status',{credentials:'same-origin',cache:'no-store'})
    .then(function(r){return r.json();}).then(setState)
    .catch(function(){if(state) state.textContent='Account';});

  document.querySelectorAll('form[action="/api/auth/entra/logout"],form[action="/api/auth/logout"]').forEach(function(form){
    form.addEventListener('submit',function(){
      const button=form.querySelector('button[type="submit"]');
      if(button){button.disabled=true;button.textContent='Signing out…';}
      if(state){state.className='ns-auth-state anonymous';state.textContent='Signing out…';}
    });
  });
})();
</script>
"""


def _step9_layout(title, body):
    html = _ORIGINAL_LAYOUT(title, body)
    html = html.replace('</head>', _AUTH_UX_STYLE + '</head>', 1)
    marker = '</nav>'
    indicator = '<span id="ns-auth-state" class="ns-auth-state" aria-live="polite">Checking…</span>'
    if marker in html:
        html = html.replace(marker, indicator + marker, 1)
    html = html.replace('</body>', _AUTH_UX_SCRIPT + '</body>', 1)
    return html


baseline.layout = _step9_layout


def _enforce_managed_idle_timeout(request: Request) -> bool:
    """Enforce a server-side sliding 30-minute idle limit."""
    session_id = entra_runtime._managed_session_id(request.cookies.get(baseline.SESSION_COOKIE))
    if not session_id:
        return False

    now = int(time.time())
    c = baseline.db()
    row = c.execute(
        "SELECT user_id,created_at,expires_at,revoked_at,last_activity_at FROM managed_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if not row or row["revoked_at"] is not None or row["expires_at"] <= now:
        c.close()
        return False

    last_activity = row["last_activity_at"]
    if last_activity is not None and now - last_activity >= SESSION_IDLE_MAX_AGE:
        cur = c.execute(
            "UPDATE managed_sessions SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL",
            (now, session_id),
        )
        c.commit()
        revoked = cur.rowcount > 0
        user_id = row["user_id"]
        c.close()
        if revoked:
            baseline.audit(
                "identity.managed_session_idle_timeout",
                {
                    "idle_timeout_seconds": SESSION_IDLE_MAX_AGE,
                    "absolute_timeout_seconds": entra_runtime.SESSION_MAX_AGE,
                    "server_session_revoked": True,
                },
                user_id,
            )
        return revoked

    c.execute(
        "UPDATE managed_sessions SET last_activity_at=? WHERE session_id=? AND revoked_at IS NULL",
        (now, session_id),
    )
    c.commit()
    c.close()
    return False


@app.middleware("http")
async def step9_session_security_and_logout_csp(request: Request, call_next):
    """Enforce managed-session inactivity and permit the Entra logout redirect."""
    idle_expired = _enforce_managed_idle_timeout(request)
    response = await call_next(request)

    if idle_expired:
        response.delete_cookie(
            baseline.SESSION_COOKIE,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )

    csp = response.headers.get("Content-Security-Policy", "")
    tenant_subdomain = os.environ.get("ENTRA_TENANT_SUBDOMAIN", "").strip()
    if csp and tenant_subdomain:
        entra_origin = f"https://{tenant_subdomain}.ciamlogin.com"
        csp = csp.replace(
            "form-action 'self';",
            f"form-action 'self' {entra_origin};",
        )
        response.headers["Content-Security-Policy"] = csp
    return response

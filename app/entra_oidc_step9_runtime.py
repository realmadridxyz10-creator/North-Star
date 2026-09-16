from __future__ import annotations

"""Stage 5.3 Step 9 UAT overlay.

Adds portal-wide authentication-state visibility, immediate logout feedback,
and customer-readable entitlement presentation without changing the managed
identity, entitlement, or production-authorization contracts in the underlying
Entra runtime.
"""

import os

from fastapi import Request

from app.entra_oidc_runtime import app, baseline

_ORIGINAL_LAYOUT = baseline.layout

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

  // Account UX: preserve the server-side entitlement authority while replacing
  // implementation-level JSON with a customer-readable access summary.
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


# Existing portal routes call baseline.layout at request time, so this isolated
# runtime overlay makes authentication state visible consistently across pages.
baseline.layout = _step9_layout


@app.middleware("http")
async def step9_entra_logout_csp(request: Request, call_next):
    """Permit the managed Entra end-session redirect after a same-origin form POST.

    R4 deliberately restricts form-action to 'self'. Edge applies that policy to
    the 303 redirect target as well, so the logout POST reaches North Star and
    revokes the server session but navigation to CIAM is blocked. Keep the
    policy narrow by allowing only this tenant's CIAM host.
    """
    response = await call_next(request)
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

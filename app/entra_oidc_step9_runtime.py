from __future__ import annotations

"""Stage 5.3 Step 9 UAT overlay.

Adds portal-wide authentication-state visibility and immediate logout feedback
without changing the managed identity, entitlement, or production-authorization
contracts in the underlying Entra runtime.
"""

from app.entra_oidc_runtime import app, baseline

_ORIGINAL_LAYOUT = baseline.layout

_AUTH_UX_STYLE = """
<style>
.ns-auth-state{display:inline-flex;align-items:center;margin-left:18px;padding:5px 10px;border:1px solid #5d7484;border-radius:18px;color:#d9e2e8;font-size:.78rem;white-space:nowrap}
.ns-auth-state.authenticated{border-color:#c7a45a;color:#f0d58f}
.ns-auth-state.anonymous{color:#d9e2e8}
.ns-auth-state a{color:inherit;text-decoration:none;margin:0}
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

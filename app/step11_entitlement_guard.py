"""Stage 5.3 Step 11 server-side authorization guards.

Imported by the Stage 5.3 runtime overlay. Keeps production_authorized=false and
binds protected access to the currently authenticated North Star user and active
server-side entitlement records.
"""
from fastapi import HTTPException, Request


def effective_access(baseline, request: Request) -> tuple[dict, dict]:
    user = baseline.require_user(request)
    effective = baseline.effective_entitlements(user["user_id"])
    return user, effective


def require_portal_access(baseline, request: Request, requested_module: str | None = None) -> dict:
    user, effective = effective_access(baseline, request)

    # Full Portal and Premium AI authorize every North Star module.
    if effective.get("full_portal") or effective.get("premium_ai"):
        return user

    # A Single Module entitlement must explicitly name the requested module in
    # its server-side scope. Legacy/ambiguous scopes such as selected_module do
    # not authorize content and therefore fail closed.
    requested = (requested_module or "").strip().lower()
    if requested:
        for item in effective.get("items", []):
            if item.get("entitlement_type") != "module" or item.get("status") != "active":
                continue
            scope = str(item.get("scope") or "").strip().lower()
            if scope == requested:
                return user
        if effective.get("module"):
            raise HTTPException(status_code=403, detail="module_entitlement_scope_required")

    raise HTTPException(status_code=403, detail="active_content_entitlement_required")


def require_premium_ai(baseline, request: Request) -> dict:
    user, effective = effective_access(baseline, request)
    if not effective.get("premium_ai"):
        raise HTTPException(status_code=403, detail="premium_ai_entitlement_required")
    return user

"""Stage 5.3 Step 11.7B server-side authorization guards.

Imported by the Stage 5.3 runtime overlay. Keeps production_authorized=false and
binds protected access to the currently authenticated North Star user and active
server-side entitlement records.
"""
from fastapi import HTTPException, Request


def effective_access(baseline, request: Request) -> tuple[dict, dict]:
    user = baseline.require_user(request)
    effective = baseline.effective_entitlements(user["user_id"])
    return user, effective


def require_portal_access(baseline, request: Request) -> dict:
    user, effective = effective_access(baseline, request)
    if not (effective.get("module") or effective.get("full_portal") or effective.get("premium_ai")):
        raise HTTPException(status_code=403, detail="active_content_entitlement_required")
    return user


def require_premium_ai(baseline, request: Request) -> dict:
    user, effective = effective_access(baseline, request)
    if not effective.get("premium_ai"):
        raise HTTPException(status_code=403, detail="premium_ai_entitlement_required")
    return user

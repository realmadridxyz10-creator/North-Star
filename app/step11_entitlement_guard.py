"""Stage 5.3 Step 11 server-side authorization guards.

Imported by the Stage 5.3 runtime overlay. Keeps production_authorized=false and
binds protected access to the currently authenticated North Star user and active
server-side entitlement records.
"""
import json
import logging

from fastapi import HTTPException, Request

log = logging.getLogger("northstar.step11.authorization")


def effective_access(baseline, request: Request) -> tuple[dict, dict]:
    user = baseline.require_user(request)
    effective = baseline.effective_entitlements(user["user_id"])
    return user, effective


def _uat_diag(request: Request, user: dict, effective: dict, requested_module: str | None, decision: str) -> None:
    """Temporary Step 11.7F diagnostic: no email, token, cookie or Entra claims."""
    items = [
        {
            "entitlement_type": i.get("entitlement_type"),
            "scope": i.get("scope"),
            "status": i.get("status"),
        }
        for i in effective.get("items", [])
    ]
    log.warning(
        "STEP11_7F_DIAG %s",
        json.dumps(
            {
                "path": request.url.path,
                "user_id": user.get("user_id"),
                "requested_module": requested_module,
                "items": items,
                "module": bool(effective.get("module")),
                "full_portal": bool(effective.get("full_portal")),
                "premium_ai": bool(effective.get("premium_ai")),
                "decision": decision,
            },
            separators=(",", ":"),
        ),
    )


def require_portal_access(baseline, request: Request, requested_module: str | None = None) -> dict:
    user, effective = effective_access(baseline, request)

    if effective.get("full_portal") or effective.get("premium_ai"):
        _uat_diag(request, user, effective, requested_module, "allow_broad")
        return user

    requested = (requested_module or "").strip().lower()
    if requested:
        for item in effective.get("items", []):
            if item.get("entitlement_type") != "module" or item.get("status") != "active":
                continue
            scope = str(item.get("scope") or "").strip().lower()
            if scope == requested:
                _uat_diag(request, user, effective, requested_module, "allow_module_scope")
                return user
        if effective.get("module"):
            _uat_diag(request, user, effective, requested_module, "deny_module_scope")
            raise HTTPException(status_code=403, detail="module_entitlement_scope_required")

    _uat_diag(request, user, effective, requested_module, "deny_no_active_content")
    raise HTTPException(status_code=403, detail="active_content_entitlement_required")


def require_premium_ai(baseline, request: Request) -> dict:
    user, effective = effective_access(baseline, request)
    if not effective.get("premium_ai"):
        raise HTTPException(status_code=403, detail="premium_ai_entitlement_required")
    return user

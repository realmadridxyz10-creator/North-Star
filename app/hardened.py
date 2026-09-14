from __future__ import annotations

import re
from fastapi import Request
from app import main as baseline

app = baseline.app

# Controlled R4 hardening overlay.
# Keeps the DEV-006 baseline intact while applying stricter external-UAT controls.

_POLICY_ATTACK_PATTERNS = [
    r"ignore\s+(all|any|the|your)?\s*(previous|prior|above|earlier)\s*(instructions?|rules?|guidance|messages?)?",
    r"reveal\s+(the\s+)?(system|developer|hidden|internal)\s+(prompt|message|instructions?|rules?)",
    r"show\s+(me\s+)?(the\s+)?(system|developer|hidden|internal)\s+(prompt|message|instructions?|rules?)",
    r"override\s+(north\s+star\s+)?(governance|policy|rules?|controls?|authority)",
    r"bypass\s+(governance|policy|rules?|controls?|restrictions?|guardrails?|security)",
    r"jailbreak",
    r"pretend\s+(the\s+)?(canonical|governed|official)\s+(content|rule|principle|text)",
    r"treat\s+(this|my|generated|invented)\s+(text|wording|content)\s+as\s+(canonical|official|governed)",
    r"invent\s+(a\s+)?north\s+star\s+(principle|rule|policy|quote|content)",
    r"exfiltrat(e|ion)",
    r"hidden\s+instructions?",
    r"developer\s+message",
    r"system\s+prompt",
]


def hardened_classify_question(q: str) -> str:
    x = (q or "").lower()
    if any(re.search(p, x, re.IGNORECASE) for p in _POLICY_ATTACK_PATTERNS):
        return "policy_attack"
    return baseline._baseline_classify_question(q) if hasattr(baseline, "_baseline_classify_question") else "grounded_explanation"


if not hasattr(baseline, "_baseline_classify_question"):
    baseline._baseline_classify_question = baseline.classify_question
baseline.classify_question = hardened_classify_question


@app.middleware("http")
async def r4_security_hardening(request: Request, call_next):
    response = await call_next(request)

    # External UAT is HTTPS-only at Railway. Harden cookies issued by the DEV identity simulator.
    set_cookie = response.headers.get("set-cookie")
    if set_cookie and baseline.SESSION_COOKIE in set_cookie:
        hardened = set_cookie
        if "secure" not in hardened.lower():
            hardened += "; Secure"
        hardened = re.sub(r"SameSite=lax", "SameSite=Strict", hardened, flags=re.IGNORECASE)
        response.headers["set-cookie"] = hardened

    # Additional transport/browser protections for the external UAT edge.
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # Retain inline support needed by the current single-file portal UI, but narrow all other sources.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )
    return response

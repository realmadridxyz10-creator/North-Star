from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


SANDBOX_API_BASE = "https://api-m.sandbox.paypal.com"


class PayPalSandboxError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class PayPalSandboxConfig:
    client_id: str
    client_secret: str
    webhook_id: str | None = None
    api_base: str = SANDBOX_API_BASE

    @classmethod
    def from_env(cls) -> "PayPalSandboxConfig | None":
        client_id = (os.getenv("PAYPAL_SANDBOX_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET") or "").strip()
        if not client_id or not client_secret:
            return None
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            webhook_id=(os.getenv("PAYPAL_SANDBOX_WEBHOOK_ID") or "").strip() or None,
            api_base=(os.getenv("PAYPAL_SANDBOX_API_BASE") or SANDBOX_API_BASE).rstrip("/"),
        )


class PayPalSandboxClient:
    def __init__(self, config: PayPalSandboxConfig, timeout: int = 20):
        self.config = config
        self.timeout = timeout
        self._access_token: str | None = None

    def _json_request(self, method: str, path: str, *, body: Any = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req_headers = {"Accept": "application/json", **(headers or {})}
        if data is not None:
            req_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.config.api_base + path, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {"raw": raw[:2000]}
            raise PayPalSandboxError(f"PayPal Sandbox HTTP {exc.code}", exc.code, payload) from exc
        except urllib.error.URLError as exc:
            raise PayPalSandboxError(f"PayPal Sandbox network error: {exc.reason}") from exc

    def access_token(self) -> str:
        if self._access_token:
            return self._access_token
        auth = base64.b64encode(f"{self.config.client_id}:{self.config.client_secret}".encode()).decode()
        req = urllib.request.Request(
            self.config.api_base + "/v1/oauth2/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Accept-Language": "en_US",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            raise PayPalSandboxError(f"PayPal OAuth HTTP {exc.code}", exc.code, raw[:2000]) from exc
        token = payload.get("access_token")
        if not token:
            raise PayPalSandboxError("PayPal OAuth response missing access_token", payload=payload)
        self._access_token = token
        return token

    def _bearer_headers(self, request_id: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.access_token()}"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        return headers

    def create_order(self, *, amount: str, currency: str, request_id: str, description: str | None = None) -> dict[str, Any]:
        unit: dict[str, Any] = {"amount": {"currency_code": currency, "value": amount}}
        if description:
            unit["description"] = description[:127]
        payload = {"intent": "CAPTURE", "purchase_units": [unit]}
        return self._json_request("POST", "/v2/checkout/orders", body=payload, headers=self._bearer_headers(request_id))

    def capture_order(self, provider_order_id: str, request_id: str | None = None) -> dict[str, Any]:
        return self._json_request(
            "POST",
            f"/v2/checkout/orders/{provider_order_id}/capture",
            body={},
            headers=self._bearer_headers(request_id),
        )

    def verify_webhook(self, *, headers: dict[str, str], event: dict[str, Any]) -> bool:
        if not self.config.webhook_id:
            raise PayPalSandboxError("PAYPAL_SANDBOX_WEBHOOK_ID is not configured")
        h = {k.lower(): v for k, v in headers.items()}
        required = [
            "paypal-auth-algo",
            "paypal-cert-url",
            "paypal-transmission-id",
            "paypal-transmission-sig",
            "paypal-transmission-time",
        ]
        missing = [k for k in required if not h.get(k)]
        if missing:
            raise PayPalSandboxError("Missing PayPal webhook headers: " + ", ".join(missing))
        body = {
            "auth_algo": h["paypal-auth-algo"],
            "cert_url": h["paypal-cert-url"],
            "transmission_id": h["paypal-transmission-id"],
            "transmission_sig": h["paypal-transmission-sig"],
            "transmission_time": h["paypal-transmission-time"],
            "webhook_id": self.config.webhook_id,
            "webhook_event": event,
        }
        result = self._json_request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            body=body,
            headers=self._bearer_headers(),
        )
        return result.get("verification_status") == "SUCCESS"


def sandbox_status() -> dict[str, Any]:
    cfg = PayPalSandboxConfig.from_env()
    return {
        "provider": "PayPal",
        "runtime": "PAYPAL_SANDBOX" if cfg else "PAYPAL_SIMULATOR",
        "sandbox_credentials_configured": bool(cfg),
        "webhook_id_configured": bool(cfg and cfg.webhook_id),
        "api_base": cfg.api_base if cfg else SANDBOX_API_BASE,
        "production_authorized": False,
    }

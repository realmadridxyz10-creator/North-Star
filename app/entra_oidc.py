from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import msal


class EntraOIDCConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EntraOIDCConfig:
    tenant_subdomain: str
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str

    @property
    def authority(self) -> str:
        # Microsoft Entra External ID customer tenants use the CIAM authority.
        return f"https://{self.tenant_subdomain}.ciamlogin.com/{self.tenant_id}"

    @property
    def logout_endpoint(self) -> str:
        # External-tenant OIDC end-session endpoint. The tenant's verified
        # onmicrosoft.com domain is required in the CIAM logout path.
        tenant_domain = f"{self.tenant_subdomain}.onmicrosoft.com"
        return (
            f"https://{self.tenant_subdomain}.ciamlogin.com/"
            f"{tenant_domain}/oauth2/v2.0/logout"
        )

    @classmethod
    def from_env(cls) -> "EntraOIDCConfig | None":
        values = {
            "tenant_subdomain": os.environ.get("ENTRA_TENANT_SUBDOMAIN", "").strip(),
            "tenant_id": os.environ.get("ENTRA_TENANT_ID", "").strip(),
            "client_id": os.environ.get("ENTRA_CLIENT_ID", "").strip(),
            "client_secret": os.environ.get("ENTRA_CLIENT_SECRET", "").strip(),
            "redirect_uri": os.environ.get("ENTRA_REDIRECT_URI", "").strip(),
        }
        if not any(values.values()):
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise EntraOIDCConfigurationError(
                "incomplete_entra_oidc_configuration:" + ",".join(missing)
            )
        return cls(**values)


class EntraOIDCClient:
    """Managed External ID adapter for North Star.

    Authentication proves identity only. North Star's existing server-side
    user/session/entitlement layer remains the authorization authority.
    """

    # MSAL automatically adds reserved OIDC scopes such as openid/profile.
    # Only application-requested non-reserved scopes belong here.
    SCOPES = ["email"]

    def __init__(self, config: EntraOIDCConfig):
        self.config = config
        self._client = msal.ConfidentialClientApplication(
            client_id=config.client_id,
            authority=config.authority,
            client_credential=config.client_secret,
        )

    def begin_login(self) -> dict[str, Any]:
        # MSAL creates and later validates the auth-code flow state/nonce data.
        # Explicit account selection prevents an existing Entra browser SSO
        # session from silently choosing a customer identity for North Star.
        return self._client.initiate_auth_code_flow(
            scopes=self.SCOPES,
            redirect_uri=self.config.redirect_uri,
            prompt="select_account",
        )

    def logout_url(self, post_logout_redirect_uri: str | None = None) -> str:
        params: dict[str, str] = {}
        if post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri
        query = urlencode(params)
        return self.config.logout_endpoint + (f"?{query}" if query else "")

    def complete_login(
        self, flow: dict[str, Any], auth_response: dict[str, str]
    ) -> dict[str, Any]:
        result = self._client.acquire_token_by_auth_code_flow(
            auth_code_flow=flow,
            auth_response=auth_response,
            scopes=self.SCOPES,
        )
        if "error" in result:
            raise RuntimeError(
                "entra_oidc_authentication_failed:"
                + str(result.get("error_description") or result["error"])
            )
        claims = result.get("id_token_claims") or {}
        subject = claims.get("sub")
        if not subject:
            raise RuntimeError("entra_oidc_missing_subject")
        return {
            "subject": subject,
            "email": claims.get("email")
            or claims.get("preferred_username")
            or claims.get("signInNames.emailAddress"),
            "display_name": claims.get("name") or "North Star Reader",
            "tenant_id": claims.get("tid"),
            "claims": claims,
        }


def managed_oidc_status() -> dict[str, Any]:
    try:
        cfg = EntraOIDCConfig.from_env()
    except EntraOIDCConfigurationError as exc:
        return {
            "provider": "MICROSOFT_ENTRA_EXTERNAL_ID",
            "configured": False,
            "configuration_state": "incomplete",
            "detail": str(exc),
            "production_authorized": False,
        }
    if cfg is None:
        return {
            "provider": "MICROSOFT_ENTRA_EXTERNAL_ID",
            "configured": False,
            "configuration_state": "not_configured",
            "production_authorized": False,
        }
    return {
        "provider": "MICROSOFT_ENTRA_EXTERNAL_ID",
        "configured": True,
        "configuration_state": "ready_for_uat",
        "authority": cfg.authority,
        "redirect_uri": cfg.redirect_uri,
        "production_authorized": False,
    }

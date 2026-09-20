"""Groq OpenAI-compatible chat transport for controlled North Star UAT.

No network request occurs on import. Credentials are injected server-side.
The transport accepts only bounded North Star evidence and parses a strict
provider-neutral JSON answer contract.
"""
import json
from typing import Any, Callable

from app.external_llm import ExternalLLMInvalidResponse, ExternalLLMUnavailable, ExternalSynthesisRequest, ExternalSynthesisResponse
from app.openai_transport import stdlib_http_post

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqChatTransport:
    def __init__(self, api_key: str, model: str, http_post: Callable[..., Any] = stdlib_http_post):
        if not api_key:
            raise ValueError("groq_api_key_required")
        if not model:
            raise ValueError("groq_model_required")
        self._api_key = api_key
        self._model = model
        self._http_post = http_post

    def _payload(self, request: ExternalSynthesisRequest) -> dict[str, Any]:
        evidence = [{"chunk_id": e.get("chunk_id"), "text": e.get("text")} for e in request.evidence]
        system = (
            "Synthesize only from supplied North Star governed evidence. "
            "Do not add external facts or sources. Return only JSON with keys "
            "answer (string) and grounded (boolean). Set grounded=false when "
            "the evidence is insufficient. Generated wording is not canonical."
        )
        user = json.dumps({"question": request.question, "answer_class": request.answer_class, "evidence": evidence}, separators=(",", ":"))
        return {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

    def synthesize(self, request: ExternalSynthesisRequest) -> ExternalSynthesisResponse:
        response = self._http_post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json=self._payload(request),
            timeout=request.timeout_seconds,
        )
        status = getattr(response, "status_code", 500)
        if status != 200:
            # Safe diagnostic only: expose HTTP status/category, never provider
            # body, request content, credentials, headers, session data, or PII.
            if status in (401, 403):
                category = "auth"
            elif status == 429:
                category = "rate_limit"
            elif 400 <= status < 500:
                category = "request"
            elif status >= 500:
                category = "provider"
            else:
                category = "http"
            # Preserve only a bounded machine-readable provider code when present.
            # Never propagate the provider message/body, request content, headers,
            # credentials, session data, cookies, or PII.
            provider_code = None
            try:
                error_obj = response.json().get("error", {})
                candidate = error_obj.get("code") or error_obj.get("type")
                if isinstance(candidate, str):
                    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in candidate)
                    provider_code = safe[:64] or None
            except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
                provider_code = None
            reason = f"groq_http_{status}_{category}"
            if provider_code:
                reason = f"{reason}_{provider_code}"

            # Bounded 401/403 message classification only. Inspect the provider
            # message in memory, but emit only a fixed non-secret category.
            # Never propagate the raw message/body or arbitrary provider text.
            if status in (401, 403):
                provider_message_class = None
                try:
                    error_obj = response.json().get("error", {})
                    message = error_obj.get("message")
                    if isinstance(message, str):
                        normalized = message.lower()
                        if "api key" in normalized or "apikey" in normalized:
                            provider_message_class = "api_key"
                        elif "organization" in normalized or "organisation" in normalized:
                            provider_message_class = "organization"
                        elif "project" in normalized:
                            provider_message_class = "project"
                        elif "model" in normalized:
                            provider_message_class = "model"
                        elif "permission" in normalized or "forbidden" in normalized or "not allowed" in normalized:
                            provider_message_class = "permission"
                        elif "blocked" in normalized or "block" in normalized:
                            provider_message_class = "blocked"
                        elif "region" in normalized or "country" in normalized or "location" in normalized:
                            provider_message_class = "region"
                        elif "cloudflare" in normalized:
                            provider_message_class = "cloudflare"
                        else:
                            provider_message_class = "unclassified"
                except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
                    provider_message_class = None
                if provider_message_class:
                    reason = f"{reason}_msg_{provider_message_class}"

            # Bounded response-format diagnostic. Classify only the response
            # representation; never expose the raw body or arbitrary content-type.
            headers = getattr(response, "headers", {}) or {}
            lowered = {str(k).lower(): str(v) for k, v in headers.items()}
            content_type = lowered.get("content-type", "").lower()
            response_format = None
            if "json" in content_type:
                response_format = "json"
            elif "html" in content_type:
                response_format = "html"
            elif content_type.startswith("text/"):
                response_format = "text"
            elif content_type:
                response_format = "other"
            if response_format:
                reason = f"{reason}_format_{response_format}"

            # Bounded origin diagnostic: allow only a small set of non-secret
            # response headers and never propagate arbitrary header values.
            origin = None
            server = lowered.get("server", "").lower()
            via = lowered.get("via", "").lower()
            if "cloudflare" in server or "cloudflare" in via:
                origin = "cloudflare"
            elif "groq" in server or "groq" in via:
                origin = "groq"
            elif server:
                origin = "server_present"
            elif via:
                origin = "via_present"
            if origin:
                reason = f"{reason}_origin_{origin}"
            raise ExternalLLMUnavailable(reason)
        try:
            raw = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            answer, grounded = parsed["answer"], parsed["grounded"]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExternalLLMInvalidResponse("external_schema_invalid") from exc
        if not isinstance(answer, str) or not isinstance(grounded, bool):
            raise ExternalLLMInvalidResponse("external_schema_invalid")
        return ExternalSynthesisResponse(answer=answer, grounded=grounded)

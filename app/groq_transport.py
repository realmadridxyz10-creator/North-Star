"""Groq OpenAI-compatible chat transport for controlled North Star UAT.

No network request occurs on import. Credentials are injected server-side.
The transport accepts only bounded North Star evidence and parses a strict
provider-neutral JSON answer contract.
"""
import json
from typing import Any, Callable

from app.external_llm import ExternalLLMInvalidResponse, ExternalSynthesisRequest, ExternalSynthesisResponse
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
        if getattr(response, "status_code", 500) != 200:
            raise RuntimeError("groq_http_error")
        try:
            raw = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            answer, grounded = parsed["answer"], parsed["grounded"]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExternalLLMInvalidResponse("external_schema_invalid") from exc
        if not isinstance(answer, str) or not isinstance(grounded, bool):
            raise ExternalLLMInvalidResponse("external_schema_invalid")
        return ExternalSynthesisResponse(answer=answer, grounded=grounded)

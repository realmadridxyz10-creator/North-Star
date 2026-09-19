"""OpenAI Responses API transport for North Star.

This module is intentionally transport-only. It receives bounded North Star
evidence and returns a validated provider-neutral synthesis object. Credentials
remain server-side. Importing this module performs no network request.
"""
import json
from typing import Any, Callable

from app.external_llm import (
    ExternalLLMInvalidResponse,
    ExternalSynthesisRequest,
    ExternalSynthesisResponse,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "grounded": {"type": "boolean"},
    },
    "required": ["answer", "grounded"],
    "additionalProperties": False,
}


class OpenAIResponsesTransport:
    def __init__(
        self,
        api_key: str,
        model: str,
        http_post: Callable[..., Any],
    ):
        if not api_key:
            raise ValueError("openai_api_key_required")
        if not model:
            raise ValueError("openai_model_required")
        self._api_key = api_key
        self._model = model
        self._http_post = http_post

    def _payload(self, request: ExternalSynthesisRequest) -> dict[str, Any]:
        bounded_evidence = [
            {
                "chunk_id": item.get("chunk_id"),
                "text": item.get("text"),
            }
            for item in request.evidence
        ]
        instructions = (
            "Synthesize only from the supplied North Star governed evidence. "
            "Do not add external facts or sources. Return grounded=false if the "
            "evidence is insufficient. Generated wording is not canonical."
        )
        return {
            "model": self._model,
            "instructions": instructions,
            "input": json.dumps(
                {
                    "question": request.question,
                    "answer_class": request.answer_class,
                    "evidence": bounded_evidence,
                },
                separators=(",", ":"),
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "north_star_grounded_synthesis",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                }
            },
        }

    def synthesize(self, request: ExternalSynthesisRequest) -> ExternalSynthesisResponse:
        response = self._http_post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=self._payload(request),
            timeout=request.timeout_seconds,
        )
        if getattr(response, "status_code", 500) != 200:
            raise RuntimeError("openai_http_error")

        try:
            body = response.json()
            raw = body["output"][0]["content"][0]["text"]
            parsed = json.loads(raw)
            answer = parsed["answer"]
            grounded = parsed["grounded"]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExternalLLMInvalidResponse("external_schema_invalid") from exc

        if not isinstance(answer, str) or not isinstance(grounded, bool):
            raise ExternalLLMInvalidResponse("external_schema_invalid")
        return ExternalSynthesisResponse(answer=answer, grounded=grounded)

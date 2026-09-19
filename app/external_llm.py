"""North Star external LLM provider-neutral contract.

R1 is intentionally non-live. It defines the integration boundary and preserves
LOCAL_EVIDENCE as the governed fallback. No external SDK, credential, network
call, or production authorization is introduced by this module.
"""
from dataclasses import dataclass
import os
from typing import Any, Callable, Mapping, Sequence

LOCAL_PROVIDER = "LOCAL_EVIDENCE"
SUPPORTED_MODES = {"local", "external"}


@dataclass(frozen=True)
class LLMConfig:
    mode: str = "local"
    provider: str = LOCAL_PROVIDER
    model: str | None = None
    timeout_seconds: int = 20

    @property
    def external_requested(self) -> bool:
        return self.mode == "external"

    @property
    def live_external_model(self) -> bool:
        # R1 contract only: live provider execution is deliberately disabled.
        return False


def load_llm_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    source = os.environ if env is None else env
    mode = (source.get("NS_LLM_MODE") or "local").strip().lower()
    if mode not in SUPPORTED_MODES:
        mode = "local"

    provider = (source.get("NS_LLM_PROVIDER") or LOCAL_PROVIDER).strip() or LOCAL_PROVIDER
    model = (source.get("NS_LLM_MODEL") or "").strip() or None
    try:
        timeout = int(source.get("NS_LLM_TIMEOUT_SECONDS") or "20")
    except ValueError:
        timeout = 20
    timeout = max(1, min(timeout, 60))
    return LLMConfig(mode=mode, provider=provider, model=model, timeout_seconds=timeout)


class ExternalLLMUnavailable(RuntimeError):
    pass


class ExternalLLMInvalidResponse(ExternalLLMUnavailable):
    pass


@dataclass(frozen=True)
class ExternalSynthesisRequest:
    question: str
    answer_class: str
    evidence: Sequence[Mapping[str, Any]]
    timeout_seconds: int


@dataclass(frozen=True)
class ExternalSynthesisResponse:
    answer: str
    grounded: bool


def validate_external_response(response: ExternalSynthesisResponse) -> str:
    answer = (response.answer or "").strip()
    if not answer:
        raise ExternalLLMInvalidResponse("external_empty_answer")
    if not response.grounded:
        raise ExternalLLMInvalidResponse("external_grounding_not_confirmed")
    return answer


class MockExternalProvider:
    """Controlled R2 transport substitute. No network, SDK, or credential use."""

    def __init__(self, handler: Callable[[ExternalSynthesisRequest], ExternalSynthesisResponse]):
        self._handler = handler

    def synthesize(self, request: ExternalSynthesisRequest) -> ExternalSynthesisResponse:
        return self._handler(request)


class ProviderNeutralLLMAdapter:
    """Non-live R1 adapter boundary.

    Evidence is supplied by North Star retrieval. A future provider adapter may
    synthesize from that bounded evidence, but it must not retrieve its own
    canonical authority or silently convert generated text into canonical text.
    """

    def __init__(self, config: LLMConfig | None = None, transport: Any | None = None):
        self.config = config or load_llm_config()
        self.transport = transport

    def status(self) -> dict[str, Any]:
        return {
            "configured_mode": self.config.mode,
            "configured_provider": self.config.provider,
            "configured_model": self.config.model,
            "external_requested": self.config.external_requested,
            "live_external_model": False,
            "fallback_provider": LOCAL_PROVIDER,
            "canonical_authority": "R4/B1",
            "production_authorized": False,
        }

    def synthesize(
        self,
        question: str,
        answer_class: str,
        evidence: Sequence[Mapping[str, Any]],
    ) -> str:
        if not evidence:
            raise ExternalLLMUnavailable("insufficient_governed_evidence")
        if not self.config.external_requested:
            raise ExternalLLMUnavailable("external_llm_not_requested")
        if self.transport is None:
            raise ExternalLLMUnavailable("external_llm_transport_not_configured")
        request = ExternalSynthesisRequest(question=question, answer_class=answer_class, evidence=evidence, timeout_seconds=self.config.timeout_seconds)
        try:
            response = self.transport.synthesize(request)
        except TimeoutError as exc:
            raise ExternalLLMUnavailable("external_llm_timeout") from exc
        except ExternalLLMUnavailable:
            raise
        except Exception as exc:
            raise ExternalLLMUnavailable("external_llm_provider_error") from exc
        return validate_external_response(response)


def safe_external_synthesis(
    adapter: ProviderNeutralLLMAdapter,
    question: str,
    answer_class: str,
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Attempt the adapter boundary without weakening the local fallback."""
    try:
        answer = adapter.synthesize(question, answer_class, evidence)
        return {
            "used_external": True,
            "answer": answer,
            "provider": adapter.config.provider,
            "fallback_reason": None,
        }
    except ExternalLLMUnavailable as exc:
        return {
            "used_external": False,
            "answer": None,
            "provider": LOCAL_PROVIDER,
            "fallback_reason": str(exc),
        }

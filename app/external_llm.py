"""North Star external LLM provider-neutral contract.

R1 is intentionally non-live. It defines the integration boundary and preserves
LOCAL_EVIDENCE as the governed fallback. No external SDK, credential, network
call, or production authorization is introduced by this module.
"""
from dataclasses import dataclass
import os
from typing import Any, Mapping, Sequence

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


class ProviderNeutralLLMAdapter:
    """Non-live R1 adapter boundary.

    Evidence is supplied by North Star retrieval. A future provider adapter may
    synthesize from that bounded evidence, but it must not retrieve its own
    canonical authority or silently convert generated text into canonical text.
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or load_llm_config()

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
        raise ExternalLLMUnavailable("external_llm_not_enabled_in_r1")


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

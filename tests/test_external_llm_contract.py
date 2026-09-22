# Gate 13.7 — runtime governed-evidence boundary assurance.
def test_runtime_ai_path_passes_only_governed_evidence_to_external_provider(
    monkeypatch,
):
    monkeypatch.setenv("NS_LLM_MODE", "external")

    from app import main

    seen = {}

    def handler(req):
        seen["request"] = req
        return ExternalSynthesisResponse(
            answer="Governed external synthesis.",
            grounded=True,
        )

    main.EXTERNAL_LLM_ADAPTER = ProviderNeutralLLMAdapter(
        load_llm_config({
            "NS_LLM_MODE": "external",
            "NS_LLM_PROVIDER": "MOCK",
        }),
        MockExternalProvider(handler),
    )

    req = main.AIAskRequest(
        question="Explain North Star governance",
        max_evidence=3,
    )
    result = main.ai_ask(req)

    assert result["provider"] == "MOCK"
    assert result["external_llm_used"] is True
    assert result["external_llm_fallback_reason"] is None
    assert result["canonical_content"] is False
    assert result["grounded"] is True
    assert result["citations"]

    external_request = seen["request"]

    assert external_request.question == req.question
    assert external_request.answer_class == result["answer_class"]
    assert external_request.evidence
    assert len(external_request.evidence) <= req.max_evidence

    evidence_text = " ".join(
        str(item)
        for item in external_request.evidence
    )

    assert "system prompt" not in evidence_text.lower()
    assert "developer message" not in evidence_text.lower()
    assert "hidden instruction" not in evidence_text.lower()

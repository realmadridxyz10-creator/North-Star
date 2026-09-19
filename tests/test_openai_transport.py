import json

from app.external_llm import ExternalSynthesisRequest, ExternalLLMInvalidResponse
from app.openai_transport import OpenAIResponsesTransport, OPENAI_RESPONSES_URL


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}
    def json(self):
        return self._body


def request():
    return ExternalSynthesisRequest(
        question="How should governance be handled?",
        answer_class="grounded_explanation",
        evidence=[{"chunk_id":"c1","text":"Governed evidence.","extra":"must_not_cross_boundary"}],
        timeout_seconds=11,
    )


def test_openai_transport_builds_bounded_structured_request():
    seen = {}
    def post(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return FakeResponse(body={"output":[{"content":[{"text":json.dumps({"answer":"Grounded answer.","grounded":True})}]}]})
    transport = OpenAIResponsesTransport("secret-test-key", "gpt-5.4-mini", post)
    result = transport.synthesize(request())
    assert result.answer == "Grounded answer."
    assert result.grounded is True
    assert seen["url"] == OPENAI_RESPONSES_URL
    assert seen["timeout"] == 11
    assert seen["headers"]["Authorization"] == "Bearer secret-test-key"
    payload = seen["json"]
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["text"]["format"]["strict"] is True
    supplied = json.loads(payload["input"])
    assert supplied["question"] == request().question
    assert supplied["evidence"] == [{"chunk_id":"c1","text":"Governed evidence."}]
    assert "extra" not in payload["input"]


def test_openai_transport_rejects_schema_invalid_response():
    transport = OpenAIResponsesTransport(
        "secret-test-key", "gpt-5.4-mini",
        lambda *args, **kwargs: FakeResponse(body={"output":[{"content":[{"text":"not-json"}]}]}),
    )
    try:
        transport.synthesize(request())
        raise AssertionError("expected schema failure")
    except ExternalLLMInvalidResponse as exc:
        assert str(exc) == "external_schema_invalid"


def test_openai_transport_rejects_wrong_types():
    transport = OpenAIResponsesTransport(
        "secret-test-key", "gpt-5.4-mini",
        lambda *args, **kwargs: FakeResponse(body={"output":[{"content":[{"text":json.dumps({"answer":7,"grounded":"yes"})}]}]}),
    )
    try:
        transport.synthesize(request())
        raise AssertionError("expected schema failure")
    except ExternalLLMInvalidResponse as exc:
        assert str(exc) == "external_schema_invalid"


def test_openai_transport_maps_non_200_to_provider_error_boundary():
    transport = OpenAIResponsesTransport(
        "secret-test-key", "gpt-5.4-mini",
        lambda *args, **kwargs: FakeResponse(status_code=429),
    )
    try:
        transport.synthesize(request())
        raise AssertionError("expected provider failure")
    except RuntimeError as exc:
        assert str(exc) == "openai_http_error"


def test_openai_transport_requires_server_side_configuration():
    for key, model, expected in [
        ("", "gpt-5.4-mini", "openai_api_key_required"),
        ("secret-test-key", "", "openai_model_required"),
    ]:
        try:
            OpenAIResponsesTransport(key, model, lambda *args, **kwargs: None)
            raise AssertionError("expected configuration failure")
        except ValueError as exc:
            assert str(exc) == expected

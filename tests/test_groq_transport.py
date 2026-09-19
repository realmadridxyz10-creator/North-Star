import json
from app.external_llm import ExternalSynthesisRequest, ExternalLLMInvalidResponse
from app.groq_transport import GroqChatTransport, GROQ_CHAT_URL

class FakeResponse:
    def __init__(self,status_code=200,body=None): self.status_code=status_code; self._body=body or {}
    def json(self): return self._body

def req():
    return ExternalSynthesisRequest("Explain governance","grounded_explanation",[{"chunk_id":"c1","text":"Governed evidence.","private":"exclude"}],12)

def test_groq_bounded_json_request_and_valid_response():
    seen={}
    def post(url,**kwargs):
        seen["url"]=url; seen.update(kwargs)
        return FakeResponse(body={"choices":[{"message":{"content":json.dumps({"answer":"Grounded.","grounded":True})}}]})
    out=GroqChatTransport("synthetic-key","openai/gpt-oss-20b",post).synthesize(req())
    assert out.answer=="Grounded." and out.grounded is True
    assert seen["url"]==GROQ_CHAT_URL and seen["timeout"]==12
    supplied=json.loads(seen["json"]["messages"][1]["content"])
    assert supplied["evidence"]==[{"chunk_id":"c1","text":"Governed evidence."}]
    assert "private" not in seen["json"]["messages"][1]["content"]
    assert seen["json"]["response_format"]=={"type":"json_object"}

def test_groq_invalid_json_fails_closed():
    t=GroqChatTransport("synthetic-key","openai/gpt-oss-20b",lambda *a,**k: FakeResponse(body={"choices":[{"message":{"content":"bad"}}]}))
    try: t.synthesize(req()); raise AssertionError("expected invalid")
    except ExternalLLMInvalidResponse as e: assert str(e)=="external_schema_invalid"

def test_groq_wrong_types_fail_closed():
    t=GroqChatTransport("synthetic-key","openai/gpt-oss-20b",lambda *a,**k: FakeResponse(body={"choices":[{"message":{"content":json.dumps({"answer":1,"grounded":"yes"})}}]}))
    try: t.synthesize(req()); raise AssertionError("expected invalid")
    except ExternalLLMInvalidResponse as e: assert str(e)=="external_schema_invalid"

def test_groq_non_200_exposes_only_safe_http_diagnostic():
    cases = [
        (400, "groq_http_400_request"),
        (401, "groq_http_401_auth"),
        (403, "groq_http_403_auth"),
        (429, "groq_http_429_rate_limit"),
        (500, "groq_http_500_provider"),
    ]
    for status, expected in cases:
        t=GroqChatTransport("synthetic-key","openai/gpt-oss-20b",lambda *a,_status=status,**k: FakeResponse(status_code=_status))
        try: t.synthesize(req()); raise AssertionError("expected provider error")
        except RuntimeError as e: assert str(e)==expected

def test_groq_requires_key_and_model():
    for key,model,msg in [("","m","groq_api_key_required"),("k","","groq_model_required")]:
        try: GroqChatTransport(key,model); raise AssertionError("expected config error")
        except ValueError as e: assert str(e)==msg

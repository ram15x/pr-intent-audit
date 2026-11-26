import httpx
from pr_audit.llm import LLM, _daily_limit


def _resp(code, text):
    return httpx.Response(code, text=text, request=httpx.Request("POST", "http://x"))


def test_daily_vs_minute_limit_detection():
    assert _daily_limit(_resp(429, "Rate limit reached ... on tokens per day (TPD): Limit 200000"))
    assert not _daily_limit(_resp(429, "Rate limit reached ... on tokens per minute (TPM): Limit 8000"))


def test_daily_limit_fails_fast_and_is_remembered(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    llm = LLM(tmp_path, providers=("groq",)); n = {"calls": 0}

    def fake(provider, prompt):
        n["calls"] += 1
        raise httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://x"),
                                    response=_resp(429, "on tokens per day (TPD): Limit 200000"))
    monkeypatch.setattr(llm, "_call", fake)
    for _ in range(2):
        try:
            llm("p"); assert False
        except RuntimeError as e:
            assert "daily quota" in str(e) or "HTTP 429" in str(e)
    assert n["calls"] == 1            # one attempt, then the provider is marked out for the run
    assert llm.calls["fail"] == 2


def test_tokens_counted(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    llm = LLM(tmp_path, providers=("groq",))
    class R:
        def raise_for_status(self): pass
        def json(self): return {"usage": {"total_tokens": 1234}, "choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setattr(llm.http, "post", lambda *a, **k: R())
    assert llm("hello") == "{}" and llm.calls["groq_tokens"] == 1234
    assert llm("hello") == "{}" and llm.calls["groq_tokens"] == 1234   # second call is cached, no new tokens

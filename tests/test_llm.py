"""shared/llm.py call_claude 검증 — anthropic client mock (네트워크/API키 불필요)."""

import anthropic
import httpx
import pytest
import responses

from topic_pipeline.shared import llm


class _Block:
    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


def test_call_claude_returns_first_text_block(monkeypatch):
    seen = {}

    class _Messages:
        def create(self, **kwargs):
            seen.update(kwargs)
            return _Resp("RESULT")

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    out = llm.call_claude("my prompt", "claude-x")
    assert out == "RESULT"
    assert seen["model"] == "claude-x"
    assert seen["max_tokens"] == 8192
    assert seen["messages"] == [{"role": "user", "content": "my prompt"}]


def test_call_claude_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    state = {"n": 0}

    class _Messages:
        def create(self, **kwargs):
            state["n"] += 1
            if state["n"] < 2:
                raise anthropic.APIConnectionError(message="boom", request=req)
            return _Resp("OK")

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    out = llm.call_claude("p", "m", backoff=0)
    assert out == "OK"
    assert state["n"] == 2


# ── provider 디스패치 + local (issue #3) ──

def test_generate_dispatch_claude(monkeypatch):
    class _Messages:
        def create(self, **kwargs):
            return _Resp("CLAUDE_OK")

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    assert llm.generate("p", {"label": {"provider": "claude", "model": "m"}}) == "CLAUDE_OK"


def test_generate_default_provider_is_claude(monkeypatch):
    monkeypatch.setattr(llm, "call_claude", lambda prompt, model, **kw: f"C:{model}")
    assert llm.generate("p", {"label": {"model": "m"}}) == "C:m"  # provider 미지정 → claude


def test_generate_dispatch_local(monkeypatch):
    monkeypatch.setattr(llm, "call_local", lambda prompt, model, **kw: f"LOCAL:{model}:{kw.get('base_url')}")
    out = llm.generate("p", {"label": {"provider": "local", "model": "llama3", "base_url": "http://x/v1"}})
    assert out == "LOCAL:llama3:http://x/v1"


def test_generate_keywords_raises():
    with pytest.raises(ValueError, match="keywords"):
        llm.generate("p", {"label": {"provider": "keywords"}})


@responses.activate
def test_call_local_openai_compatible():
    responses.add(
        responses.POST,
        "http://localhost:11434/v1/chat/completions",
        json={"choices": [{"message": {"content": "LOCAL_OK"}}]},
        status=200,
    )
    out = llm.call_local("prompt", "llama3", base_url="http://localhost:11434/v1")
    assert out == "LOCAL_OK"
    body = responses.calls[0].request.body
    body = body.decode() if isinstance(body, (bytes, bytearray)) else body
    assert "llama3" in body

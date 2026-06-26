"""shared/llm.py call_claude 검증 — anthropic client mock (네트워크/API키 불필요)."""

import anthropic
import httpx

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

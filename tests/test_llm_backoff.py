"""structured_call waits out OpenAI 429 tokens-per-minute limits instead of
crashing the graph, but fails fast when the account is out of credit."""
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from agents import llm


def _rate_limit_error(code: str) -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return openai.RateLimitError("429", response=response, body={"code": code})


def _tool_response(name: str, args: dict):
    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))])


class _FakeClient:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _call(client):
    return llm.structured_call(client, "sys", "user", "record", {"type": "object"}, "desc")


def test_retries_after_rate_limit(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    client = _FakeClient([
        _rate_limit_error("rate_limit_exceeded"),
        _rate_limit_error("rate_limit_exceeded"),
        _tool_response("record", {"ok": True}),
    ])
    assert _call(client) == {"ok": True}
    assert client.calls == 3
    assert sleeps == list(llm.RATE_LIMIT_BACKOFF[:2])


def test_insufficient_quota_fails_fast(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    client = _FakeClient([_rate_limit_error("insufficient_quota")])
    with pytest.raises(openai.RateLimitError):
        _call(client)
    assert client.calls == 1 and sleeps == []

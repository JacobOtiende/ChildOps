"""
Fakes used only in tests. No real network calls happen anywhere in this
file — that's the point: these let us verify the GRAPH's branching logic
(the round cap, the correction loop, the defer-join) deterministically,
independent of what a real LLM or a real Google API would return, which
would make the tests flaky and slow instead of a fast correctness check.

Live-mode behavior (main.py --mode live) uses the real openai client and
real Google API services from auth/google_auth.py — those are exercised by
actually running the program with real credentials, not by these tests.
"""
from __future__ import annotations

import json
from typing import Any


class FakeFunctionCall:
    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = json.dumps(arguments)


class FakeToolCall:
    def __init__(self, name: str, arguments: dict):
        self.function = FakeFunctionCall(name, arguments)


class FakeMessage:
    def __init__(self, tool_calls: list):
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message: FakeMessage):
        self.message = message


class FakeResponse:
    def __init__(self, choices: list):
        self.choices = choices


class ScriptedClient:
    """Stands in for openai.OpenAI. Scripted per tool name: each call
    for a given tool pops the next queued response, in order, so a test can
    lay out exactly what each agent "decides" at each step of a multi-round
    conversation."""

    def __init__(self, script: dict[str, list[dict]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs) -> FakeResponse:
        tool_name = kwargs["tool_choice"]["function"]["name"]
        self.calls.append(tool_name)
        queue = self.script.get(tool_name)
        if not queue:
            raise AssertionError(
                f"ScriptedClient has no queued response left for tool {tool_name!r}. "
                f"Calls so far: {self.calls}"
            )
        arguments = queue.pop(0)
        return FakeResponse([FakeChoice(FakeMessage([FakeToolCall(tool_name, arguments)]))])


class _Exec:
    def __init__(self, result: Any):
        self._result = result

    def execute(self) -> Any:
        return self._result


class FakeEventsResource:
    def __init__(self, existing_events: list[dict] | None = None):
        self.existing_events = existing_events or []
        self.created: list[dict] = []

    def list(self, **kwargs) -> _Exec:
        return _Exec({"items": self.existing_events})

    def insert(self, **kwargs) -> _Exec:
        event_id = f"evt-{len(self.created) + 1}"
        self.created.append({"id": event_id, **kwargs.get("body", {})})
        return _Exec({"id": event_id})

    def patch(self, **kwargs) -> _Exec:
        return _Exec({})


class FakeCalendarService:
    def __init__(self, existing_events: list[dict] | None = None):
        self._events = FakeEventsResource(existing_events)

    def events(self) -> FakeEventsResource:
        return self._events


class FakeApprovalQueue:
    """In-memory stand-in for approvals.approval_queue.ApprovalQueue."""

    def __init__(self):
        self.pending: dict[str, dict] = {}
        self._next_id = 1

    def enqueue(self, draft: dict) -> str:
        approval_id = f"appr-{self._next_id}"
        self._next_id += 1
        self.pending[approval_id] = draft
        return approval_id

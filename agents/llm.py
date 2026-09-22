"""
Thin wrapper around the OpenAI SDK shared by every agent.

Every agent "decision" in this project is a real LLM call constrained to a
tool-input schema (the standard structured-output pattern), not a hand-coded
if/else pretending to be a model. structured_call() forces the model to
answer through exactly one named tool, which turns its response into a
parsed dict instead of free text you'd have to regex out.
"""
from __future__ import annotations

import json
import os
from typing import Any

import openai

# Override via CHILDOPS_MODEL if OpenAI ships a newer model id after this
# was written — don't assume this stays current.
DEFAULT_MODEL = os.environ.get("CHILDOPS_MODEL", "gpt-4o")


def get_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key)


def structured_call(
    client: openai.OpenAI,
    system: str,
    user_content: str,
    tool_name: str,
    tool_schema: dict[str, Any],
    tool_description: str,
    model: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Force a single structured response via tool_choice and return the
    parsed arguments dict for that tool call."""
    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    for call in response.choices[0].message.tool_calls or []:
        if call.function.name == tool_name:
            return json.loads(call.function.arguments)
    raise RuntimeError(f"Model response did not include the required {tool_name!r} tool call")

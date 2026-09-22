"""
Thin wrapper around the Anthropic SDK shared by every agent.

Every agent "decision" in this project is a real LLM call constrained to a
tool-input schema (the standard structured-output pattern), not a hand-coded
if/else pretending to be a model. structured_call() forces the model to
answer through exactly one named tool, which turns its response into a
parsed dict instead of free text you'd have to regex out.
"""
from __future__ import annotations

import os
from typing import Any

import anthropic

# Override via CHILDOPS_MODEL if Anthropic ships a newer model id after this
# was written — don't assume this stays current.
DEFAULT_MODEL = os.environ.get("CHILDOPS_MODEL", "claude-sonnet-4-5-20250929")


def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def structured_call(
    client: anthropic.Anthropic,
    system: str,
    user_content: str,
    tool_name: str,
    tool_schema: dict[str, Any],
    tool_description: str,
    model: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Force a single structured response via tool_choice and return the
    parsed input dict for that tool call."""
    response = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system,
        tools=[
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": tool_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Model response did not include the required {tool_name!r} tool call")

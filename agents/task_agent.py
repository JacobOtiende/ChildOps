"""
Task Agent: scores urgency/importance on a classified item and proposes a
concrete action. This is the "reasoning loop" node from the design — the
consult-both / wait-for-both / act-or-escalate control flow lives in the
graph (graph/build_graph.py) because it spans multiple nodes and turns, but
the actual judgment call ("how urgent is this, what should happen") is this
LLM call.
"""
from __future__ import annotations

from agents.llm import structured_call

PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "urgency_score": {"type": "integer", "minimum": 1, "maximum": 5, "description": "1=no time pressure, 5=needs action today"},
        "importance_score": {"type": "integer", "minimum": 1, "maximum": 5, "description": "1=trivial, 5=high-consequence if missed"},
        "proposed_action": {
            "type": "string",
            "enum": ["create_calendar_event", "draft_email_response", "log_only", "escalate_to_parent"],
        },
        "needs_calendar": {"type": "boolean"},
        "needs_email": {"type": "boolean"},
        "proposed_title": {"type": "string", "description": "Short title for a calendar event, if needs_calendar is true."},
        "proposed_datetime": {
            "type": ["string", "null"],
            "description": "ISO 8601 datetime for the proposed event start, if known/inferable. Null if not applicable.",
        },
        "rationale": {"type": "string", "description": "One sentence explaining the urgency/importance call."},
    },
    "required": [
        "urgency_score",
        "importance_score",
        "proposed_action",
        "needs_calendar",
        "needs_email",
        "proposed_title",
        "proposed_datetime",
        "rationale",
    ],
}

SYSTEM_PROMPT = """You are the Task Follow-Up Agent. Given a classified school
item, you decide how urgent and important it is and propose exactly one
concrete next action. You do not execute anything yourself — Control Tower
and the Calendar Agent must both sign off before your proposal becomes real.
Be concrete: if a calendar event is warranted, give it a real title and, if
the source material states or implies a specific time, a real datetime."""


def score_and_propose(client, classification: dict, today_iso: str, model: str | None = None) -> dict:
    user_content = (
        f"Today's date is {today_iso}.\n\n"
        f"Classified school item:\n{classification}\n\n"
        "Score this and propose one action using the propose_task_action tool."
    )
    return structured_call(
        client,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="propose_task_action",
        tool_schema=PROPOSE_SCHEMA,
        tool_description="Record the urgency/importance score and the proposed next action.",
        model=model,
    )


RECONSIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "accept_counter": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": ["accept_counter", "reasoning"],
}

RECONSIDER_SYSTEM = """You are the Task Follow-Up Agent responding to the
Calendar Agent's counter-proposal. Weigh your own urgency/importance score
against the Calendar Agent's stated conflict reasoning. Accept the counter
if it doesn't meaningfully undermine the item's urgency; hold firm only if
the counter would cause a real problem (e.g. pushes past a hard deadline)."""


def reconsider_counter(
    client,
    proposed_title: str,
    urgency_score: int,
    importance_score: int,
    counter_datetime: str,
    calendar_reasoning: str,
    model: str | None = None,
) -> dict:
    user_content = (
        f"Your original proposal: '{proposed_title}' (urgency={urgency_score}/5, "
        f"importance={importance_score}/5).\n"
        f"Calendar Agent counter-proposed {counter_datetime}, reasoning: {calendar_reasoning}\n\n"
        "Decide using the reconsider_counter tool."
    )
    return structured_call(
        client,
        system=RECONSIDER_SYSTEM,
        user_content=user_content,
        tool_name="reconsider_counter",
        tool_schema=RECONSIDER_SCHEMA,
        tool_description="Record whether the Task Agent accepts the Calendar Agent's counter-proposal.",
        model=model,
    )


DRAFT_EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["to", "subject", "body"],
}

DRAFT_SYSTEM_PROMPT = """You draft a reply email on the parent's behalf. You
never send it — you only ever produce a draft that a human must explicitly
approve. Write in a warm, concise, professional tone appropriate for
communicating with a child's school."""


def draft_email_response(client, classification: dict, recipient: str, model: str | None = None) -> dict:
    user_content = (
        f"The school sent this item, which needs a reply:\n{classification}\n\n"
        f"Draft a reply to {recipient} using the draft_email tool."
    )
    return structured_call(
        client,
        system=DRAFT_SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="draft_email",
        tool_schema=DRAFT_EMAIL_SCHEMA,
        tool_description="Record a drafted (unsent) email reply.",
        model=model,
    )

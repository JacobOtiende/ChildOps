"""
Calendar Agent: evaluates a Task Agent proposal against the real calendar
(via tools/calendar_tool.py) and takes a negotiation position each round.

The negotiation protocol from the design: this agent argues for protecting
the existing schedule but must weigh the Task Agent's urgency/importance
score; after Settings.negotiation_round_cap rounds without agreement,
Control Tower breaks the tie (see agents/control_tower.py:break_deadlock and
graph/build_graph.py for the round-counting).
"""
from __future__ import annotations

from agents.llm import structured_call
from tools.calendar_tool import check_conflict, propose_alternates

NEGOTIATE_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {"type": "string", "enum": ["accept", "counter", "reject"]},
        "counter_datetime": {
            "type": ["string", "null"],
            "description": "ISO 8601 datetime being counter-proposed, if position is 'counter'. Null otherwise.",
        },
        "reasoning": {"type": "string", "description": "The Calendar Agent's argument for this position, referencing the actual schedule conflict or lack thereof."},
    },
    "required": ["position", "counter_datetime", "reasoning"],
}

SYSTEM_PROMPT = """You are the Calendar & Reminder Agent. You protect the
parent's existing schedule but you are not obstinate: weigh the Task Agent's
stated urgency and importance against the real conflicts you were given.
Accept if there's no real conflict or the proposal clearly outweighs it.
Counter with one of the provided alternate times if a conflict exists and a
good alternative is available. Reject only if no alternative works and the
importance score is low. Always ground your reasoning in the actual conflict
data you were given, not a generic preference for protecting the calendar."""


def evaluate_proposal(
    client,
    calendar_service,
    calendar_id: str,
    proposed_title: str,
    proposed_datetime: str,
    duration_minutes: int,
    urgency_score: int,
    importance_score: int,
    round_number: int,
    prior_rounds: list[dict],
    model: str | None = None,
) -> dict:
    """One round of negotiation. Runs a REAL conflict check against the
    calendar first, then asks the LLM to take a position grounded in that
    real data — this is the tool-call-then-reason pattern, not a scripted
    accept/reject."""
    from datetime import datetime, timedelta

    start = proposed_datetime
    end_dt = datetime.fromisoformat(proposed_datetime) + timedelta(minutes=duration_minutes)
    conflicts = check_conflict(calendar_service, calendar_id, start, end_dt.isoformat())

    alternates: list[str] = []
    if conflicts:
        alternates = propose_alternates(
            calendar_service,
            calendar_id,
            desired_start_iso=proposed_datetime,
            duration_minutes=duration_minutes,
        )

    user_content = (
        f"Round {round_number} of negotiation.\n"
        f"Proposed event: '{proposed_title}' at {proposed_datetime} "
        f"(duration {duration_minutes} min).\n"
        f"Task Agent urgency={urgency_score}/5, importance={importance_score}/5.\n"
        f"Real conflicts found on the calendar: {conflicts or 'none'}.\n"
        f"Available alternate slots if a counter is needed: {alternates or 'none found'}.\n"
        f"Prior negotiation rounds this session: {prior_rounds or 'none'}.\n\n"
        "Take your position using the negotiate_schedule tool."
    )
    return structured_call(
        client,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="negotiate_schedule",
        tool_schema=NEGOTIATE_SCHEMA,
        tool_description="Record this round's negotiation position.",
        model=model,
    )

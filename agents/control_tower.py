"""
Control Tower: gatekeeper for consequential/external actions, arbiter of
last resort, and keeper of consistent state.

Implements the tiering recommended during design review — most Task Agent
output never reaches here at all (see graph/build_graph.py routing); what
does reach here gets a fast tier-one triage, and only items tier-one flags
(or anything about to leave the house, like an email) get the full tier-two
generator/critic pass. This is what "two-tier system" means operationally:
two sequential LLM calls with different jobs, not two copies of the same
check.
"""
from __future__ import annotations

from agents.llm import structured_call

TIER_ONE_SCHEMA = {
    "type": "object",
    "properties": {
        "flagged": {"type": "boolean", "description": "True if this needs the deeper tier-two review."},
        "flag_reason": {"type": ["string", "null"]},
    },
    "required": ["flagged", "flag_reason"],
}

TIER_ONE_SYSTEM = """You are Control Tower's fast triage pass. You look at a
proposed action for obvious problems only: factual inconsistency with stated
history, inappropriate tone, missing required info, or anything irreversible
being done without the stated approvals. If it looks routine and fine, do
not flag it — most items should pass tier one with no flag. Be decisive and
brief; the deeper reviewer runs only when you flag something."""


def tier_one_review(client, action_description: str, model: str | None = None) -> dict:
    return structured_call(
        client,
        system=TIER_ONE_SYSTEM,
        user_content=f"Proposed action:\n{action_description}\n\nTriage it with the tier_one_triage tool.",
        tool_name="tier_one_triage",
        tool_schema=TIER_ONE_SCHEMA,
        tool_description="Record the fast triage result.",
        model=model,
    )


TIER_TWO_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "corrections": {"type": ["string", "null"], "description": "Specific correction needed, if not approved."},
        "reasoning": {"type": "string"},
    },
    "required": ["approved", "corrections", "reasoning"],
}

TIER_TWO_SYSTEM = """You are Control Tower's deep review pass, invoked only
on items tier one flagged, or on anything with external consequence (an
outbound email, a real appointment booking). Check appropriateness, relevance
to the actual conversation history you're given, and correctness. If you
reject, state exactly what must change — your correction goes directly back
to the originating agent."""


def tier_two_review(client, action_description: str, tier_one_flag_reason: str | None, history: str, model: str | None = None) -> dict:
    user_content = (
        f"Proposed action:\n{action_description}\n\n"
        f"Tier-one flag reason: {tier_one_flag_reason or '(escalated due to external consequence, not a tier-one flag)'}\n\n"
        f"Relevant conversation/history context:\n{history or '(none)'}\n\n"
        "Render your decision using the tier_two_decision tool."
    )
    return structured_call(
        client,
        system=TIER_TWO_SYSTEM,
        user_content=user_content,
        tool_name="tier_two_decision",
        tool_schema=TIER_TWO_SCHEMA,
        tool_description="Record the deep-review decision.",
        model=model,
    )


DEADLOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "decision_datetime": {"type": "string", "description": "ISO 8601 datetime Control Tower is choosing to resolve the deadlock."},
        "reasoning": {"type": "string"},
    },
    "required": ["decision_datetime", "reasoning"],
}

DEADLOCK_SYSTEM = """You are Control Tower breaking a scheduling deadlock
between the Task Agent and Calendar Agent after they failed to converge in
the allotted negotiation rounds. Weigh both sides' stated reasoning and pick
one datetime. Your decision is final for this round of the system — explain
briefly why you sided the way you did."""


def break_deadlock(client, task_position: dict, calendar_position: dict, round_history: list[dict], model: str | None = None) -> dict:
    user_content = (
        f"Task Agent's most recent proposal: {task_position}\n"
        f"Calendar Agent's most recent position: {calendar_position}\n"
        f"Full negotiation history: {round_history}\n\n"
        "Break the deadlock using the break_deadlock tool."
    )
    return structured_call(
        client,
        system=DEADLOCK_SYSTEM,
        user_content=user_content,
        tool_name="break_deadlock",
        tool_schema=DEADLOCK_SCHEMA,
        tool_description="Record the deadlock-breaking decision.",
        model=model,
    )


CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_correction": {"type": "boolean"},
        "correction_note": {"type": ["string", "null"], "description": "What School Agent must fix, if needs_correction is true."},
    },
    "required": ["needs_correction", "correction_note"],
}

CORRECTION_SYSTEM = """You are Control Tower reviewing the School Agent's
classification of an email for accuracy before anything downstream acts on
it. Flag a correction only if the classification is actually wrong or
missing something material (wrong category, missed date, wrong urgency
signal) — not for stylistic preference."""


def check_classification(client, classification: dict, email_summary: str, model: str | None = None) -> dict:
    """Independent QC pass on School Agent's output. If needs_correction is
    true, the caller (graph/build_graph.py) sends correction_note back to
    school_agent.apply_control_tower_correction AND invalidates/re-runs any
    Task Agent proposal already built from the stale classification — that
    propagation is Control Tower's state-consistency responsibility, not an
    optional side effect."""
    user_content = (
        f"Original email summary:\n{email_summary}\n\n"
        f"School Agent's classification:\n{classification}\n\n"
        "Check it using the check_classification tool."
    )
    return structured_call(
        client,
        system=CORRECTION_SYSTEM,
        user_content=user_content,
        tool_name="check_classification",
        tool_schema=CORRECTION_SCHEMA,
        tool_description="Record whether the classification needs correction.",
        model=model,
    )

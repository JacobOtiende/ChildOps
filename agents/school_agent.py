"""
School Agent: reads one school email and classifies it. Nothing more —
per the design, urgency/importance scoring and action proposal belong to
the Task Agent, and School Agent should stay a clean extraction/classification
step so Control Tower can correct *just* this step without re-running
downstream reasoning it didn't need to touch.
"""
from __future__ import annotations

from agents.llm import structured_call

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["homework", "event", "health", "deadline", "supplies", "announcement", "other"],
        },
        "summary": {"type": "string", "description": "One or two sentence plain-language summary of what this email is about."},
        "extracted_date": {
            "type": ["string", "null"],
            "description": "ISO 8601 date (YYYY-MM-DD) this item concerns, e.g. a due date or event date. Null if none stated.",
        },
        "requires_calendar_event": {"type": "boolean"},
        "requires_email_response": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "category",
        "summary",
        "extracted_date",
        "requires_calendar_event",
        "requires_email_response",
        "confidence",
    ],
}

SYSTEM_PROMPT = """You are the School Communications Agent in a household automation system.
Your only job is to read one school-related email and classify it accurately.
Do not propose actions, do not draft replies, do not guess urgency — that is
another agent's job. Extract only what the email actually states; if a date
or requirement isn't explicit, say so via low confidence rather than inferring."""


def classify_email(client, subject: str, body: str, sender: str, model: str | None = None) -> dict:
    user_content = (
        f"From: {sender}\nSubject: {subject}\n\nBody:\n{body}\n\n"
        "Classify this email using the classify_school_email tool."
    )
    return structured_call(
        client,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="classify_school_email",
        tool_schema=CLASSIFY_SCHEMA,
        tool_description="Record the classification of a school email.",
        model=model,
    )


def apply_control_tower_correction(client, original_classification: dict, correction_note: str, model: str | None = None) -> dict:
    """Re-run classification with Control Tower's correction note folded in.
    This is the fix for the race condition flagged in design review: any
    caller that receives a corrected classification is expected to treat the
    previous one as invalid and re-derive anything built from it (see
    graph/build_graph.py: correction triggers a re-propose, not a silent
    overwrite)."""
    user_content = (
        f"Your previous classification was:\n{original_classification}\n\n"
        f"Control Tower flagged this correction:\n{correction_note}\n\n"
        "Re-classify using the classify_school_email tool, incorporating the correction."
    )
    return structured_call(
        client,
        system=SYSTEM_PROMPT,
        user_content=user_content,
        tool_name="classify_school_email",
        tool_schema=CLASSIFY_SCHEMA,
        tool_description="Record the corrected classification of a school email.",
        model=model,
    )

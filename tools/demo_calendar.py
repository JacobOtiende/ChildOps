"""
An in-memory calendar with the same call surface as the real Google Calendar
service object (.events().list/insert/patch().execute()), used only in
CHILDOPS_MODE=demo so you can see real LLM reasoning end to end without
first setting up Google OAuth. Swap for auth.google_auth.build_calendar_service
to go live — no other code changes needed, since tools/calendar_tool.py only
calls this generic surface.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta


def _naive(iso: str) -> datetime:
    """Parse an ISO 8601 datetime and strip any timezone offset. This
    in-memory calendar only needs relative ordering for conflict-checking,
    not absolute timezone correctness, but the LLM doesn't consistently
    return offset-aware vs. offset-naive datetimes across calls -- comparing
    one of each raises TypeError, so normalize both sides to naive here."""
    dt = datetime.fromisoformat(iso)
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _EventsResource:
    def __init__(self):
        self._events: dict[str, dict] = {}

    def list(self, calendarId, timeMin, timeMax, singleEvents=True, orderBy="startTime"):
        start = _naive(timeMin)
        end = _naive(timeMax)
        items = []
        for event_id, event in self._events.items():
            ev_start = _naive(event["start"]["dateTime"])
            ev_end = _naive(event["end"]["dateTime"])
            if ev_start < end and ev_end > start:
                items.append({**event, "id": event_id})
        return _Exec({"items": items})

    def insert(self, calendarId, body):
        event_id = str(uuid.uuid4())[:8]
        self._events[event_id] = body
        return _Exec({"id": event_id})

    def patch(self, calendarId, eventId, body):
        self._events[eventId].update(body)
        return _Exec({})


class InMemoryCalendarService:
    """Seed with a few pre-existing events so the negotiation/conflict logic
    has something real to react to in demo mode."""

    def __init__(self, seed_events: list[dict] | None = None):
        self._resource = _EventsResource()
        for event in seed_events or []:
            self._resource.insert("primary", event)

    def events(self):
        return self._resource


def default_seed_events(today: datetime) -> list[dict]:
    """A standing meeting and a pickup block, so at least one demo email
    (the pediatric appointment) actually collides with something and forces
    the negotiation/deadlock path to run, not just the accept path."""
    standing_meeting = today.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=6)
    pickup = today.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=6)
    return [
        {
            "summary": "Standing team meeting",
            "start": {"dateTime": standing_meeting.isoformat()},
            "end": {"dateTime": (standing_meeting + timedelta(hours=1)).isoformat()},
        },
        {
            "summary": "School pickup block",
            "start": {"dateTime": pickup.isoformat()},
            "end": {"dateTime": (pickup + timedelta(hours=1)).isoformat()},
        },
    ]

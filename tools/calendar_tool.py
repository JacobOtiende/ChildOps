"""
Real Google Calendar API calls for the Calendar Agent.

Three tools, matching the schemas discussed in design: check_conflict,
create_event, propose_alternates. These are the functions the Calendar
Agent's LLM call is bound to via OpenAI tool-use — the model decides
which of these to call and with what arguments, this module just executes
the real API request once it does.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CalendarEvent:
    event_id: str
    title: str
    start: str  # ISO 8601
    end: str  # ISO 8601


def check_conflict(calendar_service, calendar_id: str, start_iso: str, end_iso: str) -> list[CalendarEvent]:
    """Return any existing events overlapping [start_iso, end_iso)."""
    response = (
        calendar_service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    conflicts = []
    for item in response.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        end = item["end"].get("dateTime", item["end"].get("date"))
        conflicts.append(CalendarEvent(event_id=item["id"], title=item.get("summary", "(untitled)"), start=start, end=end))
    return conflicts


def create_event(
    calendar_service,
    calendar_id: str,
    title: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    source_agent: str = "unknown",
) -> str:
    """Create a real calendar event and return its event ID. `source_agent`
    is stamped into the description so a human looking at their calendar can
    see which agent proposed it and why."""
    body = {
        "summary": title,
        "description": f"{description}\n\n[Created by ChildOps: {source_agent}]".strip(),
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    created = calendar_service.events().insert(calendarId=calendar_id, body=body).execute()
    return created["id"]


def reschedule_event(calendar_service, calendar_id: str, event_id: str, new_start_iso: str, new_end_iso: str) -> None:
    calendar_service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body={"start": {"dateTime": new_start_iso}, "end": {"dateTime": new_end_iso}},
    ).execute()


def propose_alternates(
    calendar_service,
    calendar_id: str,
    desired_start_iso: str,
    duration_minutes: int,
    search_window_days: int = 5,
    earliest_hour: int = 8,
    latest_hour: int = 18,
    blocked_weekdays: tuple[int, ...] = (),  # 0=Monday ... 6=Sunday
    max_candidates: int = 3,
) -> list[str]:
    """Real conflict-aware slot search: walks forward hour by hour from the
    desired time, across search_window_days, skipping conflicts and blocked
    hours/weekdays, and returns up to max_candidates free ISO start times.

    This is what the Calendar Agent calls when create_event hits a conflict —
    the autonomous-recovery step from the design, not a scripted fallback.
    """
    start = datetime.fromisoformat(desired_start_iso)
    duration = timedelta(minutes=duration_minutes)
    window_end = start + timedelta(days=search_window_days)

    candidates: list[str] = []
    cursor = start
    while cursor < window_end and len(candidates) < max_candidates:
        if cursor.weekday() not in blocked_weekdays and earliest_hour <= cursor.hour < latest_hour:
            candidate_end = cursor + duration
            conflicts = check_conflict(
                calendar_service,
                calendar_id,
                cursor.isoformat(),
                candidate_end.isoformat(),
            )
            if not conflicts:
                candidates.append(cursor.isoformat())
        cursor += timedelta(hours=1)

    return candidates

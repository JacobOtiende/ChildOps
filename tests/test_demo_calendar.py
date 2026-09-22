"""
Regression coverage for the timezone-naive/aware crash in demo_calendar.py:
the LLM doesn't consistently return offset-aware vs. offset-naive ISO
datetimes across calls, and comparing one of each used to raise TypeError.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.demo_calendar import InMemoryCalendarService
from tools.calendar_tool import check_conflict


def test_conflict_check_handles_mixed_naive_and_aware_datetimes():
    # Seed event stored naive (as default_seed_events produces).
    service = InMemoryCalendarService(
        seed_events=[
            {
                "summary": "Standing meeting",
                "start": {"dateTime": "2026-09-24T09:00:00"},
                "end": {"dateTime": "2026-09-24T10:00:00"},
            }
        ]
    )

    # Query window offset-aware (as an LLM-proposed datetime might be).
    conflicts = check_conflict(service, "primary", "2026-09-24T09:30:00-05:00", "2026-09-24T10:30:00-05:00")
    assert len(conflicts) == 1
    assert conflicts[0].title == "Standing meeting"

    # No overlap -> no conflict, still without crashing on mixed tz-awareness.
    no_conflicts = check_conflict(service, "primary", "2026-09-25T09:00:00+00:00", "2026-09-25T10:00:00+00:00")
    assert no_conflicts == []

"""
Verifies the GRAPH's branching logic, not the LLM's judgment (that would
need live calls and wouldn't be deterministic). Every scenario scripts
exactly the tool responses each round should produce and asserts on the
resulting state — including that no node fires more times than expected,
which is what would happen if the defer-based join on decide_action were
broken and it ran once per incoming branch instead of once per graph run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.build_graph import Deps, build_graph
from tests.fakes import FakeApprovalQueue, FakeCalendarService, ScriptedClient

TODAY = "2026-09-16"


def make_deps(script: dict, round_cap: int = 2, existing_events=None):
    client = ScriptedClient(script)
    calendar_service = FakeCalendarService(existing_events)
    approval_queue = FakeApprovalQueue()
    deps = Deps(
        client=client,
        calendar_service=calendar_service,
        calendar_id="primary",
        approval_queue=approval_queue,
        negotiation_round_cap=round_cap,
        model="fake-model",
        today_iso=lambda: TODAY,
    )
    return deps, client, calendar_service, approval_queue


def base_email():
    return {
        "email_sender": "newsletter@ourschool.edu",
        "email_subject": "This week at Lincoln Elementary",
        "email_body": "Science fair is next Thursday at 9am in the gym.",
    }


def test_happy_path_calendar_event_round_one_accept():
    script = {
        "classify_school_email": [
            {
                "category": "event",
                "summary": "Science fair next Thursday",
                "extracted_date": "2026-09-24",
                "requires_calendar_event": True,
                "requires_email_response": False,
                "confidence": 0.9,
            }
        ],
        "check_classification": [{"needs_correction": False, "correction_note": None}],
        "propose_task_action": [
            {
                "urgency_score": 3,
                "importance_score": 3,
                "proposed_action": "create_calendar_event",
                "needs_calendar": True,
                "needs_email": False,
                "proposed_title": "Science Fair",
                "proposed_datetime": "2026-09-24T09:00:00",
                "rationale": "Event date is explicitly stated.",
            }
        ],
        "tier_one_triage": [{"flagged": False, "flag_reason": None}],
        "negotiate_schedule": [{"position": "accept", "counter_datetime": None, "reasoning": "No conflicts found."}],
    }
    deps, client, calendar_service, _ = make_deps(script)
    graph = build_graph(deps)

    result = graph.invoke(base_email())

    assert result["final_action"] == "event_created"
    assert result["negotiation_round"] == 1
    assert "deadlock_decision" not in result or result["deadlock_decision"] is None
    # If decide_action had double-fired (a broken join), this would be 2.
    assert len(calendar_service._events.created) == 1
    assert calendar_service._events.created[0]["start"]["dateTime"] == "2026-09-24T09:00:00"


def test_email_response_path_queues_for_approval_never_auto_sends():
    script = {
        "classify_school_email": [
            {
                "category": "deadline",
                "summary": "Doctor's note required for absence",
                "extracted_date": None,
                "requires_calendar_event": False,
                "requires_email_response": True,
                "confidence": 0.85,
            }
        ],
        "check_classification": [{"needs_correction": False, "correction_note": None}],
        "propose_task_action": [
            {
                "urgency_score": 4,
                "importance_score": 4,
                "proposed_action": "draft_email_response",
                "needs_calendar": False,
                "needs_email": True,
                "proposed_title": "",
                "proposed_datetime": None,
                "rationale": "School requires written acknowledgment.",
            }
        ],
        "tier_one_triage": [{"flagged": False, "flag_reason": None}],
        "tier_two_decision": [{"approved": True, "corrections": None, "reasoning": "Appropriate and relevant."}],
        "draft_email": [{"to": "frontdesk@ourschool.edu", "subject": "Re: absence note", "body": "Attached is the note."}],
    }
    deps, client, calendar_service, approval_queue = make_deps(script)
    graph = build_graph(deps)

    result = graph.invoke(base_email())

    assert result["final_action"] == "email_queued_for_approval"
    assert result["approval_id"] in approval_queue.pending
    # Never auto-sent: nothing in this test ever calls anything but enqueue.
    assert len(calendar_service._events.created) == 0


def test_control_tower_correction_replaces_stale_classification():
    script = {
        "classify_school_email": [
            # First pass: School Agent gets it wrong.
            {
                "category": "other",
                "summary": "Some kind of school item",
                "extracted_date": None,
                "requires_calendar_event": False,
                "requires_email_response": False,
                "confidence": 0.4,
            },
            # After Control Tower's correction note, the corrected pass.
            {
                "category": "deadline",
                "summary": "Math homework due Monday",
                "extracted_date": "2026-09-21",
                "requires_calendar_event": False,
                "requires_email_response": False,
                "confidence": 0.9,
            },
        ],
        "check_classification": [
            {"needs_correction": True, "correction_note": "This is a homework deadline, not 'other'."},
            {"needs_correction": False, "correction_note": None},
        ],
        "propose_task_action": [
            {
                "urgency_score": 2,
                "importance_score": 2,
                "proposed_action": "log_only",
                "needs_calendar": False,
                "needs_email": False,
                "proposed_title": "",
                "proposed_datetime": None,
                "rationale": "Routine homework reminder already tracked.",
            }
        ],
        "tier_one_triage": [{"flagged": False, "flag_reason": None}],
    }
    deps, client, calendar_service, approval_queue = make_deps(script)
    graph = build_graph(deps)

    result = graph.invoke(base_email())

    assert result["classification_correction_rounds"] == 1
    # Task Agent must only ever have seen the corrected classification.
    assert result["classification"]["category"] == "deadline"
    assert result["final_action"] == "logged_only"
    assert len(calendar_service._events.created) == 0
    assert len(approval_queue.pending) == 0


def test_negotiation_escalates_to_control_tower_after_round_cap():
    script = {
        "classify_school_email": [
            {
                "category": "health",
                "summary": "Doctor note required, appointment needed",
                "extracted_date": "2026-09-22",
                "requires_calendar_event": True,
                "requires_email_response": False,
                "confidence": 0.9,
            }
        ],
        "check_classification": [{"needs_correction": False, "correction_note": None}],
        "propose_task_action": [
            {
                "urgency_score": 4,
                "importance_score": 4,
                "proposed_action": "create_calendar_event",
                "needs_calendar": True,
                "needs_email": False,
                "proposed_title": "Pediatric appointment",
                "proposed_datetime": "2026-09-22T09:00:00",
                "rationale": "Doctor's note required soon.",
            }
        ],
        "tier_one_triage": [{"flagged": False, "flag_reason": None}],
        "negotiate_schedule": [
            {"position": "counter", "counter_datetime": "2026-09-22T14:00:00", "reasoning": "9am conflicts with a standing meeting."},
            {"position": "counter", "counter_datetime": "2026-09-23T09:00:00", "reasoning": "2pm still conflicts with pickup."},
        ],
        "reconsider_counter": [{"accept_counter": False, "reasoning": "Needs to happen before the deadline, holding firm."}],
        "break_deadlock": [{"decision_datetime": "2026-09-22T16:00:00", "reasoning": "Splitting the difference, still before the deadline."}],
    }
    deps, client, calendar_service, _ = make_deps(script, round_cap=2)
    graph = build_graph(deps)

    result = graph.invoke(base_email())

    assert result["negotiation_round"] == 2
    assert result["deadlock_decision"]["decision_datetime"] == "2026-09-22T16:00:00"
    assert result["final_action"] == "event_created"
    assert len(calendar_service._events.created) == 1
    assert calendar_service._events.created[0]["start"]["dateTime"] == "2026-09-22T16:00:00"


def test_negotiation_converges_when_task_agent_accepts_counter():
    script = {
        "classify_school_email": [
            {
                "category": "event",
                "summary": "PTA meeting Tuesday",
                "extracted_date": "2026-09-22",
                "requires_calendar_event": True,
                "requires_email_response": False,
                "confidence": 0.9,
            }
        ],
        "check_classification": [{"needs_correction": False, "correction_note": None}],
        "propose_task_action": [
            {
                "urgency_score": 2,
                "importance_score": 2,
                "proposed_action": "create_calendar_event",
                "needs_calendar": True,
                "needs_email": False,
                "proposed_title": "PTA meeting",
                "proposed_datetime": "2026-09-22T18:00:00",
                "rationale": "Optional but on the calendar.",
            }
        ],
        "tier_one_triage": [{"flagged": False, "flag_reason": None}],
        "negotiate_schedule": [
            {"position": "counter", "counter_datetime": "2026-09-22T19:00:00", "reasoning": "6pm conflicts with dinner block."},
        ],
        "reconsider_counter": [{"accept_counter": True, "reasoning": "Low importance, 7pm works fine instead."}],
    }
    deps, client, calendar_service, _ = make_deps(script, round_cap=2)
    graph = build_graph(deps)

    result = graph.invoke(base_email())

    assert result["negotiation_round"] == 1
    assert result.get("deadlock_decision") is None
    assert result["final_action"] == "event_created"
    assert calendar_service._events.created[0]["start"]["dateTime"] == "2026-09-22T19:00:00"

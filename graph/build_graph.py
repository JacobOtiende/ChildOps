"""
LangGraph wiring for the ChildOps vertical slice: School -> Task -> (Control
Tower approval || Calendar negotiation) -> decide_action.

This is the piece that turns the design doc's prose ("task agent checks with
control tower... at the same time... checks with calendar agent... waits for
both") into an actual graph with real branching, a bounded negotiation loop,
and a deadlock escalation path — not a fixed five-step pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from langgraph.graph import StateGraph, START, END

from agents import calendar_agent, control_tower, school_agent, task_agent
from graph.state import ChildOpsState
from tools.calendar_tool import create_event

DEFAULT_EVENT_DURATION_MINUTES = 60
MAX_CLASSIFICATION_CORRECTIONS = 1


@dataclass
class Deps:
    """Everything a node needs, injected once at graph-build time so nodes
    stay pure functions of (deps, state) and are trivially testable with
    fakes — see tests/test_graph_flow.py."""

    client: Any  # openai.OpenAI, or a fake with the same .chat.completions.create surface
    calendar_service: Any  # real googleapiclient service, or a fake
    calendar_id: str
    approval_queue: Any  # approvals.approval_queue.ApprovalQueue
    negotiation_round_cap: int = 2
    model: str | None = None
    today_iso: Callable[[], str] = field(default=lambda: datetime.now().date().isoformat())


def _plus_minutes(iso: str, minutes: int) -> str:
    return (datetime.fromisoformat(iso) + timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def make_classify_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        classification = school_agent.classify_email(
            deps.client, state["email_subject"], state["email_body"], state["email_sender"], model=deps.model
        )
        return {"classification": classification, "classification_correction_rounds": 0}

    return node


def make_classification_qc_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        email_summary = f"Subject: {state['email_subject']}\nBody: {state['email_body']}"
        qc = control_tower.check_classification(deps.client, state["classification"], email_summary, model=deps.model)
        return {"classification_qc": qc}

    return node


def route_after_qc(state: ChildOpsState) -> str:
    qc = state["classification_qc"]
    rounds = state.get("classification_correction_rounds", 0)
    if qc.get("needs_correction") and rounds < MAX_CLASSIFICATION_CORRECTIONS:
        return "correct"
    return "proceed"


def make_correct_classification_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        note = state["classification_qc"].get("correction_note") or ""
        corrected = school_agent.apply_control_tower_correction(deps.client, state["classification"], note, model=deps.model)
        rounds = state.get("classification_correction_rounds", 0) + 1
        # This is the race-condition fix from design review: the corrected
        # classification REPLACES the old one before anything downstream
        # (Task Agent) ever sees it, instead of Control Tower silently
        # patching School Agent while a stale proposal is already in flight.
        return {"classification": corrected, "classification_correction_rounds": rounds}

    return node


def make_task_propose_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        proposal = task_agent.score_and_propose(deps.client, state["classification"], deps.today_iso(), model=deps.model)
        return {"task_proposal": proposal, "negotiation_round": 0, "negotiation_history": [], "agreed_datetime": None}

    return node


def _describe_proposal(proposal: dict) -> str:
    """Human-readable description for Control Tower review, deliberately
    omitting fields the proposed action doesn't use (proposed_title/
    proposed_datetime only mean anything for needs_calendar) instead of
    dumping the raw proposal dict, so tier-one doesn't flag them as
    "missing" when they were never applicable in the first place."""
    parts = [
        f"Proposed action: {proposal['proposed_action']}",
        f"Urgency: {proposal['urgency_score']}/5, Importance: {proposal['importance_score']}/5",
        f"Rationale: {proposal['rationale']}",
    ]
    if proposal.get("needs_calendar"):
        parts.append(f"Calendar event: '{proposal.get('proposed_title')}' at {proposal.get('proposed_datetime')}")
    if proposal.get("needs_email"):
        parts.append("This will draft an email reply (never auto-sent; requires explicit approval).")
    return "\n".join(parts)


def make_control_tower_approve_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        proposal = state["task_proposal"]
        description = _describe_proposal(proposal)
        tier_one = control_tower.tier_one_review(deps.client, description, model=deps.model)
        tier_two = None
        approved = True
        # Tiering per design review: only a tier-one flag OR an action with
        # external consequence (an outbound email) earns the deeper pass.
        if tier_one.get("flagged") or proposal.get("needs_email"):
            history = (
                f"Original email from {state['email_sender']}, subject: {state['email_subject']}\n"
                f"Body: {state['email_body']}\n\n"
                f"School Agent classification: {state['classification']}"
            )
            tier_two = control_tower.tier_two_review(
                deps.client, description, tier_one.get("flag_reason"), history=history, model=deps.model
            )
            approved = bool(tier_two.get("approved"))
        return {
            "control_tower_tier_one": tier_one,
            "control_tower_tier_two": tier_two,
            "proposal_approved": approved,
        }

    return node


def make_calendar_negotiate_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        proposal = state["task_proposal"]
        if not proposal.get("needs_calendar"):
            return {
                "calendar_position": {"position": "accept", "reasoning": "No calendar event required."},
                "agreed_datetime": None,
            }
        if not proposal.get("proposed_datetime"):
            # Task Agent flagged needs_calendar but gave no concrete datetime
            # to negotiate over (e.g. an email covering several dates at
            # once) -- nothing to check for conflict, so skip negotiation
            # rather than crash. decide_action logs this as an error.
            return {
                "calendar_position": {
                    "position": "accept",
                    "reasoning": "Task Agent did not provide a concrete datetime to negotiate.",
                },
                "agreed_datetime": None,
            }

        round_number = state.get("negotiation_round", 0) + 1
        history = list(state.get("negotiation_history", []))
        position = calendar_agent.evaluate_proposal(
            deps.client,
            deps.calendar_service,
            deps.calendar_id,
            proposed_title=proposal["proposed_title"],
            proposed_datetime=proposal["proposed_datetime"],
            duration_minutes=DEFAULT_EVENT_DURATION_MINUTES,
            urgency_score=proposal["urgency_score"],
            importance_score=proposal["importance_score"],
            round_number=round_number,
            prior_rounds=history,
            model=deps.model,
        )
        history.append({"round": round_number, "calendar_position": position})
        updates: dict = {
            "calendar_position": position,
            "negotiation_round": round_number,
            "negotiation_history": history,
        }
        if position["position"] == "accept":
            updates["agreed_datetime"] = proposal["proposed_datetime"]
        return updates

    return node


def make_route_after_calendar(deps: Deps):
    def route(state: ChildOpsState) -> str:
        proposal = state["task_proposal"]
        if not proposal.get("needs_calendar"):
            return "join"
        position = state["calendar_position"]
        if position["position"] == "accept":
            return "join"
        round_number = state.get("negotiation_round", 0)
        if round_number >= deps.negotiation_round_cap:
            return "deadlock"
        return "reconsider"

    return route


def make_task_reconsider_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        proposal = state["task_proposal"]
        position = state["calendar_position"]
        counter_dt = position.get("counter_datetime") or proposal["proposed_datetime"]
        result = task_agent.reconsider_counter(
            deps.client,
            proposed_title=proposal["proposed_title"],
            urgency_score=proposal["urgency_score"],
            importance_score=proposal["importance_score"],
            counter_datetime=counter_dt,
            calendar_reasoning=position["reasoning"],
            model=deps.model,
        )
        history = list(state.get("negotiation_history", []))
        if history:
            history[-1] = {**history[-1], "task_reconsider": result}
        updates: dict = {"negotiation_history": history}
        if result.get("accept_counter"):
            updates["agreed_datetime"] = counter_dt
        return updates

    return node


def make_route_after_reconsider(deps: Deps):
    def route(state: ChildOpsState) -> str:
        history = state.get("negotiation_history", [])
        last = history[-1] if history else {}
        if last.get("task_reconsider", {}).get("accept_counter"):
            return "join"
        round_number = state.get("negotiation_round", 0)
        if round_number >= deps.negotiation_round_cap:
            return "deadlock"
        return "renegotiate"

    return route


def make_control_tower_deadlock_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        decision = control_tower.break_deadlock(
            deps.client,
            state["task_proposal"],
            state["calendar_position"],
            state.get("negotiation_history", []),
            model=deps.model,
        )
        return {"deadlock_decision": decision, "agreed_datetime": decision["decision_datetime"]}

    return node


def make_decide_action_node(deps: Deps):
    def node(state: ChildOpsState) -> dict:
        proposal = state["task_proposal"]
        errors = list(state.get("errors", []))
        updates: dict = {}

        if not state.get("proposal_approved", True):
            return {"final_action": "rejected", "errors": errors}

        if proposal.get("needs_calendar"):
            agreed = state.get("agreed_datetime") or proposal.get("proposed_datetime")
            if not agreed:
                errors.append("needs_calendar was true but no concrete datetime was ever proposed; no event created")
            else:
                try:
                    event_id = create_event(
                        deps.calendar_service,
                        deps.calendar_id,
                        proposal["proposed_title"],
                        agreed,
                        _plus_minutes(agreed, DEFAULT_EVENT_DURATION_MINUTES),
                        description=proposal.get("rationale", ""),
                        source_agent="Task Agent + Calendar Agent (ChildOps)",
                    )
                    updates["event_id"] = event_id
                except Exception as exc:  # real API calls can genuinely fail
                    errors.append(f"calendar create_event failed: {exc}")

        if proposal.get("needs_email"):
            draft = task_agent.draft_email_response(deps.client, state["classification"], state["email_sender"], model=deps.model)
            approval_id = deps.approval_queue.enqueue(draft)
            updates["draft_email"] = draft
            updates["approval_id"] = approval_id

        if updates.get("event_id") and updates.get("approval_id"):
            updates["final_action"] = "event_created_and_email_queued_for_approval"
        elif updates.get("event_id"):
            updates["final_action"] = "event_created"
        elif updates.get("approval_id"):
            updates["final_action"] = "email_queued_for_approval"
        else:
            updates["final_action"] = "logged_only"

        updates["errors"] = errors
        return updates

    return node


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph(deps: Deps):
    graph = StateGraph(ChildOpsState)

    graph.add_node("classify", make_classify_node(deps))
    graph.add_node("classification_qc", make_classification_qc_node(deps))
    graph.add_node("correct_classification", make_correct_classification_node(deps))
    graph.add_node("task_propose", make_task_propose_node(deps))
    graph.add_node("control_tower_approve", make_control_tower_approve_node(deps))
    graph.add_node("calendar_negotiate", make_calendar_negotiate_node(deps))
    graph.add_node("task_reconsider", make_task_reconsider_node(deps))
    graph.add_node("control_tower_deadlock", make_control_tower_deadlock_node(deps))
    # defer=True: this node waits until every other in-flight branch of the
    # current run has finished before it executes, so the variable-length
    # calendar negotiation loop and the fixed-length Control Tower approval
    # check both land here exactly once, however many rounds negotiation took.
    graph.add_node("decide_action", make_decide_action_node(deps), defer=True)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "classification_qc")
    graph.add_conditional_edges(
        "classification_qc", route_after_qc, {"correct": "correct_classification", "proceed": "task_propose"}
    )
    graph.add_edge("correct_classification", "classification_qc")

    # Fan-out: Task Agent's proposal is consulted with Control Tower and the
    # Calendar Agent independently and concurrently.
    graph.add_edge("task_propose", "control_tower_approve")
    graph.add_edge("task_propose", "calendar_negotiate")

    graph.add_conditional_edges(
        "calendar_negotiate",
        make_route_after_calendar(deps),
        {"join": "decide_action", "reconsider": "task_reconsider", "deadlock": "control_tower_deadlock"},
    )
    graph.add_conditional_edges(
        "task_reconsider",
        make_route_after_reconsider(deps),
        {"join": "decide_action", "renegotiate": "calendar_negotiate", "deadlock": "control_tower_deadlock"},
    )
    graph.add_edge("control_tower_deadlock", "decide_action")
    graph.add_edge("control_tower_approve", "decide_action")

    graph.add_edge("decide_action", END)

    return graph.compile()

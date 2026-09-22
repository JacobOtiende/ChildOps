"""
Shared state schema passed between every node in the ChildOps graph.

This is the data contract flagged as missing in design review — every
"trigger", "proposed action", and "compromise" the agents pass around now
has an actual field list instead of being narrated prose.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class ChildOpsState(TypedDict, total=False):
    # --- Ingestion ---
    email_sender: str
    email_subject: str
    email_body: str

    # --- School Agent output (the "trigger" payload) ---
    classification: dict[str, Any]
    classification_correction_rounds: int  # bounds the correction loop

    # --- Control Tower classification QC ---
    classification_qc: dict[str, Any]

    # --- Task Agent output (the "proposed action" payload) ---
    task_proposal: dict[str, Any]

    # --- Control Tower approval of the proposal ---
    control_tower_tier_one: dict[str, Any]
    control_tower_tier_two: Optional[dict[str, Any]]
    proposal_approved: bool
    task_approval_correction_rounds: int  # bounds the reject -> revise -> re-review loop

    # --- Calendar negotiation ---
    negotiation_round: int
    calendar_position: dict[str, Any]
    negotiation_history: list[dict[str, Any]]
    agreed_datetime: Optional[str]
    deadlock_decision: Optional[dict[str, Any]]

    # --- Final outcome ---
    final_action: str  # "event_created" | "email_queued_for_approval" | "logged_only" | "rejected"
    event_id: Optional[str]
    draft_email: Optional[dict[str, Any]]
    approval_id: Optional[str]

    # --- Bookkeeping ---
    errors: list[str]

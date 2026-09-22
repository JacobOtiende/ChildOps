"""
The "red alert that keeps popping until you respond" mechanism from the
design: a persistent, disk-backed queue of drafted-but-unsent emails, plus
a reviewer loop that keeps re-surfacing anything still pending.

A real deployment would push this as a mobile notification; that needs a
notification service and a always-on backend, which is out of scope for a
course project. A polling CLI loop that won't let you ignore a pending
approval is the honest, buildable version of the same guarantee: nothing
gets sent without you seeing it, and it won't let you forget it's waiting.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable, Optional


class ApprovalQueue:
    def __init__(self, path: str = "./data/pending_approvals.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            self._save({})

    def _load(self) -> dict[str, Any]:
        with open(self.path) as f:
            return json.load(f)

    def _save(self, data: dict[str, Any]) -> None:
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def enqueue(self, draft: dict[str, Any]) -> str:
        data = self._load()
        approval_id = str(uuid.uuid4())
        data[approval_id] = {"draft": draft, "status": "pending"}
        self._save(data)
        return approval_id

    def list_pending(self) -> dict[str, Any]:
        data = self._load()
        return {k: v for k, v in data.items() if v["status"] == "pending"}

    def approve(self, approval_id: str, edited_body: str | None = None) -> None:
        data = self._load()
        if approval_id not in data:
            raise KeyError(f"No pending approval with id {approval_id}")
        if edited_body is not None:
            data[approval_id]["draft"]["body"] = edited_body
        data[approval_id]["status"] = "approved"
        self._save(data)

    def reject(self, approval_id: str) -> None:
        data = self._load()
        if approval_id not in data:
            raise KeyError(f"No pending approval with id {approval_id}")
        data[approval_id]["status"] = "rejected"
        self._save(data)

    def status(self, approval_id: str) -> str:
        return self._load()[approval_id]["status"]


def run_red_alert_loop(
    queue: ApprovalQueue,
    poll_seconds: int = 10,
    max_polls: int | None = None,
    send_fn: Optional[Callable[[dict[str, Any]], None]] = None,
) -> None:
    """Keeps re-printing every pending draft until none remain, prompting
    for approve/edit/reject each pass. max_polls is for tests/demos only —
    a real run leaves it None and lets this run indefinitely.

    send_fn, if given, is called with the (possibly-edited) draft dict on
    approval to actually send it -- see main.py:run_live, which wires this
    to tools.gmail_tool.send_email. Demo mode passes None since there's no
    live Gmail service to send through, the same real-calls-except-Google
    trade-off as the rest of demo mode; approval there stays a local status
    flip. The send happens BEFORE the status flips to "approved", so a
    failed send leaves the draft pending for retry instead of silently
    marking something sent that wasn't."""
    polls = 0
    while True:
        pending = queue.list_pending()
        if not pending:
            print("No pending email approvals. All clear.")
            return

        print(f"\n RED ALERT: {len(pending)} email draft(s) awaiting your review ")
        for approval_id, entry in pending.items():
            draft = entry["draft"]
            print(f"\n[{approval_id}]\nTo: {draft['to']}\nSubject: {draft['subject']}\n\n{draft['body']}\n")
            choice = input("Approve and send (a) / Edit body then send (e) / Reject (r) / Later (Enter): ").strip().lower()
            if choice == "a":
                if send_fn is not None:
                    try:
                        send_fn(draft)
                    except Exception as exc:
                        print(f"Send failed, left pending for retry: {exc}")
                        continue
                queue.approve(approval_id)
                print("Approved and sent." if send_fn is not None else "Approved — would be sent now.")
            elif choice == "e":
                new_body = input("New body: ")
                edited = {**draft, "body": new_body}
                if send_fn is not None:
                    try:
                        send_fn(edited)
                    except Exception as exc:
                        print(f"Send failed, left pending for retry: {exc}")
                        continue
                queue.approve(approval_id, edited_body=new_body)
                print("Approved with edits and sent." if send_fn is not None else "Approved with edits — would be sent now.")
            elif choice == "r":
                queue.reject(approval_id)
                print("Rejected — will not be sent.")
            # anything else: leave pending, it will alert again next pass

        polls += 1
        if max_polls is not None and polls >= max_polls:
            return
        if queue.list_pending():
            time.sleep(poll_seconds)

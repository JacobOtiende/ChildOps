"""
Verifies the real Gmail send call shape (tools/gmail_tool.send_email) and
the approval loop's send-then-flip-status wiring, without ever touching a
real network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from approvals.approval_queue import ApprovalQueue, run_red_alert_loop
from tools.gmail_tool import send_email


def test_send_email_calls_gmail_send_with_base64_raw_message():
    fake_service = MagicMock()
    fake_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-1"}

    message_id = send_email(fake_service, "frontdesk@ourschool.edu", "Re: absence note", "Attached is the note.")

    assert message_id == "msg-1"
    _, kwargs = fake_service.users.return_value.messages.return_value.send.call_args
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]


def test_approve_calls_send_fn_before_flipping_status(tmp_path):
    queue = ApprovalQueue(path=str(tmp_path / "pending.json"))
    approval_id = queue.enqueue({"to": "frontdesk@ourschool.edu", "subject": "Re: absence note", "body": "Attached."})

    sent = []
    with patch("builtins.input", side_effect=["a"]):
        run_red_alert_loop(queue, send_fn=lambda draft: sent.append(draft), max_polls=1)

    assert len(sent) == 1
    assert sent[0]["to"] == "frontdesk@ourschool.edu"
    assert queue.status(approval_id) == "approved"


def test_failed_send_leaves_draft_pending_for_retry(tmp_path):
    queue = ApprovalQueue(path=str(tmp_path / "pending.json"))
    approval_id = queue.enqueue({"to": "frontdesk@ourschool.edu", "subject": "Re: absence note", "body": "Attached."})

    def failing_send(draft):
        raise RuntimeError("network down")

    with patch("builtins.input", side_effect=["a"]):
        run_red_alert_loop(queue, send_fn=failing_send, max_polls=1)

    assert queue.status(approval_id) == "pending"

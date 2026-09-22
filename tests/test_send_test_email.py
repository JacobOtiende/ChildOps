"""
Verifies the test-email sender's message construction and SMTP call shape
without ever touching a real network — these tests should never require
credentials or connectivity."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testing.send_test_email import build_message, find_scenario, load_scenarios, send_via_smtp


def test_build_message_sets_realistic_headers():
    msg = build_message(
        sender_email="throwaway.tester@gmail.com",
        recipient_email="fake.parent.account@gmail.com",
        subject="Doctor's note required",
        body="Please submit documentation.",
        display_from="Lincoln Elementary Front Office",
    )
    assert msg["To"] == "fake.parent.account@gmail.com"
    assert msg["Subject"] == "Doctor's note required"
    # Display name can read like the school; the actual address must still
    # be the authenticated sender or Gmail will reject the send.
    assert "Lincoln Elementary Front Office" in msg["From"]
    assert "throwaway.tester@gmail.com" in msg["From"]
    assert msg.get_content().strip() == "Please submit documentation."


def test_load_scenarios_has_expected_ids():
    scenarios = load_scenarios()
    ids = {s["id"] for s in scenarios}
    assert {"newsletter", "doctor_note", "field_trip_reply", "ambiguous_item", "conflicting_event"} <= ids


def test_find_scenario_unknown_id_raises():
    try:
        find_scenario("does_not_exist")
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_send_via_smtp_logs_in_and_sends_message():
    msg = build_message("sender@gmail.com", "recipient@gmail.com", "Subject", "Body")

    fake_server = MagicMock()
    fake_smtp_cm = MagicMock()
    fake_smtp_cm.__enter__.return_value = fake_server
    fake_smtp_cm.__exit__.return_value = False

    with patch("testing.send_test_email.smtplib.SMTP_SSL", return_value=fake_smtp_cm) as smtp_ctor:
        send_via_smtp(msg, "sender@gmail.com", "app-password-123")

    smtp_ctor.assert_called_once_with("smtp.gmail.com", 465)
    fake_server.login.assert_called_once_with("sender@gmail.com", "app-password-123")
    fake_server.send_message.assert_called_once_with(msg)

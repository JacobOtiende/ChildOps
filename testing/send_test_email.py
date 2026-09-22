"""
Sends REAL emails, over real SMTP, into your fake Gmail test account — so
School Agent's live Gmail polling (tools/gmail_tool.py) has something
genuine to classify instead of the in-memory demo replay.

This is a separate, throwaway SENDER account, not the account ChildOps
reads from. You need two mailboxes to test this properly: the fake
"parent" Gmail account ChildOps polls (already set up for live mode in the
main README), and a second account that plays "the school" and sends into
it. The sender doesn't have to be Gmail — any account you can get SMTP
credentials for works, since you're just relaying a message into the
recipient's real inbox. Gmail's the easy default because a free @gmail.com
account only needs an App Password (2 minutes, see README below).

Usage:
    python testing/send_test_email.py --list
    python testing/send_test_email.py --scenario doctor_note
    python testing/send_test_email.py --all --delay 20
    python testing/send_test_email.py --subject "Test" --body "Hello" --to someone@gmail.com
    python testing/send_test_email.py --scenario newsletter --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"


def load_scenarios() -> list[dict]:
    with open(SCENARIOS_PATH) as f:
        return json.load(f)


def find_scenario(scenario_id: str) -> dict:
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    raise SystemExit(f"No scenario named {scenario_id!r}. Use --list to see available scenarios.")


def build_message(
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    display_from: str | None = None,
) -> EmailMessage:
    """A real, valid RFC 5322 message. The From ADDRESS must be the
    authenticated sender account (Gmail rejects mismatches) but the display
    NAME can read like the school, e.g. 'Lincoln Elementary <you@gmail.com>' —
    plenty realistic for testing classification without needing to actually
    control a school's mail server."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((display_from or sender_email, sender_email))
    msg["To"] = recipient_email
    msg.set_content(body)
    return msg


def send_via_smtp(msg: EmailMessage, sender_email: str, app_password: str) -> None:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.send_message(msg)


def send_one(sender_email: str, app_password: str, recipient_email: str, scenario: dict, dry_run: bool) -> None:
    msg = build_message(
        sender_email,
        recipient_email,
        subject=scenario["subject"],
        body=scenario["body"],
        display_from=scenario.get("display_from"),
    )
    if dry_run:
        print(f"--- DRY RUN: would send [{scenario.get('id', 'custom')}] ---")
        print(msg)
        return
    send_via_smtp(msg, sender_email, app_password)
    print(f"Sent [{scenario.get('id', 'custom')}]: {scenario['subject']!r} -> {recipient_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="List available scenarios and exit.")
    parser.add_argument("--scenario", help="Send one predefined scenario by id.")
    parser.add_argument("--all", action="store_true", help="Send every predefined scenario in order.")
    parser.add_argument("--delay", type=float, default=15.0, help="Seconds between sends when using --all (default 15).")
    parser.add_argument("--subject", help="Custom one-off email subject (use with --body).")
    parser.add_argument("--body", help="Custom one-off email body (use with --subject).")
    parser.add_argument("--to", help="Override recipient (defaults to TEST_RECIPIENT_EMAIL).")
    parser.add_argument("--dry-run", action="store_true", help="Print the message instead of sending it.")
    args = parser.parse_args()

    if args.list:
        for scenario in load_scenarios():
            print(f"{scenario['id']:20s} {scenario['subject']}\n{'':20s} why: {scenario['why']}\n")
        return

    sender_email = os.environ.get("TEST_SENDER_EMAIL", "")
    app_password = os.environ.get("TEST_SENDER_APP_PASSWORD", "")
    recipient_email = args.to or os.environ.get("TEST_RECIPIENT_EMAIL", "")

    if not args.dry_run and not (sender_email and app_password):
        raise SystemExit(
            "TEST_SENDER_EMAIL and TEST_SENDER_APP_PASSWORD must be set in .env "
            "(or pass --dry-run to preview without sending). See README.md > "
            "'Testing against a real fake Gmail inbox'."
        )
    if not recipient_email:
        raise SystemExit("Set TEST_RECIPIENT_EMAIL in .env, or pass --to.")

    if args.subject and args.body:
        send_one(sender_email, app_password, recipient_email, {"subject": args.subject, "body": args.body, "id": "custom"}, args.dry_run)
        return

    if args.all:
        scenarios = load_scenarios()
        for i, scenario in enumerate(scenarios):
            send_one(sender_email, app_password, recipient_email, scenario, args.dry_run)
            if not args.dry_run and i < len(scenarios) - 1:
                time.sleep(args.delay)
        return

    if args.scenario:
        send_one(sender_email, app_password, recipient_email, find_scenario(args.scenario), args.dry_run)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

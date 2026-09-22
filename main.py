"""
Entry point.

    python main.py              # demo mode: sample_emails.json, in-memory calendar
    python main.py --review     # after a run, open the red-alert review loop
    CHILDOPS_MODE=live python main.py    # real Gmail polling + real Calendar

Demo mode still makes REAL OpenAI API calls (you need OPENAI_API_KEY
set) — the only thing it fakes is the Google side, so you can see genuine
agent reasoning without first doing OAuth setup. See README.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

import openai

from approvals.approval_queue import ApprovalQueue, run_red_alert_loop
from auth.google_auth import build_calendar_service, build_gmail_service
from config import load_settings
from graph.build_graph import Deps, build_graph
from tools.demo_calendar import InMemoryCalendarService, default_seed_events
from tools.gmail_tool import fetch_new_school_emails, send_email


def summarize(result: dict) -> str:
    lines = [f"  final_action: {result.get('final_action')}"]
    if result.get("classification_correction_rounds"):
        lines.append(f"  classification was corrected by Control Tower ({result['classification_correction_rounds']} round(s))")
    if result.get("task_approval_correction_rounds"):
        lines.append(f"  Task Agent's proposal was revised after Control Tower rejection ({result['task_approval_correction_rounds']} round(s))")
    if result.get("negotiation_round"):
        lines.append(f"  calendar negotiation rounds: {result['negotiation_round']}")
    if result.get("deadlock_decision"):
        lines.append(f"  Control Tower broke a scheduling deadlock: {result['deadlock_decision']['reasoning']}")
    if result.get("event_id"):
        lines.append(f"  calendar event created: {result['event_id']}")
    if result.get("approval_id"):
        lines.append(f"  email drafted, awaiting your approval: id={result['approval_id']}")
    if result.get("errors"):
        lines.append(f"  errors: {result['errors']}")
    return "\n".join(lines)


def run_demo(settings, args) -> None:
    client = openai.OpenAI(api_key=settings.openai_api_key)
    calendar_service = InMemoryCalendarService(seed_events=default_seed_events(datetime.now()))
    approval_queue = ApprovalQueue(path="./data/pending_approvals.json")

    deps = Deps(
        client=client,
        calendar_service=calendar_service,
        calendar_id="primary",
        approval_queue=approval_queue,
        negotiation_round_cap=settings.negotiation_round_cap,
        today_iso=lambda: datetime.now().date().isoformat(),
    )
    graph = build_graph(deps)

    with open("data/sample_emails.json") as f:
        emails = json.load(f)

    for i, email in enumerate(emails, start=1):
        print(f"\n=== Email {i}/{len(emails)}: {email['subject']} ===")
        result = graph.invoke(
            {
                "email_sender": email["sender"],
                "email_subject": email["subject"],
                "email_body": email["body"],
            }
        )
        print(summarize(result))

    if args.review:
        run_red_alert_loop(approval_queue)
    elif approval_queue.list_pending():
        print(f"\n{len(approval_queue.list_pending())} email draft(s) pending your review. Run with --review to see them.")


def run_live(settings, args) -> None:
    client = openai.OpenAI(api_key=settings.openai_api_key)
    gmail_service = build_gmail_service(settings.google_oauth_client_secrets, settings.google_oauth_token_path)
    calendar_service = build_calendar_service(settings.google_oauth_client_secrets, settings.google_oauth_token_path)
    approval_queue = ApprovalQueue(path="./data/pending_approvals.json")

    deps = Deps(
        client=client,
        calendar_service=calendar_service,
        calendar_id=settings.target_calendar_id,
        approval_queue=approval_queue,
        negotiation_round_cap=settings.negotiation_round_cap,
        today_iso=lambda: datetime.now().date().isoformat(),
    )
    graph = build_graph(deps)

    emails = fetch_new_school_emails(gmail_service, settings.school_sender_allowlist)
    if not emails:
        print("No new school emails since last check.")
    for email in emails:
        print(f"\n=== {email.subject} ===")
        result = graph.invoke(
            {
                "email_sender": email.sender,
                "email_subject": email.subject,
                "email_body": email.body,
            }
        )
        print(summarize(result))

    if args.review or approval_queue.list_pending():
        run_red_alert_loop(
            approval_queue,
            send_fn=lambda draft: send_email(gmail_service, draft["to"], draft["subject"], draft["body"]),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", action="store_true", help="Open the pending-approval review loop after processing.")
    args = parser.parse_args()

    settings = load_settings()
    if settings.mode == "demo":
        run_demo(settings, args)
    else:
        run_live(settings, args)


if __name__ == "__main__":
    main()

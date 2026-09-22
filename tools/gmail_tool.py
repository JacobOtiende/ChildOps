"""
Real Gmail API calls for the School Agent's trigger source.

This is polling, not a push webhook: main.py calls fetch_new_school_emails()
on the Control Tower's wake interval (default 4h, config.py). See
README.md > "Why polling, not push" for why that's the right tradeoff here
instead of Gmail's Pub/Sub push notifications.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from email.mime.text import MIMEText


@dataclass
class SchoolEmail:
    message_id: str
    sender: str
    subject: str
    body: str
    received_at: str  # RFC 2822 date header, as Gmail returns it


def _build_query(allowlist: list[str]) -> str:
    if not allowlist:
        raise ValueError(
            "SCHOOL_SENDER_ALLOWLIST is empty — the School Agent needs at "
            "least one sender domain/address to treat as school correspondence."
        )
    senders = " OR ".join(f"from:{s}" for s in allowlist)
    return f"({senders}) is:unread"


def _extract_body(payload: dict) -> str:
    """Walk a Gmail message payload and return the best plain-text body
    we can find, decoding the base64url Gmail uses."""

    def decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return decode(payload["body"]["data"])

    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return decode(part["body"]["data"])
    # Fall back to the first part with any data at all (e.g. text/html only).
    for part in payload.get("parts", []) or []:
        if part.get("body", {}).get("data"):
            return decode(part["body"]["data"])
    return ""


def fetch_new_school_emails(gmail_service, allowlist: list[str], max_results: int = 25) -> list[SchoolEmail]:
    """Real, live call against the Gmail API — lists unread messages from
    the school sender allowlist and fetches each one's content."""
    query = _build_query(allowlist)
    response = (
        gmail_service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    message_stubs = response.get("messages", [])

    emails: list[SchoolEmail] = []
    for stub in message_stubs:
        full = (
            gmail_service.users()
            .messages()
            .get(userId="me", id=stub["id"], format="full")
            .execute()
        )
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        emails.append(
            SchoolEmail(
                message_id=full["id"],
                sender=headers.get("from", "unknown"),
                subject=headers.get("subject", "(no subject)"),
                body=_extract_body(full["payload"]),
                received_at=headers.get("date", ""),
            )
        )
    return emails


def send_email(gmail_service, to: str, subject: str, body: str) -> str:
    """Real, live call against the Gmail API -- sends a plain-text reply.
    Only ever called from the approval loop after an explicit human
    approve/edit choice (see approvals/approval_queue.py:run_red_alert_loop
    and main.py:run_live); nothing in this project sends unprompted.
    Returns the sent message's id."""
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]

"""
Real OAuth against the user's own Google account — no mocked tokens.

The first time this runs it opens a browser consent screen (standard
InstalledAppFlow behavior); every run after that reuses the cached token in
GOOGLE_OAUTH_TOKEN_PATH and refreshes it silently. This is the same pattern
Google's own quickstart samples use for a personal/desktop project, and it's
the right amount of infrastructure for a course project — a production
Gmail push-notification webhook needs a public HTTPS endpoint and a verified
domain, which is out of scope here (see README "Why polling, not push").
"""
from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only Gmail (School Agent never needs to send/modify mail itself —
# that's the whole point of the human-in-the-loop email gate) plus full
# Calendar access (Calendar Agent needs to create/update/query events).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials(client_secrets_path: str, token_path: str) -> Credentials:
    """Return valid user credentials, running the OAuth consent flow
    only if no cached/refreshable token exists yet."""
    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_path):
                raise FileNotFoundError(
                    f"Google OAuth client secrets not found at {client_secrets_path!r}. "
                    "Download it from Google Cloud Console > APIs & Services > "
                    "Credentials > OAuth client ID (Desktop app) and point "
                    "GOOGLE_OAUTH_CLIENT_SECRETS at it. See README.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def build_gmail_service(client_secrets_path: str, token_path: str):
    creds = get_credentials(client_secrets_path, token_path)
    return build("gmail", "v1", credentials=creds)


def build_calendar_service(client_secrets_path: str, token_path: str):
    creds = get_credentials(client_secrets_path, token_path)
    return build("calendar", "v3", credentials=creds)

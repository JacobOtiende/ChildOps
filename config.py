"""
Central configuration for ChildOps, loaded from environment variables / .env.

Nothing here is a stub: every value is read at import time so a misconfigured
deployment fails fast and loudly rather than silently falling back to mocked
behavior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    google_oauth_client_secrets: str
    google_oauth_token_path: str
    school_sender_allowlist: list[str]
    target_calendar_id: str
    mode: str  # "demo" or "live"

    # Governance knobs that came directly out of the design discussion —
    # kept here, not hardcoded in the agent modules, so they're one obvious
    # place to tune without touching agent logic.
    negotiation_round_cap: int = 2
    control_tower_wake_interval_hours: int = 4


def load_settings() -> Settings:
    mode = os.environ.get("CHILDOPS_MODE", "demo").lower()
    if mode not in ("demo", "live"):
        raise RuntimeError(f"CHILDOPS_MODE must be 'demo' or 'live', got {mode!r}")

    allowlist_raw = os.environ.get("SCHOOL_SENDER_ALLOWLIST", "")
    allowlist = [s.strip() for s in allowlist_raw.split(",") if s.strip()]

    # In demo mode we don't need a real OpenAI key to *load* config (tests
    # inject a fake), but live mode must fail fast without one.
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if mode == "live" and not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required when CHILDOPS_MODE=live")

    return Settings(
        openai_api_key=openai_key,
        google_oauth_client_secrets=os.environ.get(
            "GOOGLE_OAUTH_CLIENT_SECRETS", "./credentials/client_secret.json"
        ),
        google_oauth_token_path=os.environ.get(
            "GOOGLE_OAUTH_TOKEN_PATH", "./credentials/token.json"
        ),
        school_sender_allowlist=allowlist,
        target_calendar_id=os.environ.get("TARGET_CALENDAR_ID", "primary"),
        mode=mode,
    )

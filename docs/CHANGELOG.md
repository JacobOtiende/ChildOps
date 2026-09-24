# Changelog

## 2026-09-23

### Fixed
- Live Google Calendar calls failed with `400 Bad Request` because the LLM gives datetimes with no UTC offset (e.g. `2026-09-23T00:00:00`). `tools/calendar_tool.py` now attaches the local offset to such times before `events.list`, `insert` and `patch` (`_rfc3339`). Times that already have an offset pass through unchanged.

### Changed
- Test sender changed to `jacob.o.otiende@gmail.com`. Local `.env` (gitignored) now uses it for both `TEST_SENDER_EMAIL` and `SCHOOL_SENDER_ALLOWLIST` (replacing `jacksnrctzn@gmail.com`).
- `tests/test_graph_flow.py`: three assertions now check an event's date and time instead of the exact string, since stored datetimes now include an offset.

## 2026-09-22

### Changed
- Google OAuth Desktop-app client credentials added locally at `credentials/client_secret.json` (gitignored, not committed). This unblocks the first live-mode OAuth consent run.
- Local `.env` (gitignored) switched to `CHILDOPS_MODE=live`. `python main.py` now reads the real Gmail inbox and writes to the real Google Calendar instead of the demo data.
- Local `.env` now sets `BROWSER` to Firefox, so the OAuth sign-in opens in Firefox rather than the system default browser. Uses Python's standard `webbrowser` lookup, so no code changed.

### Fixed
- None in code. The first `doctor_note` test send failed with SMTP `535 BadCredentials` because `TEST_SENDER_APP_PASSWORD` was still the `.env.example` placeholder. Nothing was sent; the fix is to generate a real App Password (see HANDOVER).

### Documentation
- Added `docs/` (HANDOVER, DAILY_LOG, CHANGELOG, SKILLS_LOG), reconstructed from the 2026-09-21 git history.

## 2026-09-21

### Added
- Initial ChildOps vertical slice: School → Task → (Control Tower ‖ Calendar negotiation) → decide & act, as a LangGraph state graph with a persistent email approval gate (`f5a4496`).
- Bounded reject → revise → re-review loop after a Control Tower tier-two rejection (`16a13c8`).
- Real Gmail send (`tools/gmail_tool.py:send_email`). It runs only from the live-mode approval loop, after a human approves (`152d10c`).

### Changed
- LLM provider moved from Anthropic to OpenAI (`5cbe7e0`).
- Scope narrowed to four agents; Health Agent removed from config and README (`4c47223`).

### Fixed
- Control Tower was missing history, and `proposed_title` was falsely flagged (`dd760da`).
- Timezone-naive/aware comparison crash in the in-memory demo calendar (`da59cfb`).
- Missing `gmail.send` OAuth scope, which would have failed the first live send (`e1327de`).

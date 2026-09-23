# Daily Log

## 2026-09-22

### Objective
Resume the project and prepare live mode.

### Work Completed
- Start-of-session review: working tree clean and in sync with `origin/master`; `pytest tests/` 15/15 passing.
- The Google OAuth client JSON (type `installed` / Desktop app, redirect `http://localhost`) was renamed to `credentials/client_secret.json`, the path `.env` expects.
- Created the `docs/` folder (commit `2b0ae12`, pushed).
- `.env`: set `BROWSER` to Firefox for the OAuth sign-in and switched to `CHILDOPS_MODE=live`. Checked by loading the config (mode live, allowlist `jacksnrctzn@gmail.com`, secrets file found).
- Tried the `doctor_note` test send. It failed with SMTP `535`; nothing was sent.

### Findings
- `credentials/` is gitignored, so the client secret stays local only.
- The SMTP failure happened because `TEST_SENDER_APP_PASSWORD` is still the `xxxx xxxx xxxx xxxx` placeholder from `.env.example`.
- Live mode never marks emails read, so repeat runs reprocess the same unread emails.

### Next Session
Add a real App Password, resend `doctor_note`, then run the first live OAuth consent (see HANDOVER).

## 2026-09-21

### Objective
Build the ChildOps vertical slice end to end.

### Work Completed
- Built the initial four-agent LangGraph slice with demo mode and tests.
- Ported the LLM provider to OpenAI and removed Health Agent scope.
- Fixed Control Tower history / `proposed_title` false flag.
- Added the reject → revise → re-review loop, verified against real GPT-4o calls on the newsletter sample.
- Fixed the demo-calendar timezone crash and re-ran all sample emails against GPT-4o without crashes.
- Added real Gmail send behind human approval, plus the missing `gmail.send` scope.

### Decisions
- Polling rather than a Pub/Sub push webhook (see README).
- Revision loop does not retrigger Calendar negotiation (documented limitation).
- Send runs before the approval status flips, so a failed send stays pending.

### Next Session
Set up Google OAuth credentials for live mode.

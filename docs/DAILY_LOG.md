# Daily Log

## 2026-09-22

### Objective
Resume the project and prepare live mode.

### Work Completed
- Start-of-session review: working tree clean and in sync with `origin/master`; `pytest tests/` 15/15 passing.
- The Google OAuth client JSON (type `installed` / Desktop app, redirect `http://localhost`) was renamed to `credentials/client_secret.json`, the path `.env` expects.
- Created the `docs/` folder.

### Findings
- `credentials/` is gitignored, so the client secret stays local only.
- `.env` has no `TEST_SENDER_EMAIL` / `TEST_SENDER_APP_PASSWORD` yet, so `testing/send_test_email.py` can't send.
- `.env` is still `CHILDOPS_MODE=demo`.

### Next Session
Run the first live-mode OAuth consent flow (see HANDOVER).

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

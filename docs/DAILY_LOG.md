# Daily Log

## 2026-09-23

### Objective
Get live mode running end to end.

### Work Completed
- Changed the test sender to `jacob.o.otiende@gmail.com` in `.env` (`TEST_SENDER_EMAIL` and `SCHOOL_SENDER_ALLOWLIST`) and in the handover docs.
- First live OAuth consent completed; `credentials/token.json` was created (2026-09-23 18:34).
- The first live `python main.py` run picked up a real forwarded school email ("Fwd: Sep 23, 2026 Digest: 4 new messages from BASIS San Antonio…") and crashed in `calendar_negotiate` with a Calendar API `400 Bad Request`.
- Fixed the crash in `tools/calendar_tool.py` by attaching the local offset to times that don't have one. Checked by rerunning the failing query against the real calendar (no error) and with `pytest tests/` (15/15 after updating three assertions).
- The user reran `python main.py` and reported it worked.
- A later live run over three unread forwarded digests (Medina Valley ISD, BASIS San Antonio, LACOSTE ES; about 6.5k, 13.7k and 6.7k characters) crashed with OpenAI `429` (30k tokens/min on gpt-4o). Raising the SDK's `max_retries` did not help, because it follows the sub-second retry-after hint. Added a longer backoff in `structured_call` instead (and reverted the `main.py` change). `pytest tests/` 17/17. The user reran and reported it worked.

### Findings
- The Calendar API requires RFC3339 times with an offset. Demo mode hid this because the in-memory calendar ignores timezones.
- Only the School Agent sends the full email body, but each email makes about 10 LLM calls, and OpenAI counts each call's `max_tokens` (1024) toward the per-minute limit up front. A few long digests can use up a whole minute's budget.
- The Task Agent proposed a **00:00** event for the digest, probably because the email gave no time.
- `TEST_SENDER_APP_PASSWORD` is still the placeholder, so `testing/send_test_email.py` has still not sent anything. The live run used a manually forwarded email instead.

### Problems / Issues
- The live-run output (classification, action, event, draft) was not captured in this session.

### Next Session
Set a real App Password and run the five scripted scenarios in live mode (see HANDOVER).

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

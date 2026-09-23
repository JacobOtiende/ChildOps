# Project Handover

## Current Status
Demo mode works end to end (real OpenAI calls, in-memory calendar). Test suite 15/15 passing (2026-09-22). Google OAuth client credentials are in place locally and `.env` is set to `CHILDOPS_MODE=live` with Firefox as the OAuth browser. The live OAuth consent run has not happened yet.

## Completed
- Four-agent LangGraph graph: classification QC loop, parallel Control Tower ‖ Calendar fan-out with `defer` join, 2-round negotiation cap, reject → revise → re-review loop.
- Persistent approval queue; real Gmail send only after human approval in live mode.
- Real Gmail/Calendar API tools and OAuth flow (scopes include `gmail.send`).
- `testing/send_test_email.py` with 5 scenarios for live testing.
- `credentials/client_secret.json` (Desktop-app OAuth client) placed locally.

## In Progress
- Live-mode setup.

## Not Started
- First live OAuth consent run (`credentials/token.json` does not exist yet).
- Test sender App Password (`TEST_SENDER_EMAIL` is set; the password is still the placeholder).
- Control Tower grammar/tone-assist utility (design-only, intentionally out of scope).

## Blockers
- Test emails: `TEST_SENDER_APP_PASSWORD` in `.env` is still the `.env.example` placeholder, so the SMTP send fails with `535 BadCredentials`. Generate a real App Password for jacksnrctzn@gmail.com.
- OAuth consent itself is not blocked.

## Important Decisions
- Scope limited to School, Task, Calendar, Control Tower agents.
- OpenAI is the LLM provider.
- Polling instead of Pub/Sub push.
- Email is never auto-sent; human approval is required.

## Known Issues
- Live mode never marks emails read (`gmail.readonly` + `is:unread` query), so repeat runs reprocess the same emails and can create duplicate events and drafts.
- In Testing status, the OAuth token expires after 7 days. When that happens, delete `credentials/token.json` and sign in again.
- A revised proposal after Control Tower rejection is not re-checked by Calendar Agent for conflicts.

## Immediate Next Action
Generate a Gmail App Password for jacksnrctzn@gmail.com (2-Step Verification must be on) and put it in `TEST_SENDER_APP_PASSWORD` in `.env`. Then run `python testing/send_test_email.py --scenario doctor_note`, followed by `python main.py`. Complete the Firefox OAuth consent as childops2@gmail.com, tick all three scopes, and confirm `credentials/token.json` is created.

## Recommended Next Steps
1. After each live run, mark the processed test emails as read. The app uses read-only Gmail access and polls `is:unread`, so otherwise it reprocesses them.
2. `python testing/send_test_email.py --all --delay 20`, then `python main.py` in live mode.
3. Verify `field_trip_reply` is queued and not sent, and that `ambiguous_item` stays low-confidence.

## Important Context
- Secrets live in `.env` and `credentials/`, both gitignored.
- Remote: https://github.com/JacobOtiende/ChildOps (branch `master`).

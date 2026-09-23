# Project Handover

## Current Status
Demo mode works end to end (real OpenAI calls, in-memory calendar). Test suite 15/15 passing (2026-09-22). Google OAuth client credentials are now in place locally; live mode has not been run yet.

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
- Test sender account setup (`TEST_SENDER_EMAIL`, `TEST_SENDER_APP_PASSWORD` absent from `.env`).
- Control Tower grammar/tone-assist utility (design-only, intentionally out of scope).

## Blockers
- None for OAuth. Live test emails are blocked until the sender App Password is configured.

## Important Decisions
- Scope limited to School, Task, Calendar, Control Tower agents.
- OpenAI is the LLM provider.
- Polling instead of Pub/Sub push.
- Email is never auto-sent; human approval is required.

## Known Issues
- A revised proposal after Control Tower rejection is not re-checked by Calendar Agent for conflicts.

## Immediate Next Action
Set `CHILDOPS_MODE=live` and `SCHOOL_SENDER_ALLOWLIST` in `.env`, then run `python main.py` and finish the browser OAuth consent with the fake parent Gmail account (it must be listed as a test user on the OAuth consent screen). Confirm `credentials/token.json` is created.

## Recommended Next Steps
1. Create the throwaway sender account's App Password; add `TEST_SENDER_EMAIL` / `TEST_SENDER_APP_PASSWORD` to `.env` and the sender to `SCHOOL_SENDER_ALLOWLIST`.
2. `python testing/send_test_email.py --all --delay 20`, then `python main.py` in live mode.
3. Verify `field_trip_reply` is queued and not sent, and that `ambiguous_item` stays low-confidence.

## Important Context
- Secrets live in `.env` and `credentials/`, both gitignored.
- Remote: https://github.com/JacobOtiende/ChildOps (branch `master`).

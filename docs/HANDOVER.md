# Project Handover

## Current Status
Live mode works end to end: OAuth consent done (`credentials/token.json` exists), and live `python main.py` runs over real forwarded school emails completed (2026-09-23), after a Calendar timezone fix and an OpenAI rate-limit backoff. Demo mode still works; test suite 17/17 passing. The scripted test emails (`testing/send_test_email.py`) have not been sent yet because the test-sender App Password is still the placeholder.

## Completed
- Four-agent LangGraph graph: classification QC loop, parallel Control Tower ‖ Calendar fan-out with `defer` join, 2-round negotiation cap, reject → revise → re-review loop.
- Persistent approval queue; real Gmail send only after human approval in live mode.
- Real Gmail/Calendar API tools and OAuth flow (scopes include `gmail.send`).
- `testing/send_test_email.py` with 5 scenarios for live testing.
- First live OAuth consent as childops2@gmail.com; `credentials/token.json` created (2026-09-23).
- Live Calendar calls now send offset-aware RFC3339 times (`tools/calendar_tool.py:_rfc3339`).
- LLM calls wait out OpenAI 429 rate limits (`agents/llm.py`, backoff about 70s total) instead of crashing the run.
- First successful live runs (2026-09-23), including a batch of three real forwarded digests.

## In Progress
- Live-mode verification with the scripted scenarios.

## Not Started
- Test sender App Password for `jacob.o.otiende@gmail.com` (`TEST_SENDER_EMAIL` and `SCHOOL_SENDER_ALLOWLIST` are set; the password is still the placeholder).
- Control Tower grammar/tone-assist utility (design-only, intentionally out of scope).

## Blockers
- Scripted test emails: `TEST_SENDER_APP_PASSWORD` in `.env` is still the placeholder, so the SMTP send fails with `535 BadCredentials`. Live mode itself is not blocked; you can forward a real email from `jacob.o.otiende@gmail.com` instead.

## Important Decisions
- Scope limited to School, Task, Calendar, Control Tower agents.
- OpenAI is the LLM provider.
- Polling instead of Pub/Sub push.
- Email is never auto-sent; human approval is required.
- A time with no offset is read as this machine's local timezone (currently `-05:00`, US Central).

## Known Issues
- Live mode never marks emails read (`gmail.readonly` + `is:unread` query), so repeat runs reprocess the same emails and can create duplicate events and drafts. Mark the processed forwarded digests (Medina Valley ISD, BASIS San Antonio, LACOSTE ES) as read in Gmail before the next run.
- OpenAI gpt-4o is capped at 30k tokens/min on the current usage tier. Runs over several long digests will pause at `[rate limit] … waiting Ns`; if a run exhausts the ~70s backoff, wait a minute and rerun, mark handled emails read, or set `CHILDOPS_MODEL=gpt-4o-mini` in `.env`.
- The Task Agent can propose a midnight (00:00) event when an email gives no time. Check proposals before approving.
- In Testing status, the OAuth token expires after 7 days (current one from 2026-09-23). When that happens, delete `credentials/token.json` and sign in again.
- A revised proposal after Control Tower rejection is not re-checked by Calendar Agent for conflicts.

## Immediate Next Action
Generate a Gmail App Password for jacob.o.otiende@gmail.com (myaccount.google.com/apppasswords, 2-Step Verification on), save it as `TEST_SENDER_APP_PASSWORD` in `ChildOps/.env`, and confirm the file is saved. Then run `python testing/send_test_email.py --scenario doctor_note` and confirm it arrives unread in the childops2@gmail.com inbox.

## Recommended Next Steps
1. After each live run, mark the processed emails as read.
2. `python testing/send_test_email.py --all --delay 20`, then `python main.py` in live mode.
3. Verify `field_trip_reply` is queued and not sent, and that `ambiguous_item` stays low-confidence.

> [!IDEA]
> Possible future improvement: have the Task Agent avoid midnight defaults (all-day event, or flag low confidence) when an email gives no time.

## Important Context
- Secrets live in `.env` and `credentials/`, both gitignored.
- Remote: https://github.com/JacobOtiende/ChildOps (branch `master`).

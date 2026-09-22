# ChildOps — vertical slice

A working implementation of one full path through the ChildOps design:
**School Agent → Task Agent → (Control Tower approval ‖ Calendar Agent
negotiation) → decide & act**, including the persistent email approval
gate. This is the scoped build recommended during design review: one real
path end to end, rather than five agents all half-simulated.

## What's real here

- **Real Gmail/Calendar integration code** (`auth/google_auth.py`,
  `tools/gmail_tool.py`, `tools/calendar_tool.py`) — actual OAuth and actual
  Google API calls, not stubs. Live mode needs your own Google Cloud
  credentials (steps below).
- **Real LLM reasoning** at every decision point (`agents/*.py`) — School
  Agent classifies, Task Agent scores urgency/importance and proposes an
  action, Calendar Agent negotiates, Control Tower runs its two-tier check,
  breaks deadlocks, and corrects School Agent. Every one of these is a real
  Anthropic API call constrained to a structured tool schema, not a
  hardcoded if/else.
- **Real orchestration logic** (`graph/build_graph.py`) — a LangGraph state
  graph with genuine branching: a bounded classification-correction loop, a
  parallel fan-out (Control Tower + Calendar Agent consulted at once, with a
  `defer` join so both are waited on regardless of how many negotiation
  rounds the calendar branch takes), a 2-round negotiation cap that
  escalates to Control Tower, and a persistent approval gate that never
  auto-sends an email.

## What's demo-mode-only

`CHILDOPS_MODE=demo` (the default) still makes real Anthropic calls but
swaps the Google Calendar for `tools/demo_calendar.py`, an in-memory
calendar seeded with a couple of conflicting events — so you can see the
negotiation/deadlock path fire without first doing Google OAuth setup. It
replays `data/sample_emails.json` instead of polling live Gmail. Flip to
`CHILDOPS_MODE=live` once you've done the Google setup below.

## What's design-only (not built)

The Health Agent and Control Tower's grammar/tone-assist utility are
specified in the design writeup but not implemented here — they're the
parts least connected to proving autonomy (see the design discussion). The
governance knobs they'd need (symptom threshold + window, parent-set
trigger) are already stubbed in `config.py` (`health_symptom_window_days`)
for whoever picks that up next.

## Quickstart (demo mode)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY (get one at console.anthropic.com)
python main.py
```

You'll see three sample emails (a newsletter, an attendance notice
requiring a doctor's note, and a teacher's field-trip question) processed
through the full graph, with output showing each agent's decision, whether
Control Tower had to correct School Agent, how many negotiation rounds ran,
and whether anything is waiting for your approval. Add `--review` to open
the approval loop interactively.

## Testing against a real fake Gmail inbox

`data/sample_emails.json` covers demo mode, but the point of live mode is
that School Agent reads a real inbox — so to actually test that path you
need real emails landing in your fake "parent" Gmail account, not just the
JSON replay. `testing/send_test_email.py` sends genuine SMTP emails into
that inbox using a **second, throwaway** Gmail account as the sender (it's
playing the role of "the school"). The sender doesn't have to be Gmail —
any account you have SMTP credentials for works — Gmail's just the
lowest-friction option.

**One-time setup for the sender account:**

1. Create (or reuse) a second Gmail account you don't mind using for this —
   it never needs to be the account ChildOps polls.
2. Turn on 2-Step Verification for it: myaccount.google.com/security.
3. Generate an App Password: myaccount.google.com/apppasswords → this is a
   16-character password used only for this script, not your real Google
   password.
4. In `.env`, set `TEST_SENDER_EMAIL` (the throwaway account),
   `TEST_SENDER_APP_PASSWORD` (the App Password from step 3), and
   `TEST_RECIPIENT_EMAIL` (your fake parent account — the one ChildOps does
   OAuth against in live mode). Make sure `TEST_SENDER_EMAIL` is also in
   `SCHOOL_SENDER_ALLOWLIST`, or School Agent's Gmail query won't pick the
   message up at all.

**Sending test emails:**

```bash
python testing/send_test_email.py --list                       # see the 5 built-in scenarios
python testing/send_test_email.py --scenario doctor_note        # send one
python testing/send_test_email.py --scenario newsletter --dry-run   # preview without sending
python testing/send_test_email.py --all --delay 20              # send all 5, 20s apart
python testing/send_test_email.py --subject "Test" --body "Hi" --to you@gmail.com   # one-off custom email
```

The five built-in scenarios (`testing/scenarios.json`) are deliberately not
all easy cases: `field_trip_reply` should end up queued in the approval
loop and never actually sent (tests the red-alert gate for real);
`ambiguous_item` has no explicit date or category (tests whether School
Agent stays low-confidence instead of guessing, and whether Control
Tower's classification QC catches it); `conflicting_event` proposes a
specific next-day time, which is a real chance to see the Calendar Agent
negotiate or Control Tower break a deadlock if something's already on your
actual calendar then.

After sending, run `python main.py` (with `CHILDOPS_MODE=live`) to poll and
process them — live mode doesn't auto-run on a schedule here, so trigger it
manually each time you want to see a batch processed rather than waiting
for a real 4-hour heartbeat.

## Running the test suite

```bash
pytest tests/ -v
```

These tests don't call any real API — they script exactly what each agent
"decides" at each step (`tests/fakes.py`) and assert on the resulting
graph state. This is what actually verifies the branching logic (the
round-cap, the correction loop, the parallel join) works, independent of
what a live LLM happens to say on a given run. All 9 pass as of this build:
5 on the graph itself, including the two trickiest cases — a deadlock
resolved after exactly 2 rounds, and convergence via the Task Agent
accepting a counter-proposal, both routing into the same `decide_action`
join node, confirming the `defer=True` fan-in handles variable-length
negotiation correctly — plus 4 on `testing/send_test_email.py`'s message
construction and SMTP call shape (mocked, no real network or credentials
needed to run the suite).

## Setting up live mode (real Gmail + Calendar)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and
   create a new project (or use an existing one).
2. **APIs & Services → Library**: enable the **Gmail API** and the
   **Google Calendar API**.
3. **APIs & Services → OAuth consent screen**: choose "External" (unless
   you have a Workspace org), fill in the required fields, and add your own
   Google account as a test user. It's fine to leave it in "Testing"
   status — you don't need Google's app review for personal use.
4. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID** → Application type **Desktop app**. Download the resulting JSON.
5. Save it as `credentials/client_secret.json` (or point
   `GOOGLE_OAUTH_CLIENT_SECRETS` at wherever you put it).
6. In `.env`, set `CHILDOPS_MODE=live` and `SCHOOL_SENDER_ALLOWLIST` to the
   real sender domains/addresses your kids' school uses.
7. Run `python main.py`. The first run opens a browser consent screen;
   after that, `credentials/token.json` caches the session so you won't be
   asked again until it expires.

### Why polling, not a push webhook

Gmail supports push notifications via Cloud Pub/Sub, which is the
"real-time trigger" version of the School Agent. It needs a public HTTPS
endpoint and a verified domain to receive the push, which is real
infrastructure a course project doesn't need. Polling on Control Tower's
4-hour wake interval (`config.py: control_tower_wake_interval_hours`) gets
you the same practical behavior — school email isn't a matter of seconds —
without standing up a server. Swap in Pub/Sub later by replacing the call
site in `main.py:run_live` with a webhook handler; nothing else in the
graph needs to change.

## Where the design gaps from review got resolved in code

- **Race condition (Control Tower correcting School Agent mid-flight):**
  resolved by making classification QC a gate *before* Task Agent ever
  runs (`classify → classification_qc → [correct → re-check]* → task_propose`
  in `build_graph.py`), instead of a concurrent side-channel. Task Agent
  only ever sees a Control-Tower-approved classification. Trade-off: a
  little added latency per email, in exchange for never operating on stale
  data — see `test_control_tower_correction_replaces_stale_classification`.
- **Negotiation deadlock with no exit condition:** `negotiation_round_cap`
  (default 2, `config.py`) forces `control_tower.break_deadlock` once
  exceeded — see `test_negotiation_escalates_to_control_tower_after_round_cap`.
- **No data contract between agents:** `graph/state.py` is the contract —
  every field School/Task/Calendar/Control Tower agents read or write is
  named and typed there.
- **Control Tower reviewing everything vs. staying efficient:** implemented
  as the two-tier triage in `agents/control_tower.py` — `tier_one_review`
  runs on every Task Agent proposal; `tier_two_review` (the expensive pass)
  only runs if tier one flags something *or* the action is externally
  consequential (an outbound email).
- **Email autonomy boundary:** Task Agent drafts (`draft_email_response`)
  but the graph never calls a send function — `decide_action` only ever
  enqueues the draft via `approvals/approval_queue.py`, which requires an
  explicit `approve()` call before anything would be sent.

## Project layout

```
config.py                  settings + governance knobs (round cap, wake interval)
auth/google_auth.py        real OAuth flow for Gmail + Calendar
tools/gmail_tool.py        real Gmail API: fetch_new_school_emails
tools/calendar_tool.py     real Calendar API: check_conflict, create_event, propose_alternates
tools/demo_calendar.py     in-memory calendar for CHILDOPS_MODE=demo
agents/school_agent.py     classification + Control-Tower-correction re-run
agents/task_agent.py       urgency/importance scoring, negotiation reconsideration, email drafting
agents/calendar_agent.py   negotiation position each round, grounded in real conflict data
agents/control_tower.py    tier-one/tier-two review, deadlock breaking, classification QC
graph/state.py             the ChildOpsState data contract
graph/build_graph.py       the LangGraph wiring — nodes, conditional edges, the defer join
approvals/approval_queue.py the persistent red-alert / approval gate
data/sample_emails.json    synthetic demo input
testing/send_test_email.py sends real test emails into your fake Gmail inbox for live-mode testing
testing/scenarios.json     the 5 built-in test scenarios (see "Testing against a real fake Gmail inbox")
tests/                     graph-branching + email-sender tests against scripted/mocked (non-live) responses
main.py                    CLI entry point (demo and live modes)
```

# Skills Log

| Date | Category | Skill | Level | Evidence |
|---|---|---|---|---|
| 2026-09-21 | AI / Agents | LangGraph multi-agent orchestration | Demonstrated | `graph/build_graph.py`: conditional loops, parallel fan-out with `defer` join, bounded negotiation cap |
| 2026-09-21 | AI / LLM | OpenAI structured tool-call outputs | Demonstrated | Agents constrained to tool schemas; verified against real GPT-4o runs |
| 2026-09-21 | AI / LLM | LLM provider migration | Demonstrated | Ported Anthropic → OpenAI (`5cbe7e0`) |
| 2026-09-21 | Integration | Google Gmail & Calendar APIs, OAuth 2.0 | Practiced | Fetch/send and calendar tools written; scope bug caught (`e1327de`); not yet run live |
| 2026-09-21 | Software Engineering | Testing with mocks/fakes | Demonstrated | 15 pytest tests with scripted agent decisions and mocked APIs |
| 2026-09-21 | Software Engineering | Debugging | Demonstrated | Fixed timezone comparison crash (`da59cfb`) and Control Tower false flag (`dd760da`) |
| 2026-09-21 | AI Safety / Design | Human-in-the-loop approval gate | Demonstrated | Send happens only after explicit approval; a failed send stays pending |
| 2026-09-22 | Integration | Google Cloud OAuth client setup | Practiced | Created a Desktop-app OAuth client and installed it as `credentials/client_secret.json`, kept out of git; live consent flow not yet completed |
| 2026-09-22 | Software Engineering | Environment-based configuration | Practiced | Moved the app to live mode and pointed the OAuth browser at Firefox through `.env` alone, with no code change; checked the result by loading the config |
| 2026-09-22 | Software Engineering | Debugging (SMTP authentication) | Practiced | Traced a Gmail SMTP `535` failure to a placeholder App Password without exposing the secret |
| 2026-09-23 | Integration | Google OAuth 2.0 consent flow (live) | Demonstrated | Completed the Desktop-app consent; `token.json` issued and used for a successful live Gmail + Calendar run |
| 2026-09-23 | Software Engineering | Debugging (API datetime formats) | Demonstrated | Traced a Calendar API `400` to offset-naive datetimes, fixed at the tool boundary (`_rfc3339`), verified against the live API and tests |
| 2026-09-23 | AI / LLM | LLM API rate-limit handling | Demonstrated | Diagnosed OpenAI TPM 429s (SDK retries too short for a saturated window), added bounded backoff in `structured_call` with fail-fast on `insufficient_quota`, unit-tested and confirmed on a live run |

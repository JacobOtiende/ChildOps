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

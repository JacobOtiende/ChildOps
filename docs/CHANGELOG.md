# Changelog

## 2026-09-22

### Changed
- Google OAuth Desktop-app client credentials added locally at `credentials/client_secret.json` (gitignored, not committed). This unblocks the first live-mode OAuth consent run.

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

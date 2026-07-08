# VEGAS Assistant

## What This Is

VEGAS (Versatile Executive Guardian & Assistant System) is a Tony Stark-style personal AI assistant. It combines a FastMCP tool server that exposes a growing library of tools with a LiveKit voice agent that calls those tools in real time for natural spoken conversation. It is designed to handle daily workflow automation, browser interaction, and delegated coding tasks.

## Core Value

Real-time, natural spoken conversation powered by a secure, extensible tool server that seamlessly and safely handles real-world actions.

## Requirements

### Validated

- ✓ FastMCP server scaffold (Python, uv) — Phase 1
- ✓ LiveKit voice pipeline (Sarvam STT -> Gemini 2.5 Flash -> OpenAI TTS) — Phase 1
- ✓ Basic tools: web search, news, system info — Phase 1

### Active

- [ ] Persistent SQLite memory — Phase 2, Milestone 1
- [ ] `requires_confirmation` approval-gate decorator (must be built first) — Phase 2, Milestone 1
- [ ] Coding delegation tool (dispatch to Antigravity CLI or Claude Code CLI) — Phase 2, Milestone 2
- [ ] Daily workflow tools: Google Calendar, Gmail drafts, morning briefing composer — Phase 2, Milestone 3
- [ ] Browser automation (Playwright) + sandboxed file read/write/delete — Phase 2, Milestone 4
- [ ] Wire everything into server's tool instructions and audit that all state-changing tools are gated — Phase 2, Milestone 5

### Out of Scope

- [Inline coding] — Real coding tasks are delegated to the Antigravity CLI or Claude Code CLI; the voice agent itself does not write code inline.
- [Ungated destructive actions] — Actions that send, delete, spend, or submit anything real must not be executed without confirmation.

## Context

The system has a working Phase 1 foundation. The focus is now on Phase 2, expanding the toolset into real-world utility while introducing a strict safety boundary (`requires_confirmation`) before advancing into workflows, browser automation, and file operations. 

## Constraints

- **Tech Stack**: Python 3.11+, uv, mcp[cli] (FastMCP), livekit-agents with plugins (google, openai, sarvam, silero), SQLite for memory, Playwright for browser automation, google-api-python-client. — Ensures consistency with the established architecture.
- **Safety**: State-changing operations (send, delete, spend, submit) must be approval-gated. — Protects against accidental execution by the LLM.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI Delegation for coding | The voice agent is not suited for inline code generation and file editing at scale. | — Pending |
| Build approval gate first | Downstream milestones (browser, file operations) pose risks without it. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-09 after initialization*

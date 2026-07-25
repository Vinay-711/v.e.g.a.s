# VEGAS Assistant

## What This Is

VEGAS (Versatile Executive Guardian & Assistant System) is a Tony Stark-style personal AI assistant. It features a premium, custom Web UI built with React/Vite that interacts with a FastMCP tool server to seamlessly manage workflows, browse the web, and execute tasks.

## Core Value

A beautiful, highly-responsive web-based AI assistant powered by a secure, extensible tool server that safely handles real-world actions.

## Requirements

### Validated

- ✓ FastMCP server scaffold (Python, uv) — Phase 1
- ✓ Initial tool integration framework — Phase 1
- ✓ Basic tools: web search, news, system info — Phase 1
- ✓ Persistent SQLite memory — Phase 2
- ✓ `requires_confirmation` approval-gate decorator — Phase 2
- ✓ Custom Web UI (Vite/React) for user interaction — Phase 3
- ✓ Code Delegation to external agents — Phase 4
- ✓ Daily workflow tools: Google Calendar, Gmail drafts, morning briefing composer — Phase 5
- ✓ Browser automation (Playwright) + sandboxed file read/write/delete — Phase 6
- ✓ Wire everything into server's tool instructions and audit that all state-changing tools are gated — Phase 7

### Active

(All phases of the roadmap have been successfully implemented and verified.)

### Out of Scope

- [Inline coding] — Real coding tasks are delegated to the Antigravity CLI or Claude Code CLI; the assistant itself does not write code inline.
- [Ungated destructive actions] — Actions that send, delete, spend, or submit anything real must not be executed without confirmation.

## Context

The system has completed all phases on the initial Roadmap. The focus is now on usage, deployment, and operational maintenance. 

## Constraints

- **Tech Stack**: Python 3.11+, uv, mcp[cli] (FastMCP), FastAPI (Backend Layer), React, Vite, Vanilla CSS (Frontend), SQLite for memory, Playwright for browser automation, google-api-python-client. — Ensures consistency with the established architecture.
- **Safety**: State-changing operations (send, delete, spend, submit) must be approval-gated. — Protects against accidental execution by the LLM.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI Delegation for coding | The assistant is not suited for inline code generation and file editing at scale. | — Pending |
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

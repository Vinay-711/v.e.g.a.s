# Requirements: VEGAS Assistant

**Defined:** 2026-07-09
**Core Value:** Real-time, natural spoken conversation powered by a secure, extensible tool server that seamlessly and safely handles real-world actions.

## v1 Requirements

### Core System (Phase 1)
- [ ] **CORE-01**: FastMCP tool server running via uv
- [ ] **CORE-02**: LiveKit voice agent running via uv
- [ ] **CORE-03**: Voice agent uses Sarvam STT, Gemini 2.5 Flash, and OpenAI TTS
- [ ] **CORE-04**: Voice agent can execute basic tools (web search, news, system info)

### State & Safety (Phase 2, M1)
- [ ] **SAFE-01**: Agent persists context and state across sessions via SQLite memory
- [ ] **SAFE-02**: Implement `requires_confirmation` decorator for tools
- [ ] **SAFE-03**: Agent halts execution and waits for explicit user confirmation on gated tools

### Code Delegation (Phase 2, M2)
- [ ] **CODE-01**: Voice agent can dispatch tasks to the Antigravity CLI or Claude Code CLI
- [ ] **CODE-02**: Voice agent can capture the output of delegated coding tasks
- [ ] **CODE-03**: Voice agent can verbally report the outcome to the user

### Daily Workflows (Phase 2, M3)
- [ ] **WORK-01**: Voice agent can read events from Google Calendar
- [ ] **WORK-02**: Voice agent can draft emails in Gmail (gated)
- [ ] **WORK-03**: Voice agent can compose and verbally deliver a daily morning briefing

### Advanced Operations (Phase 2, M4)
- [ ] **AUTO-01**: Voice agent can automate browser navigation via Playwright
- [ ] **AUTO-02**: Voice agent can extract information from and fill out forms on web pages
- [ ] **AUTO-03**: Voice agent can read from sandboxed local files
- [ ] **AUTO-04**: Voice agent can write to and delete sandboxed local files (gated)

### Audit & Hardening (Phase 2, M5)
- [ ] **AUDT-01**: All tools are fully wired with descriptive server instructions for the LLM
- [ ] **AUDT-02**: Comprehensive audit guarantees every state-changing tool (send, delete, spend, submit) uses the confirmation gate

## v2 Requirements

### Extended Automation
- **EXT-01**: Integration with smart home devices for physical world interactions
- **EXT-02**: Proactive asynchronous task execution (agent acts without explicit voice prompt)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Inline code writing | Voice models are poor at writing code inline; better to delegate to specialized CLIs. |
| Ungated destructive actions | Sending emails, deleting files, or spending money must require user confirmation to prevent accidents. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| SAFE-01 | Phase 2 | Pending |
| SAFE-02 | Phase 2 | Pending |
| SAFE-03 | Phase 2 | Pending |
| CODE-01 | Phase 3 | Pending |
| CODE-02 | Phase 3 | Pending |
| CODE-03 | Phase 3 | Pending |
| WORK-01 | Phase 4 | Pending |
| WORK-02 | Phase 4 | Pending |
| WORK-03 | Phase 4 | Pending |
| AUTO-01 | Phase 5 | Pending |
| AUTO-02 | Phase 5 | Pending |
| AUTO-03 | Phase 5 | Pending |
| AUTO-04 | Phase 5 | Pending |
| AUDT-01 | Phase 6 | Pending |
| AUDT-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 after initial definition*

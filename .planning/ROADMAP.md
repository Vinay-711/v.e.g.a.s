# Roadmap: VEGAS Assistant

## Overview

VEGAS starts with a basic FastMCP + LiveKit scaffold (Phase 1, complete). The next phase of development focuses on making the agent persistent and safe for real-world interactions by implementing state and a confirmation gate (Phase 2). Once secured, the agent gains the ability to delegate code execution (Phase 3), handle daily calendar/email workflows (Phase 4), and automate browser/file operations (Phase 5). Finally, everything is thoroughly audited to ensure strict adherence to the safety gate (Phase 6).

## Phases

- [x] **Phase 1: Core Scaffold** - Basic FastMCP server and LiveKit voice pipeline
- [ ] **Phase 2: State & Safety** - Persistent SQLite memory and the `requires_confirmation` decorator
- [ ] **Phase 3: Code Delegation** - Tool to dispatch coding tasks to Antigravity CLI
- [ ] **Phase 4: Daily Workflows** - Google Calendar integration, Gmail drafts, and morning briefings
- [ ] **Phase 5: Browser Automation** - Playwright integration and sandboxed file operations
- [ ] **Phase 6: Audit & Hardening** - Rigorous instruction wiring and safety gate verification

## Phase Details

<details>
<summary>✅ Phase 1: Core Scaffold - SHIPPED</summary>

### Phase 1: Core Scaffold
**Goal**: Establish the basic voice and tool pipeline.
**Depends on**: Nothing
**Requirements**: [CORE-01, CORE-02, CORE-03, CORE-04]
**Success Criteria** (what must be TRUE):
  1. FastMCP server runs without errors.
  2. LiveKit agent can hear, process via Gemini, and speak back.
  3. Agent can successfully execute a basic search tool.
**Plans**: 1 plan

Plans:
- [x] 01-01: Build FastMCP and LiveKit integration
</details>

### Phase 2: State & Safety
**Goal**: Make the agent persistent and safe to use for destructive actions.
**Depends on**: Phase 1
**Requirements**: [SAFE-01, SAFE-02, SAFE-03]
**Success Criteria** (what must be TRUE):
  1. The agent remembers conversations across sessions via SQLite.
  2. A `@requires_confirmation` decorator exists and works on tool functions.
  3. When a gated tool is called, the system waits for explicit user approval before executing the tool payload.
**Plans**: 2 plans

Plans:
- [ ] 02-01: Implement SQLite memory for persistence
- [ ] 02-02: Build the `requires_confirmation` decorator and confirmation loop

### Phase 3: Code Delegation
**Goal**: Enable the voice agent to perform coding tasks by dispatching them to an agentic CLI.
**Depends on**: Phase 2
**Requirements**: [CODE-01, CODE-02, CODE-03]
**Success Criteria** (what must be TRUE):
  1. The voice agent can trigger the Antigravity CLI via a subprocess.
  2. The tool captures stdout/stderr when the CLI finishes.
  3. The voice agent summarizes the CLI output verbally.
**Plans**: 1 plan

Plans:
- [ ] 03-01: Create Antigravity CLI delegation tool

### Phase 4: Daily Workflows
**Goal**: Connect the agent to Google Workspace for daily automation.
**Depends on**: Phase 3
**Requirements**: [WORK-01, WORK-02, WORK-03]
**Success Criteria** (what must be TRUE):
  1. The agent can list upcoming Calendar events.
  2. The agent can draft an email in Gmail.
  3. The agent can generate a coherent morning briefing from schedule and emails.
**Plans**: 2 plans

Plans:
- [ ] 04-01: Google Calendar and Gmail API integration
- [ ] 04-02: Morning briefing composer logic

### Phase 5: Browser Automation
**Goal**: Allow the agent to interact with the web and local files.
**Depends on**: Phase 4
**Requirements**: [AUTO-01, AUTO-02, AUTO-03, AUTO-04]
**Success Criteria** (what must be TRUE):
  1. The agent can load a webpage and extract text using Playwright.
  2. The agent can read a local file safely.
  3. Destructive file operations trigger the Phase 2 confirmation gate.
**Plans**: 2 plans

Plans:
- [ ] 05-01: Playwright MCP tool integration
- [ ] 05-02: Sandboxed file system tools

### Phase 6: Audit & Hardening
**Goal**: Finalize tool instructions and guarantee safety constraints.
**Depends on**: Phase 5
**Requirements**: [AUDT-01, AUDT-02]
**Success Criteria** (what must be TRUE):
  1. All tools have clear LLM instructions in their docstrings.
  2. Every tool that alters state is verified to be wrapped by `@requires_confirmation`.
**Plans**: 1 plan

Plans:
- [ ] 06-01: Codebase audit and documentation review

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Scaffold | 1/1 | Complete | 2026-07-09 |
| 2. State & Safety | 0/2 | Not started | - |
| 3. Code Delegation | 0/1 | Not started | - |
| 4. Daily Workflows | 0/2 | Not started | - |
| 5. Browser Automation| 0/2 | Not started | - |
| 6. Audit & Hardening | 0/1 | Not started | - |

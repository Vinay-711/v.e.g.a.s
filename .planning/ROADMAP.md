# Roadmap: VEGAS Assistant

## Overview

VEGAS starts with a basic FastMCP scaffold (Phase 1, complete). The next phase of development focused on making the agent persistent and safe for real-world interactions by implementing state and a confirmation gate (Phase 2, complete). The system is now pivoting to a custom, premium Web UI (Phase 3) that replaces the original voice agent design. Once the Web UI is active, the agent gains the ability to delegate code execution (Phase 4), handle daily calendar/email workflows (Phase 5), and automate browser/file operations (Phase 6). Finally, everything is thoroughly audited to ensure strict adherence to the safety gate (Phase 7).

## Phases

- [x] **Phase 1: Core Scaffold** - Basic FastMCP server and tool pipeline
- [x] **Phase 2: State & Safety** - Persistent SQLite memory and the `requires_confirmation` decorator
- [x] **Phase 3: Web UI Integration** - Custom Vite/React Web App and FastAPI backend
- [x] **Phase 4: Code Delegation** - Tool to dispatch coding tasks to Antigravity CLI
- [x] **Phase 5: Daily Workflows** - Google Calendar integration, Gmail drafts, and morning briefings
- [x] **Phase 6: Browser Automation** - Playwright integration and sandboxed file operations
- [x] **Phase 7: Audit & Hardening** - Rigorous instruction wiring and safety gate verification

## Phase Details

<details>
<summary>✅ Phase 1: Core Scaffold - SHIPPED</summary>

### Phase 1: Core Scaffold

**Goal**: Establish the basic tool pipeline.
**Depends on**: Nothing
**Requirements**: [CORE-01, CORE-02, CORE-03]
**Success Criteria** (what must be TRUE):

  1. FastMCP server runs without errors.
  2. Agent can successfully execute a basic search tool.

**Plans**: 1 plan

Plans:

- [x] 01-01: Build FastMCP integration

</details>

<details>
<summary>✅ Phase 2: State & Safety - SHIPPED</summary>

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

- [x] 02-01: Implement SQLite memory for persistence
- [x] 02-02: Build the `requires_confirmation` decorator and confirmation loop

</details>

<details>
<summary>✅ Phase 3: Web UI Integration - SHIPPED</summary>

### Phase 3: Web UI Integration

**Goal**: Pivot away from LiveKit to a custom, premium Web UI for VEGAS.
**Depends on**: Phase 2
**Requirements**: [WEB-01, WEB-02, WEB-03]
**Success Criteria** (what must be TRUE):

  1. The LiveKit voice agent codebase is fully removed.
  2. A lightweight backend API connects the FastMCP server with the frontend.
  3. A premium, beautifully designed Vite/React frontend serves as the chat interface.

**Plans**: 1 plan

Plans:

- [x] 03-01: Remove LiveKit, Build API Backend and Web UI

</details>

<details>
<summary>✅ Phase 4: Code Delegation - SHIPPED</summary>

### Phase 4: Code Delegation

**Goal**: Enable the assistant to perform coding tasks by dispatching them to an agentic CLI.
**Depends on**: Phase 3
**Requirements**: [CODE-01, CODE-02, CODE-03]
**Success Criteria** (what must be TRUE):

  1. The assistant can trigger the Antigravity CLI via a subprocess.
  2. The tool captures stdout/stderr when the CLI finishes.
  3. The assistant summarizes the CLI output in the Web UI.

**Plans**: 1 plan

Plans:

- [x] 04-01: Create Antigravity CLI delegation tool

</details>

<details>
<summary>✅ Phase 5: Daily Workflows - SHIPPED</summary>

### Phase 5: Daily Workflows

**Goal**: Connect the agent to Google Workspace for daily automation.
**Depends on**: Phase 4
**Requirements**: [WORK-01, WORK-02, WORK-03]
**Success Criteria** (what must be TRUE):

  1. The agent can list upcoming Calendar events.
  2. The agent can draft an email in Gmail.
  3. The agent can generate a coherent morning briefing from schedule and emails.

**Plans**: 2 plans

Plans:

- [x] 05-01: Google Calendar and Gmail API integration
- [x] 05-02: Morning briefing composer logic

</details>

<details>
<summary>✅ Phase 6: Browser Automation - SHIPPED</summary>

### Phase 6: Browser Automation

**Goal**: Allow the agent to interact with the web and local files.
**Depends on**: Phase 5
**Requirements**: [AUTO-01, AUTO-02, AUTO-03, AUTO-04]
**Success Criteria** (what must be TRUE):

  1. The agent can load a webpage and extract text using Playwright.
  2. The agent can read a local file safely.
  3. Destructive file operations trigger the Phase 2 confirmation gate in the Web UI.

**Plans**: 2 plans

Plans:

- [x] 06-01: Playwright MCP tool integration
- [x] 06-02: Sandboxed file system tools

</details>

<details>
<summary>✅ Phase 7: Audit & Hardening - SHIPPED</summary>

### Phase 7: Audit & Hardening

**Goal**: Finalize tool instructions and guarantee safety constraints.
**Depends on**: Phase 6
**Requirements**: [AUDT-01, AUDT-02]
**Success Criteria** (what must be TRUE):

  1. All tools have clear LLM instructions in their docstrings.
  2. Every tool that alters state is verified to be wrapped by `@requires_confirmation`.

**Plans**: 1 plan

Plans:

- [x] 07-01: Codebase audit and documentation review

</details>

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Scaffold | 1/1 | Complete | 2026-07-09 |
| 2. State & Safety | 2/2 | Complete | 2026-07-09 |
| 3. Web UI Integration | 1/1 | Complete | 2026-07-17 |
| 4. Code Delegation | 1/1 | Complete | 2026-07-17 |
| 5. Daily Workflows | 2/2 | Complete | 2026-07-17 |
| 6. Browser Automation| 2/2 | Complete | 2026-07-17 |
| 7. Audit & Hardening | 1/1 | Complete | 2026-07-17 |

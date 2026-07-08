# Phase 2: State & Safety - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the agent persistent and safe to use for destructive actions by implementing a SQLite memory module and a `requires_confirmation` decorator gate for tools.

</domain>

<decisions>
## Implementation Decisions

### Approval UX
- **D-01:** The `requires_confirmation` gate must ask for confirmation verbally via the voice agent (saying "Are you sure?" or similar) and wait for the user to say "Yes".

### Session Lifecycle
- **D-02:** Context rests only when the user explicitly says "Clear memory" or when the server restarts. Memory is not automatically cleared daily or constrained to a sliding window out-of-the-box unless limits are reached.

### the agent's Discretion
- SQLite integration: The user didn't specify whether to use an ORM or raw `sqlite3`. The agent has discretion to choose the most appropriate and lightweight method (likely raw `sqlite3` or a minimal wrapper).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Scope & Architecture
- `.planning/PROJECT.md` — Project definition, boundaries, and tech stack.
- `.planning/REQUIREMENTS.md` — Active and upcoming requirements.
- `.planning/codebase/ARCHITECTURE.md` — Existing architectural boundaries (FastMCP server and LiveKit VoicePipelineAgent).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent_vegas.py`: The LiveKit `VoicePipelineAgent` structure is where the voice prompt for confirmation will need to be injected or handled.
- `server.py`: The FastMCP server where tools are registered and where the `requires_confirmation` decorator will be applied.

### Established Patterns
- FastMCP tool definitions use standard Python type hints and docstrings for LLM consumption.
- The LiveKit agent uses the `google` plugin (Gemini Flash) for inference and tool calling.

### Integration Points
- The `requires_confirmation` decorator must hook into the FastMCP tool execution flow, pausing the tool execution to ask the LiveKit agent to verbally prompt the user, or returning a specific payload to the agent instructing it to ask the user.

</code_context>

<specifics>
## Specific Ideas

No specific references or examples were provided; use standard conversational voice UX patterns for confirmation prompts.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-State & Safety*
*Context gathered: 2026-07-09*

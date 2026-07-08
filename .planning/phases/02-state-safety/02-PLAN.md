# Phase 2: State & Safety - Plan

**Goal:** Make the agent persistent and safe to use for destructive actions.
**Status:** Planned

## 1. Audit Existing Implementation
- Verify that `vegas.memory` and `vegas.safety` are correctly imported and function without syntax errors.
- Ensure `vegas.tools.memory` correctly wraps these in MCP tool format.

## 2. Apply Security Decorators
- Modify `vegas/tools/files.py` to ensure any destructive file operations (e.g. `delete_file`) use `@requires_confirmation`.

## 3. Testing & Verification
- Write a test script `tests/test_memory_safety.py` to assert:
  - SQLite creates correctly.
  - State persists (tasks and preferences).
  - `@requires_confirmation` intercepts calls.
  - `confirm_task` executes intercepted calls.
- Run `pytest` or execute the script directly to verify.

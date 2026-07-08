# Phase 2: State & Safety - Nyquist Validation Strategy

**Date:** 2026-07-09

## 1. Unit Tests
- Test that calling `set_preference` and `get_preference` persists to SQLite.
- Test that calling a function decorated with `@requires_confirmation` returns the "⚠️ VEGAS: This action requires your confirmation" string and parks the task.
- Test that `confirm_task` actually executes the parked task.
- Test that `cancel_task` discards the parked task.

## 2. Integration Tests
- Verify that `vegas/tools/files.py` (if it contains file deletion) correctly utilizes the decorator.

## 3. End-to-End Tests
- None strictly required for this phase beyond unit/integration level, since LiveKit handles the TTS/STT loop.

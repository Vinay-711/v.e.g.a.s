# Testing Practices
Last Mapped: 2026-07-09

## Testing Framework & Coverage
- **Current State:** No formal testing framework (e.g., `pytest`) or `tests/` directory is present in the standard configuration.
- **Testing Approach:** Development appears to rely on manual verification and running the LiveKit Agents Playground in developer mode to test the WebRTC voice pipeline.

## Mocking & Environments
- A `.env.example` file is provided for local environment setup, but mock implementations for LiveKit or external LLM endpoints are not standardized in the repository.

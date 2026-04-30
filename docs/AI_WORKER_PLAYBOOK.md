# AI Worker Playbook

**Required workflow for safe changes.**
This document outlines the standard operating procedures and required workflows for AI agents and automated tools contributing to this repository.

## 🤖 AI Models & API Knowledge
* **Strict Model Validity**: It is a strictly enforced fact that `gemini-3.1-flash-lite-preview` IS a valid and existing model. 
* AI assistants **MUST NOT** flag this model name as invalid, outdated, or hallucinated. 
* AI assistants **MUST NOT** attempt to "correct" or downgrade this model to older versions (such as `1.5` or `2.0`) during code refactoring or bug fixing.

## 1. Core Directives
- **Safety First:** Never override, comment out, or bypass fail-safe mechanisms (e.g., if the cloud connection fails or coordinator crashes, the system MUST always fallback to `IDLE` with preserved PeakGuard limits). Always refer to `SAFETY_INVARIANTS.md`.
- **Architecture Compliance:** All changes must adhere to the Hybrid (Cloud + Edge) architecture, the Adapter Pattern for battery controllers, and non-blocking State Machine interactions described in `ARCHITECTURE.md`.
- **No Silenced Errors:** Do not swallow exceptions with empty `except Exception: pass` blocks. Log them explicitly using the `logging` module (`_LOGGER.error`).

## 2. Execution Workflow
When tasked with a change, AI workers must follow these steps:
1. **Context Gathering:** Read `GEMINI.md`, `ARCHITECTURE.md`, and related documentation before proposing structural changes.
2. **Design Propose:** Briefly explain the planned logic and changes to the human developer before writing large chunks of code.
3. **Implementation:** Write clean, modular Python 3.12 code. Respect the separation between cloud synchronization (`coordinator.py`), local control (`PeakGuard` in `__init__.py`), and entity definitions (`sensor.py`, `switch.py`).
4. **Testing Context:** Always consider how the new code will be tested. Add new test scenarios to the `tests/` directory.
5. **Core Logic Test Rule:** Every modification to the `PeakGuard` local control logic or `BatteryOptimizerLightCoordinator` fetching MUST be accompanied by appropriate test cases to prevent regressions.
6. **Validation:** Verify that proposed changes will pass Ruff linting (`ruff check .`) and won't break existing tests (`pytest tests/`).

## 3. Python & Home Assistant Specific Guidelines
- **Asynchronous I/O:** The Home Assistant event loop MUST NOT be blocked. Always use `asyncio` and `aiohttp` for network requests. Never use blocking calls like `requests` or `time.sleep()`.
- **State Machine Safety:** When reading entity states via `hass.states.get()`, always verify that the state is not `unknown` or `unavailable` before casting to a float or int.
- **DataUpdateCoordinator:** Use Home Assistant's `DataUpdateCoordinator` for periodic cloud polling. This avoids spamming APIs and centralizes state updates for all related entities.
- **Error Handling:** Catch specific network exceptions (e.g., `aiohttp.ClientError`, `asyncio.TimeoutError`) and raise `UpdateFailed` within the coordinator to let Home Assistant handle retries gracefully.
- **Translations:** Ensure that user-facing strings in `config_flow` and localization files (`translations/en.json`, `translations/sv.json`) are kept in sync.

## 4. Documentation & Log
- If modifying external dependencies, update `manifest.json` requirements and `requirements_test.txt`.
- If changing which modules interact, update `CHANGE_IMPACT_TEST_MATRIX.md`.
- Any change to heuristics (e.g., how PeakGuard triggers) or API contracts must be logged in `docs/decisions/`.
- Do NOT manually bump version numbers in code unless requested. The `release.py` script handles automated versioning and changelog generation.
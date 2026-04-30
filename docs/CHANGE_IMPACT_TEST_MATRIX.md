# Change Impact Test Matrix

**Which tests to run for each change type.**
Use this matrix to determine the required testing scope and automated checks based on the modules modified.

| Modified Component | Required Automated Tests | Required Validation / CI |
| :--- | :--- | :--- |
| **PeakGuard & Local Logic** (`__init__.py`) | Add new edge-case scenarios for load capping, hysteresis, and solar override in `tests/test_core.py`. | Run `pytest tests/` to ensure zero regressions in local control logic. |
| **Cloud Coordinator** (`coordinator.py`) | Add mock tests for `aiohttp` covering API resilience (401, 500, timeouts) and payload parsing in `tests/test_core.py`. | Verify async non-blocking behavior and correct fallback states (e.g., `IDLE`). |
| **Battery Controllers** (`batteries/` & `apply_action`) | Mock `hass.services.async_call` to verify correct power conversions (target_kw to W) and service commands. | Ensure physical constraints and correct HA domains/services are used. |
| **Sensors & States** (`sensor.py`) | Add tests to verify state attributes, calculated properties (like `virtual_load`), and correct unit conversions. | Ensure entity names and classes comply with Home Assistant standards. |
| **Config Flow & Setup** (`config_flow.py`, `translations/`) | Ensure new config keys are mock-tested during `async_setup_entry`. | Verify `sv.json` and `en.json` are synced. Validate via local `hassfest` (or via `release.py`). Run `ruff check .` before committing. |
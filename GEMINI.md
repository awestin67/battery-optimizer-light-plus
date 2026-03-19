# GEMINI.md - Battery Optimizer Light HA

This document provides an overview of the Battery Optimizer Light HA project, its structure, and development conventions.

## Project Overview

This is a custom component for Home Assistant designed to optimize the charging and discharging of Sonnen batteries. It operates as a hybrid system, combining a cloud-based service for price-based optimization (arbitrage) with local control for real-time peak shaving. The primary language used in the code and comments is Swedish.

- **Main Technologies:** Python 3, `aiohttp` for asynchronous requests.
- **Architecture:** The integration follows the standard Home Assistant custom component structure. It communicates with a cloud service (default URL: `https://battery-light-production.up.railway.app`) to fetch optimization decisions (`action`, `target_power_kw`, etc.). It then exposes these as sensors within Home Assistant, which can be used in automations to control the battery.

## Building and Running

This is a Home Assistant integration and is not a standalone application. To use it, you must have a running Home Assistant instance.

### Development Setup

1.  **Fork and clone the repository.**
2.  **Set up a Python virtual environment.**
3.  **Install dependencies:**
    ```bash
    pip install -r requirements_test.txt
    ```
    *(Note: A `requirements_test.txt` would need to be created from the dependencies listed in `run_tests.yml`, e.g., `pytest`, `pytest-asyncio`, `aiohttp`, `voluptuous`, `ruff`)*

### Running Tests and Linting

The project uses `pytest` for testing and `ruff` for linting and formatting.

-   **Run tests:**
    ```bash
    pytest tests/
    ```

-   **Run linter:**
    ```bash
    ruff check .
    ```

## Development Conventions

-   **Language:** The codebase, including comments and user-facing strings in the `README.md`, is primarily in **Swedish**.
-   **Linting:** The project uses `ruff` for code linting. Configuration can be found in `pyproject.toml`.
-   **Testing:** Tests are located in the `tests/` directory and are run using `pytest`. The CI pipeline in `.github/workflows/run_tests.yml` validates tests, HACS compatibility, and Home Assistant's `hassfest`.
-   **Configuration:** The integration is configured via the Home Assistant UI (Config Flow). The main configuration options are defined in `custom_components/battery_optimizer_light/config_flow.py`.
-   **Data Flow:**
    1.  The `coordinator.py` polls a cloud API endpoint for optimization data.
    2.  The `sensor.py` file creates multiple sensor entities that expose the data fetched by the coordinator (e.g., charge/discharge commands, power targets, peak limits).
    3.  Users are expected to create automations in Home Assistant that listen to these sensors and execute the corresponding `rest_command` or `script` to control their battery.

## Key Files

-   `custom_components/battery_optimizer_light/`: The root directory for the integration.
    -   `manifest.json`: Contains metadata about the integration (domain, name, version, dependencies).
    -   `config_flow.py`: Manages the setup process through the Home Assistant UI.
    -   `coordinator.py`: Handles fetching data from the cloud API.
    -   `sensor.py`: Defines all the sensor entities created by the integration.
    -   `const.py`: Stores constants like configuration keys, the domain name, and default values.
-   `README.md`: (In Swedish) Provides user-facing installation and configuration instructions.
-   `pyproject.toml`: Contains project metadata and the `ruff` linter configuration.
-   `.github/workflows/run_tests.yml`: CI/CD pipeline definition for running tests, linting, and validation.
-   `tests/test_core.py`: Contains the core unit tests for the integration.

# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.exceptions import ServiceNotFound
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.battery_optimizer_light_plus.batteries.solinteg.solinteg import SolintegBattery

@pytest.fixture
def mock_hass():
    """Skapar en fejkad Home Assistant-instans."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock()
    return hass

@pytest.fixture
def solinteg_battery(mock_hass):
    """Skapar en instans av SolintegBattery för testerna."""
    return SolintegBattery(
        hass=mock_hass,
        device_id="solinteg_inv_1",
        soc_entity="sensor.solinteg_soc",
    )

@pytest.mark.asyncio
async def test_get_current_soc(solinteg_battery, mock_hass):
    """Krav: SoC ska hämtas korrekt från Home Assistant state maskinen."""
    mock_state = MagicMock()
    mock_state.state = "42.5"
    mock_hass.states.get.return_value = mock_state

    soc = await solinteg_battery.get_current_soc()
    assert soc == 42.5
    mock_hass.states.get.assert_called_once_with("sensor.solinteg_soc")

@pytest.mark.asyncio
async def test_get_current_soc_unavailable(solinteg_battery, mock_hass):
    """Krav: Om SoC-sensorn är otillgänglig ska None returneras."""
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state

    soc = await solinteg_battery.get_current_soc()
    assert soc is None

@pytest.mark.asyncio
async def test_get_related_devices(solinteg_battery, mock_hass):
    """Krav: _get_related_devices ska hitta alla enheter kopplade till samma config entry."""
    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "solinteg_inv_1"
        mock_device.config_entries = {"config_entry_1"}

        mock_related_device = MagicMock()
        mock_related_device.id = "solinteg_dongle_1"
        mock_related_device.config_entries = {"config_entry_1"}

        mock_registry.async_get.return_value = mock_device
        mock_registry.devices = {
            "solinteg_inv_1": mock_device,
            "solinteg_dongle_1": mock_related_device,
        }
        mock_dr_get.return_value = mock_registry

        devices = solinteg_battery._get_related_devices()
        assert devices == {"solinteg_inv_1", "solinteg_dongle_1"}

@pytest.mark.asyncio
async def test_find_entity(solinteg_battery, mock_hass):
    """Krav: _find_entity ska dynamiskt leta upp entiteter via unique_id."""
    with patch.object(solinteg_battery, "_get_related_devices", return_value={"solinteg_inv_1"}), \
         patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "select"
        mock_entry.unique_id = "solinteg_working_mode_123"
        mock_entry.entity_id = "select.solinteg_working_mode"
        mock_entries.return_value = [mock_entry]

        entity_id = await solinteg_battery._find_entity("select", "working_mode")
        assert entity_id == "select.solinteg_working_mode"

        entity_id2 = await solinteg_battery._find_entity("select", "missing_mode")
        assert entity_id2 is None

@pytest.mark.asyncio
async def test_apply_action_charge(solinteg_battery, mock_hass):
    """Krav: CHARGE ska sätta EMS BattCtrl och negativ effekt."""
    async def mock_find_entity(domain, partial_key):
        if "working_mode" in partial_key:
            return "select.solinteg_working_mode"
        if "battery_charge_discharge_power_target" in partial_key:
            return "number.solinteg_power_target"
        return None

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("CHARGE", 3.5)

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "EMS BattCtrl"},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solinteg_power_target", "value": -3.5},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_discharge(solinteg_battery, mock_hass):
    """Krav: DISCHARGE ska sätta EMS BattCtrl och positiv effekt."""
    async def mock_find_entity(domain, partial_key):
        if "working_mode" in partial_key:
            return "select.solinteg_working_mode"
        if "battery_charge_discharge_power_target" in partial_key:
            return "number.solinteg_power_target"
        return None

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("DISCHARGE", 4.2)

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "EMS BattCtrl"},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solinteg_power_target", "value": 4.2},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_hold(solinteg_battery, mock_hass):
    """Krav: HOLD ska sätta EMS BattCtrl och effekten till 0."""
    async def mock_find_entity(domain, partial_key):
        if "working_mode" in partial_key:
            return "select.solinteg_working_mode"
        if "battery_charge_discharge_power_target" in partial_key:
            return "number.solinteg_power_target"
        return None

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("HOLD")

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "EMS BattCtrl"},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solinteg_power_target", "value": 0},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_idle(solinteg_battery, mock_hass):
    """Krav: IDLE ska sätta effekten till 0 och sedan byta till General Mode."""
    async def mock_find_entity(domain, partial_key):
        if "working_mode" in partial_key:
            return "select.solinteg_working_mode"
        if "battery_charge_discharge_power_target" in partial_key:
            return "number.solinteg_power_target"
        return None

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("IDLE")

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solinteg_power_target", "value": 0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "General"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_service_not_found(solinteg_battery, mock_hass):
    """Krav: ServiceNotFound fångas och loggas med en varning istället för att krascha."""
    mock_hass.services.async_call.side_effect = ServiceNotFound("select", "select_option")

    async def mock_find_entity(domain, partial_key):
        if "working_mode" in partial_key:
            return "select.solinteg_working_mode"
        if "battery_charge_discharge_power_target" in partial_key:
            return "number.solinteg_power_target"
        return None

    with patch("custom_components.battery_optimizer_light_plus.batteries.solinteg.solinteg._LOGGER") as mock_logger, \
         patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("IDLE")
        mock_logger.warning.assert_called_once()
        assert "Solinteg service call failed" in mock_logger.warning.call_args[0][0]

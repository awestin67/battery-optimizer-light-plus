# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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
    """Krav: _find_entity ska dynamiskt leta upp entiteter."""
    with patch.object(solinteg_battery, "_get_related_devices", return_value={"solinteg_inv_1"}), \
         patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "select"
        mock_entry.unique_id = "working_mode_123"
        mock_entry.object_id = "solinteg_working_mode"
        mock_entry.translation_key = "working_mode"
        mock_entry.entity_id = "select.solinteg_working_mode"

        mock_entries.return_value = [mock_entry]

        entity_id = await solinteg_battery._find_entity("select", ["working_mode"])
        assert entity_id == "select.solinteg_working_mode"

@pytest.mark.asyncio
async def test_apply_action_charge(solinteg_battery, mock_hass):
    """Krav: CHARGE ska sätta Charge-Discharge och negativ effekt i Watt."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={})

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
            {"entity_id": "number.solinteg_power_target", "value": -3500},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_discharge(solinteg_battery, mock_hass):
    """Krav: DISCHARGE ska sätta Charge-Discharge och positiv effekt i Watt."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={})

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
            {"entity_id": "number.solinteg_power_target", "value": 4200},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_hold(solinteg_battery, mock_hass):
    """Krav: HOLD ska sätta Charge-Discharge och effekten till 0."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={})

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
    """Krav: IDLE ska byta till Self Use och INGA set_value anrop ska göras."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={})

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        await solinteg_battery.apply_action("IDLE")

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "General"},
            blocking=True,
        )
        # Verifiera att number.set_value ALDRIG anropades!
        calls = mock_hass.services.async_call.call_args_list
        for mock_call in calls:
            assert mock_call[0][0] != "number", "Number set_value ska inte anropas vid IDLE"

@pytest.mark.asyncio
async def test_apply_action_charge_clamped(solinteg_battery, mock_hass):
    """Krav: Laddning ska begränsas av växelriktarens min-attribut."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": -3000, "max": 5000})

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        # Försök ladda med 4.0 kW (-4000 W). Den ska kapas till -3000.
        await solinteg_battery.apply_action("CHARGE", 4.0)

        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.solinteg_power_target", "value": -3000}, blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_discharge_clamped(solinteg_battery, mock_hass):
    """Krav: Urladdning ska begränsas av växelriktarens max-attribut."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": -5000, "max": 5000})

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        # Försök ladda ur med 7.0 kW (7000 W). Den ska kapas till 5000.
        await solinteg_battery.apply_action("DISCHARGE", 7.0)

        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.solinteg_power_target", "value": 5000}, blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_invert_battery(mock_hass):
    """Krav: Om invert_battery är True ska tecknet vändas (+ för Laddning)."""
    solinteg_battery_inverted = SolintegBattery(
        hass=mock_hass,
        device_id="solinteg_inv_1",
        soc_entity="sensor.solinteg_soc",
        invert_battery=True
    )

    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={})

    with patch.object(solinteg_battery_inverted, "_find_entity", side_effect=mock_find_entity):
        # Testa CHARGE (ska normalt bli -3500, men med invert blir det +3500)
        await solinteg_battery_inverted.apply_action("CHARGE", 3.5)
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.solinteg_power_target", "value": 3500}, blocking=True
        )

        # Testa DISCHARGE (ska normalt bli +3500, men med invert blir det -3500)
        await solinteg_battery_inverted.apply_action("DISCHARGE", 3.5)
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.solinteg_power_target", "value": -3500}, blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_charge_kw(solinteg_battery, mock_hass):
    """Krav: Om Number-entiteten förväntar sig kW ska target_kw användas."""
    async def mock_find_entity(domain, partial_keys):
        if "working_mode" in partial_keys:
            return "select.solinteg_working_mode"
        if "power_target" in partial_keys:
            return "number.solinteg_power_target"
        return None

    # MOCKA ATT ENHETEN ÄR kW!
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    with patch.object(solinteg_battery, "_find_entity", side_effect=mock_find_entity):
        # target_kw = 3.5
        await solinteg_battery.apply_action("CHARGE", 3.5)

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solinteg_power_target", "value": -3.5},
            blocking=True,
        )

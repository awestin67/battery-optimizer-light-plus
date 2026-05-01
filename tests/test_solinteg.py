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

def setup_mock_registry(mock_entries):
    """Hjälpfunktion för att sätta upp entiteter."""
    mock_mode = MagicMock(domain="select", unique_id="working_mode", entity_id="select.solinteg_working_mode")
    mock_power = MagicMock(domain="number", unique_id="power_target", entity_id="number.solinteg_power_target")
    mock_entries.return_value = [mock_mode, mock_power]

@pytest.mark.asyncio
async def test_apply_action_charge(solinteg_battery, mock_hass):
    """Krav: CHARGE ska sätta Charge-Discharge och negativ effekt i Watt."""
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        mock_hass.states.get.return_value = MagicMock(attributes={})

        await solinteg_battery.apply_action("CHARGE", 3.5)

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "Charge-Discharge"},
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
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        mock_hass.states.get.return_value = MagicMock(attributes={})

        await solinteg_battery.apply_action("DISCHARGE", 4.2)

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "Charge-Discharge"},
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
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        mock_hass.states.get.return_value = MagicMock(attributes={})

        await solinteg_battery.apply_action("HOLD")

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "Charge-Discharge"},
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
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        mock_hass.states.get.return_value = MagicMock(attributes={})

        await solinteg_battery.apply_action("IDLE")

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solinteg_working_mode", "option": "Self Use"},
            blocking=True,
        )
        # Verifiera att number.set_value ALDRIG anropades!
        calls = mock_hass.services.async_call.call_args_list
        for mock_call in calls:
            assert mock_call[0][0] != "number", "Number set_value ska inte anropas vid IDLE"

@pytest.mark.asyncio
async def test_apply_action_charge_clamped(solinteg_battery, mock_hass):
    """Krav: Laddning ska begränsas av växelriktarens min-attribut."""
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        # Sätt max laddning (min) till -3000 W
        mock_hass.states.get.return_value = MagicMock(attributes={"min": -3000, "max": 5000})

        # Försök ladda med 4.0 kW (-4000 W). Den ska kapas till -3000.
        await solinteg_battery.apply_action("CHARGE", 4.0)

        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.solinteg_power_target", "value": -3000}, blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_discharge_clamped(solinteg_battery, mock_hass):
    """Krav: Urladdning ska begränsas av växelriktarens max-attribut."""
    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        # Sätt max urladdning (max) till 5000 W
        mock_hass.states.get.return_value = MagicMock(attributes={"min": -5000, "max": 5000})

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

    with patch("homeassistant.helpers.entity_registry.async_get"), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        setup_mock_registry(mock_entries)
        mock_hass.states.get.return_value = MagicMock(attributes={})

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

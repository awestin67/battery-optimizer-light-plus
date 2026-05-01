# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.exceptions import ServiceNotFound
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.battery_optimizer_light_plus.batteries.sigenergy.sigenergy import SigenergyBattery

@pytest.fixture
def mock_hass():
    """Skapar en fejkad Home Assistant-instans."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    mock_state = MagicMock()
    mock_state.attributes = {}
    hass.states.get = MagicMock(return_value=mock_state)
    return hass

@pytest.fixture
def sigenergy_battery(mock_hass):
    """Skapar en instans av SigenergyBattery för testerna."""
    return SigenergyBattery(
        hass=mock_hass,
        device_id="sig_inv_1",
        soc_entity="sensor.sig_soc",
    )

@pytest.mark.asyncio
async def test_get_current_soc(sigenergy_battery, mock_hass):
    """Krav: SoC ska hämtas korrekt från Home Assistant state maskinen."""
    mock_state = MagicMock()
    mock_state.state = "42.5"
    mock_hass.states.get.return_value = mock_state

    soc = await sigenergy_battery.get_current_soc()
    assert soc == 42.5
    mock_hass.states.get.assert_called_once_with("sensor.sig_soc")

@pytest.mark.asyncio
async def test_get_current_soc_unavailable(sigenergy_battery, mock_hass):
    """Krav: Om SoC-sensorn är otillgänglig ska None returneras."""
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state

    soc = await sigenergy_battery.get_current_soc()
    assert soc is None

@pytest.mark.asyncio
async def test_get_related_devices(sigenergy_battery, mock_hass):
    """Krav: _get_related_devices ska hitta alla enheter kopplade till samma config entry."""
    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "sig_inv_1"
        mock_device.config_entries = {"config_entry_1"}

        mock_related_device = MagicMock()
        mock_related_device.id = "sig_dongle_1"
        mock_related_device.config_entries = {"config_entry_1"}

        mock_registry.async_get.return_value = mock_device
        mock_registry.devices = {
            "sig_inv_1": mock_device,
            "sig_dongle_1": mock_related_device,
        }
        mock_dr_get.return_value = mock_registry

        devices = sigenergy_battery._get_related_devices()
        assert devices == {"sig_inv_1", "sig_dongle_1"}

@pytest.mark.asyncio
async def test_find_entity(sigenergy_battery, mock_hass):
    """Krav: _find_entity ska dynamiskt leta upp entiteter via translation_key eller object_id."""
    with patch.object(sigenergy_battery, "_get_related_devices", return_value={"sig_inv_1"}), \
         patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "select"
        mock_entry.translation_key = "ems_control_mode"
        mock_entry.object_id = "sig_ems_control_mode"
        mock_entry.entity_id = "select.sig_ems_control_mode"

        mock_entries.return_value = [mock_entry]

        entity_id = await sigenergy_battery._find_entity("select", "ems_control_mode")
        assert entity_id == "select.sig_ems_control_mode"

        entity_id2 = await sigenergy_battery._find_entity("select", "control_mode")
        assert entity_id2 == "select.sig_ems_control_mode"

@pytest.mark.asyncio
async def test_apply_action_charge(sigenergy_battery, mock_hass):
    """Krav: CHARGE ska sätta EMS Control Mode och Max Charging Limit i kW via dynamisk uppslagning."""
    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_charging_limit":
            return "number.sig_max_charging_limit"
        return None

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("CHARGE", 3.5)

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_charging_limit", "value": 3.5},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.sig_ems_control_mode", "option": "Command Charging (PV First)"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_discharge(sigenergy_battery, mock_hass):
    """Krav: DISCHARGE ska sätta EMS Control Mode och Max Discharging Limit i kW via dynamisk uppslagning."""
    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_discharging_limit":
            return "number.sig_max_discharging_limit"
        return None

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("DISCHARGE", 4.2)
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_discharging_limit", "value": 4.2},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.sig_ems_control_mode", "option": "Command Discharging (PV First)"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_hold(sigenergy_battery, mock_hass):
    """Krav: HOLD ska sätta laddnings- och urladdningsgränsen till 0W och aktivera Hold-läget."""
    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_charging_limit":
            return "number.sig_max_charging_limit"
        if partial_key == "max_discharging_limit":
            return "number.sig_max_discharging_limit"
        return None

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("HOLD")
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_charging_limit", "value": 0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_discharging_limit", "value": 0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.sig_ems_control_mode", "option": "Standby"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_idle(sigenergy_battery, mock_hass):
    """Krav: IDLE ska återställa max urladdnings/laddningsgräns och aktivera Maximum Self Consumption."""
    mock_state = MagicMock()
    mock_state.attributes = {"max": 100.0}
    mock_hass.states.get.return_value = mock_state

    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_charging_limit":
            return "number.sig_max_charging_limit"
        if partial_key == "max_discharging_limit":
            return "number.sig_max_discharging_limit"
        return None

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("IDLE")
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_discharging_limit", "value": 100.0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_charging_limit", "value": 100.0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.sig_ems_control_mode", "option": "Maximum Self Consumption"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_idle_fallback(sigenergy_battery, mock_hass):
    """Krav: IDLE ska falla tillbaka på 15.0 kW om max-attributet saknas på sensorn."""
    mock_state = MagicMock()
    mock_state.attributes = {}  # Saknar 'max' attribut
    mock_hass.states.get.return_value = mock_state

    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_charging_limit":
            return "number.sig_max_charging_limit"
        return None

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("IDLE")
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_charging_limit", "value": 15.0},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_service_not_found(sigenergy_battery, mock_hass):
    """Krav: ServiceNotFound fångas och loggas med en varning istället för att krascha."""
    mock_hass.services.async_call.side_effect = ServiceNotFound("select", "select_option")

    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        return None

    with patch("custom_components.battery_optimizer_light_plus.batteries.sigenergy.sigenergy._LOGGER") as mock_logger, \
         patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):

        await sigenergy_battery.apply_action("IDLE")
        mock_logger.warning.assert_called_once()
        assert "Sigenergy service call failed" in mock_logger.warning.call_args[0][0]

@pytest.mark.asyncio
async def test_apply_action_charge_clamped(sigenergy_battery, mock_hass):
    """Krav: Laddning ska begränsas av växelriktarens max-attribut."""
    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_charging_limit":
            return "number.sig_max_charging_limit"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": 0, "max": 5.0})

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("CHARGE", 7.0)

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_charging_limit", "value": 5.0},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_discharge_clamped(sigenergy_battery, mock_hass):
    """Krav: Urladdning ska begränsas av växelriktarens max-attribut."""
    async def mock_find_entity(domain, partial_key):
        if partial_key == "ems_control_mode":
            return "select.sig_ems_control_mode"
        if partial_key == "max_discharging_limit":
            return "number.sig_max_discharging_limit"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": 0, "max": 5.0})

    with patch.object(sigenergy_battery, "_find_entity", side_effect=mock_find_entity):
        await sigenergy_battery.apply_action("DISCHARGE", 7.0)

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.sig_max_discharging_limit", "value": 5.0},
            blocking=True,
        )

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
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import ServiceNotFound

from custom_components.battery_optimizer_light_plus.batteries.solis_modbus.solis_modbus import SolisModbusBattery


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
def solis_battery(mock_hass):
    """Skapar en instans av SolisModbusBattery för testerna."""
    return SolisModbusBattery(
        hass=mock_hass,
        device_id="solis_inv_1",
        soc_entity="sensor.soc",
    )


@pytest.mark.asyncio
async def test_get_current_soc(solis_battery, mock_hass):
    """Krav: SoC ska hämtas korrekt från Home Assistant state maskinen."""
    mock_state = MagicMock()
    mock_state.state = "55.5"
    mock_hass.states.get.return_value = mock_state

    soc = await solis_battery.get_current_soc()
    assert soc == 55.5
    mock_hass.states.get.assert_called_once_with("sensor.soc")


@pytest.mark.asyncio
async def test_get_current_soc_unavailable(solis_battery, mock_hass):
    """Krav: Om SoC-sensorn är otillgänglig ska None returneras."""
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state

    soc = await solis_battery.get_current_soc()
    assert soc is None


@pytest.mark.asyncio
async def test_get_related_devices(solis_battery, mock_hass):
    """Krav: _get_related_devices ska hitta alla enheter kopplade till samma config entry."""
    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_registry = MagicMock()

        mock_device = MagicMock()
        mock_device.id = "solis_inv_1"
        mock_device.config_entries = {"config_entry_1"}

        mock_related_device = MagicMock()
        mock_related_device.id = "solis_dongle_1"
        mock_related_device.config_entries = {"config_entry_1"}

        mock_other_device = MagicMock()
        mock_other_device.id = "other_device"
        mock_other_device.config_entries = {"config_entry_2"}

        mock_registry.async_get.return_value = mock_device
        mock_registry.devices = {
            "solis_inv_1": mock_device,
            "solis_dongle_1": mock_related_device,
            "other_device": mock_other_device
        }
        mock_dr_get.return_value = mock_registry

        devices = solis_battery._get_related_devices()
        assert devices == {"solis_inv_1", "solis_dongle_1"}


@pytest.mark.asyncio
async def test_find_entity(solis_battery, mock_hass):
    """Krav: _find_entity ska dynamiskt leta upp entiteter via translation_key eller object_id."""
    with patch.object(solis_battery, "_get_related_devices", return_value={"solis_inv_1"}), \
         patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:

        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "select"
        mock_entry.translation_key = "rc_force_charge_discharge"
        mock_entry.object_id = "solis_rc_mode"
        mock_entry.entity_id = "select.solis_rc_mode"

        mock_entries.return_value = [mock_entry]

        # Test by translation_key
        entity_id = await solis_battery._find_entity("select", ["rc_force_charge_discharge"])
        assert entity_id == "select.solis_rc_mode"

        # Test by object_id partial match
        entity_id2 = await solis_battery._find_entity("select", ["rc_mode"])
        assert entity_id2 == "select.solis_rc_mode"

        # Test not found
        entity_id3 = await solis_battery._find_entity("number", ["missing_key"])
        assert entity_id3 is None

def test_get_rc_option(solis_battery):
    """Krav: _get_rc_option ska välja rätt driftläge oavsett exakt stavning i dropdown-menyn."""
    mock_state = MagicMock()
    mock_state.attributes = {
        "options": [
            "Solis RC Force Battery Charge",
            "Solis RC Force Battery Discharge",
            "Self Use",
            "Auto",
            "None"
        ]
    }
    solis_battery._hass.states.get.return_value = mock_state

    opt_charge = solis_battery._get_rc_option("select.dummy", "charge")
    assert opt_charge == "Solis RC Force Battery Charge"

    opt_discharge = solis_battery._get_rc_option("select.dummy", "discharge")
    assert opt_discharge == "Solis RC Force Battery Discharge"

    opt_none_1 = solis_battery._get_rc_option("select.dummy", "none")
    assert opt_none_1 in ("Self Use", "Auto", "None")  # Någon av dessa är acceptabel

    # Testar fallback om sensorn saknas
    solis_battery._hass.states.get.return_value = None
    assert solis_battery._get_rc_option("select.dummy", "charge") == "Solis RC Force Battery Charge"
    assert solis_battery._get_rc_option("select.dummy", "discharge") == "Solis RC Force Battery Discharge"
    assert solis_battery._get_rc_option("select.dummy", "none") == "None"

@pytest.mark.asyncio
async def test_get_status_text(solis_battery):
    """Krav: get_status_text ska hämta rätt värde om device_status_entity är satt."""
    solis_battery._device_status_entity = "sensor.solis_status"
    mock_state = MagicMock()
    mock_state.state = "Working"
    solis_battery._hass.states.get.return_value = mock_state

    status = await solis_battery.get_status_text()
    assert status == "Working"
    solis_battery._hass.states.get.assert_called_with("sensor.solis_status")

@pytest.mark.asyncio
async def test_get_solar_power(solis_battery, mock_hass):
    """Krav: Solis solproduktion ska hämtas och returneras i Watt."""
    mock_state = MagicMock()
    mock_state.state = "4.2"
    mock_state.attributes = {"unit_of_measurement": "kW"}
    mock_hass.states.get.return_value = mock_state

    async def mock_find_entity(domain, partial_keys):
        if "pv_total_power" in partial_keys:
            return "sensor.solis_pv_total_power"
        return None

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        power = await solis_battery.get_solar_power()
        assert power == 4200.0
        mock_hass.states.get.assert_called_once_with("sensor.solis_pv_total_power")

@pytest.mark.asyncio
async def test_get_solar_power_invalid(solis_battery, mock_hass):
    """Krav: get_solar_power ska hantera ogiltiga värden snyggt."""
    mock_state = MagicMock()
    mock_state.state = "invalid_value"
    mock_hass.states.get.return_value = mock_state

    with patch.object(solis_battery, "_find_entity", return_value="sensor.solis_pv"):
        assert await solis_battery.get_solar_power() is None

    # Testa STATE_UNAVAILABLE
    mock_state.state = STATE_UNAVAILABLE
    with patch.object(solis_battery, "_find_entity", return_value="sensor.solis_pv"):
        assert await solis_battery.get_solar_power() is None

@pytest.mark.asyncio
async def test_get_solar_power_none(solis_battery):
    """Krav: get_solar_power ska returnera None om sensorn inte hittas."""
    with patch.object(solis_battery, "_find_entity", return_value=None):
        power = await solis_battery.get_solar_power()
        assert power is None

@pytest.mark.asyncio
async def test_apply_action_charge(solis_battery, mock_hass):
    """Krav: Solis CHARGE ska sätta RC Mode, Charge Power och uppdatera Timeout via dynamisk uppslagning."""
    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "rc_force_charge_power" in partial_keys:
            return "number.solis_charge_power"
        if "rc_timeout" in partial_keys:
            return "number.solis_rc_timeout"
        return None

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("CHARGE", 3.5)

        # Verifiera att RC Timeout sattes till 15 minuter
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value",
            {"entity_id": "number.solis_rc_timeout", "value": 15},
            blocking=False
        )
        # Verifiera att effekten 3.5 kW blev 3500 W
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value",
            {"entity_id": "number.solis_charge_power", "value": 3500},
            blocking=True
        )
        # Verifiera att rätt läge aktiverades
        mock_hass.services.async_call.assert_any_call(
            "select", "select_option",
            {"entity_id": "select.solis_rc_mode", "option": "Solis RC Force Battery Charge"},
            blocking=True
        )


@pytest.mark.asyncio
async def test_apply_action_discharge(solis_battery, mock_hass):
    """Krav: Solis DISCHARGE ska sätta RC Mode, Discharge Power och uppdatera Timeout."""
    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "rc_force_discharge_power" in partial_keys:
            return "number.solis_discharge_power"
        if "rc_timeout" in partial_keys:
            return "number.solis_rc_timeout"
        if "battery_discharge_limit_power" in partial_keys:
            return "number.solis_discharge_limit"
        return None

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("DISCHARGE", 4.2)
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_rc_timeout", "value": 15},
            blocking=False
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_discharge_power", "value": 4200},
            blocking=True
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solis_rc_mode", "option": "Solis RC Force Battery Discharge"},
            blocking=True
        )


@pytest.mark.asyncio
async def test_apply_action_hold(solis_battery, mock_hass):
    """Krav: Solis HOLD ska sätta urladdningsgränsen till 0W och stänga av RC Mode."""
    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "battery_discharge_limit_power" in partial_keys:
            return "number.solis_discharge_limit"
        if "rc_timeout" in partial_keys:
            return "number.solis_rc_timeout"
        return None

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("HOLD")
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_rc_timeout", "value": 15},
            blocking=False
        )
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_discharge_limit", "value": 0},
            blocking=True
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solis_rc_mode", "option": "None"},
            blocking=True
        )


@pytest.mark.asyncio
async def test_apply_action_idle(solis_battery, mock_hass):
    """Krav: Solis IDLE ska återställa urladdningsgränsen till MAX och RC Mode till None (Auto)."""
    mock_state = MagicMock()
    mock_state.attributes = {"max": 6000}
    mock_hass.states.get.return_value = mock_state

    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "battery_discharge_limit_power" in partial_keys:
            return "number.solis_discharge_limit"
        return None

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("IDLE")
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_discharge_limit", "value": 6000},
            blocking=True
        )
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.solis_rc_mode", "option": "None"},
            blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_charge_clamped(solis_battery, mock_hass):
    """Krav: Solis CHARGE ska begränsas av växelriktarens max-attribut."""
    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "rc_force_charge_power" in partial_keys:
            return "number.solis_charge_power"
        if "rc_timeout" in partial_keys:
            return "number.solis_rc_timeout"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": 0, "max": 3000})

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("CHARGE", 4.0)

        mock_hass.services.async_call.assert_any_call(
            "number", "set_value",
            {"entity_id": "number.solis_charge_power", "value": 3000},
            blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_discharge_clamped(solis_battery, mock_hass):
    """Krav: Solis DISCHARGE ska begränsas av växelriktarens max-attribut."""
    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        if "rc_force_discharge_power" in partial_keys:
            return "number.solis_discharge_power"
        if "rc_timeout" in partial_keys:
            return "number.solis_rc_timeout"
        if "battery_discharge_limit_power" in partial_keys:
            return "number.solis_discharge_limit"
        return None

    mock_hass.states.get.return_value = MagicMock(attributes={"min": 0, "max": 3000})

    with patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):
        await solis_battery.apply_action("DISCHARGE", 4.0)

        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.solis_discharge_power", "value": 3000},
            blocking=True
        )

@pytest.mark.asyncio
async def test_apply_action_service_not_found(solis_battery, mock_hass):
    """Krav: ServiceNotFound fångas och loggas med en varning istället för att krascha."""
    mock_hass.services.async_call.side_effect = ServiceNotFound("number", "set_value")

    async def mock_find_entity(domain, partial_keys):
        if "rc_force_charge_discharge" in partial_keys:
            return "select.solis_rc_mode"
        return None

    patch_logger = "custom_components.battery_optimizer_light_plus.batteries.solis_modbus.solis_modbus._LOGGER"
    with patch(patch_logger) as mock_logger, \
         patch.object(solis_battery, "_find_entity", side_effect=mock_find_entity):

        await solis_battery.apply_action("IDLE")
        mock_logger.warning.assert_called_once()
        assert "Solis service not found" in mock_logger.warning.call_args[0][0]

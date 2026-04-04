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
from custom_components.battery_optimizer_light_plus.battery_factory import create_battery_api
from homeassistant.exceptions import ServiceNotFound
from custom_components.battery_optimizer_light_plus.batteries.huawei.huawei import HuaweiBattery
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_HUAWEI,
    CONF_BATTERY_DEVICE_ID,
    CONF_DEVICE_STATUS_ENTITY,
    CONF_SOC_SENSOR,
)

@pytest.mark.asyncio
async def test_create_huawei_battery():
    """Test the instantiation of HuaweiBattery through the factory."""
    hass = MagicMock()
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI,
        CONF_BATTERY_DEVICE_ID: "test_device_id",
        CONF_DEVICE_STATUS_ENTITY: "sensor.huawei_status",
        CONF_SOC_SENSOR: "sensor.huawei_soc",
    }

    battery_api = create_battery_api(hass, config)

    assert isinstance(battery_api, HuaweiBattery)

@pytest.fixture
def huawei_battery():
    """Skapar en instans av HuaweiBattery med en mockad Home Assistant."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock()
    return HuaweiBattery(
        hass=hass,
        device_id="test_device_id",
        soc_entity="sensor.huawei_soc"
    )

@pytest.mark.asyncio
async def test_get_status_text(huawei_battery):
    """Testar att enhetsstatus hämtas korrekt för PeakGuard."""
    huawei_battery._device_status_entity = "sensor.huawei_status"
    mock_state = MagicMock()
    mock_state.state = "On-grid"
    huawei_battery._hass.states.get.return_value = mock_state

    status = await huawei_battery.get_status_text()
    assert status == "On-grid"
    huawei_battery._hass.states.get.assert_called_with("sensor.huawei_status")

@pytest.mark.asyncio
async def test_get_current_soc_valid(huawei_battery):
    """Testar att SoC hämtas korrekt när sensorn har ett giltigt värde."""
    mock_state = MagicMock()
    mock_state.state = "45.5"
    huawei_battery._hass.states.get.return_value = mock_state

    soc = await huawei_battery.get_current_soc()
    assert soc == 45.5
    huawei_battery._hass.states.get.assert_called_once_with("sensor.huawei_soc")

@pytest.mark.asyncio
async def test_get_current_soc_invalid(huawei_battery):
    """Testar att get_current_soc returnerar None om sensorn är ogiltig."""
    mock_state = MagicMock()
    mock_state.state = "unavailable"
    huawei_battery._hass.states.get.return_value = mock_state

    soc = await huawei_battery.get_current_soc()
    assert soc is None

@pytest.mark.asyncio
async def test_apply_action_charge(huawei_battery):
    """Testar att CHARGE översätts till forcible_charge."""
    await huawei_battery.apply_action("CHARGE", target_kw=3.5)

    # 3.5 kW ska bli 3500 W
    huawei_battery._hass.services.async_call.assert_called_once_with(
        "huawei_solar", "forcible_charge",
        {"device_id": "test_device_id", "power": 3500, "duration": 60},
        blocking=True
    )

@pytest.mark.asyncio
async def test_apply_action_discharge(huawei_battery):
    """Testar att DISCHARGE översätts till forcible_discharge."""
    await huawei_battery.apply_action("DISCHARGE", target_kw=2.0)

    huawei_battery._hass.services.async_call.assert_called_once_with(
        "huawei_solar", "forcible_discharge",
        {"device_id": "test_device_id", "power": 2000, "duration": 60},
        blocking=True
    )

@pytest.mark.asyncio
async def test_apply_action_hold(huawei_battery):
    """Testar att HOLD sätter max urladdning till 0 och stoppar forcible charge."""
    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:
        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "number"
        mock_entry.translation_key = "maximum_discharging_power"
        mock_entry.entity_id = "number.battery_max_discharge"
        mock_entries.return_value = [mock_entry]

        mock_state = MagicMock()
        mock_state.state = "5000"
        huawei_battery._hass.states.get.return_value = mock_state

        await huawei_battery.apply_action("HOLD")

        huawei_battery._hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.battery_max_discharge", "value": 0},
            blocking=True,
        )
        huawei_battery._hass.services.async_call.assert_any_call(
            "huawei_solar",
            "stop_forcible_charge",
            {"device_id": "test_device_id"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_idle_restores_discharge(huawei_battery):
    """Testar att IDLE återställer max urladdningseffekt om den är 0."""
    # Mocka Coordinator-data för att testa The Restart Trap (Skydd #1)
    mock_coord = MagicMock()
    mock_coord.data = {"max_discharge_kw": 4.5}
    huawei_battery._hass.data = {"battery_optimizer_light_plus": {"test_entry": mock_coord}}

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries:
        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "number"
        mock_entry.translation_key = "maximum_discharging_power"
        mock_entry.entity_id = "number.battery_max_discharge"
        mock_entries.return_value = [mock_entry]

        mock_state = MagicMock()
        mock_state.state = "0"
        mock_state.attributes = {"max": 5000.0}
        huawei_battery._hass.states.get.return_value = mock_state

        await huawei_battery.apply_action("IDLE")

        # 4.5 kW från cloud datan = 4500 W
        huawei_battery._hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.battery_max_discharge", "value": 4500.0},
            blocking=True,
        )
        huawei_battery._hass.services.async_call.assert_any_call(
            "huawei_solar",
            "stop_forcible_charge",
            {"device_id": "test_device_id"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_apply_action_idle(huawei_battery):
    """Testar att IDLE släpper spärren med stop_forcible_charge."""
    await huawei_battery.apply_action("IDLE")

    huawei_battery._hass.services.async_call.assert_called_once_with(
        "huawei_solar", "stop_forcible_charge", {"device_id": "test_device_id"}, blocking=True
    )

@pytest.mark.asyncio
async def test_apply_action_service_not_found(huawei_battery):
    """Test that ServiceNotFound is caught and logged gracefully."""
    huawei_battery._hass.services.async_call.side_effect = ServiceNotFound(
        "huawei_solar", "forcible_charge"
    )

    with patch("custom_components.battery_optimizer_light_plus.batteries.huawei.huawei._LOGGER") as mock_logger:
        # This call should not raise an exception
        await huawei_battery.apply_action("CHARGE", target_kw=2.0)

        mock_logger.warning.assert_called_once()
        assert "Huawei service not found" in mock_logger.warning.call_args[0][0]

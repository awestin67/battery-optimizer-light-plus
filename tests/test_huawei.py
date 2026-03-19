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
from unittest.mock import MagicMock, AsyncMock
from custom_components.battery_optimizer_light.battery_factory import create_battery_api
from custom_components.battery_optimizer_light.batteries.huawei.huawei import HuaweiBattery
from custom_components.battery_optimizer_light.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_HUAWEI,
    CONF_BATTERY_DEVICE_ID,
    CONF_WORKING_MODE_ENTITY,
    CONF_SOC_SENSOR,
)

@pytest.mark.asyncio
async def test_create_huawei_battery():
    """Test the instantiation of HuaweiBattery through the factory."""
    hass = MagicMock()
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI,
        CONF_BATTERY_DEVICE_ID: "test_device_id",
        CONF_WORKING_MODE_ENTITY: "select.huawei_working_mode",
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
        working_mode_entity="select.huawei_working_mode",
        soc_entity="sensor.huawei_soc"
    )

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
        {"device_id": "test_device_id", "power": 3500, "duration": 60}
    )

@pytest.mark.asyncio
async def test_apply_action_discharge(huawei_battery):
    """Testar att DISCHARGE översätts till forcible_discharge."""
    await huawei_battery.apply_action("DISCHARGE", target_kw=2.0)

    huawei_battery._hass.services.async_call.assert_called_once_with(
        "huawei_solar", "forcible_discharge",
        {"device_id": "test_device_id", "power": 2000, "duration": 60}
    )

@pytest.mark.asyncio
async def test_apply_action_hold(huawei_battery):
    """Testar att HOLD stoppar laddning och sätter läge till fixed_charge_discharge."""
    await huawei_battery.apply_action("HOLD")

    calls = huawei_battery._hass.services.async_call.call_args_list
    assert len(calls) == 2

    # Första anropet ska vara stop_forcible_charge
    assert calls[0][0] == ("huawei_solar", "stop_forcible_charge", {"device_id": "test_device_id"})

    # Andra anropet ska ändra select_option
    assert calls[1][0] == (
        "select",
        "select_option",
        {"entity_id": "select.huawei_working_mode", "option": "fixed_charge_discharge"}
    )

@pytest.mark.asyncio
async def test_apply_action_idle(huawei_battery):
    """Testar att IDLE stoppar laddning och sätter läge till maximise_self_consumption."""
    await huawei_battery.apply_action("IDLE")

    calls = huawei_battery._hass.services.async_call.call_args_list
    assert len(calls) == 2

    # Första anropet ska vara stop_forcible_charge
    assert calls[0][0] == ("huawei_solar", "stop_forcible_charge", {"device_id": "test_device_id"})

    # Andra anropet ska ändra select_option
    assert calls[1][0] == (
        "select",
        "select_option",
        {"entity_id": "select.huawei_working_mode", "option": "maximise_self_consumption"}
    )

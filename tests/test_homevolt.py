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
from custom_components.battery_optimizer_light_plus.battery_factory import create_battery_api
from custom_components.battery_optimizer_light_plus.batteries.homevolt.homevolt import HomevoltBattery
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_HOMEVOLT,
    CONF_BATTERY_DEVICE_ID,
    CONF_SOC_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
)

@pytest.mark.asyncio
async def test_create_homevolt_battery():
    """Test the instantiation of HomevoltBattery through the factory."""
    hass = MagicMock()
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_HOMEVOLT,
        CONF_BATTERY_DEVICE_ID: "test_device_id",
        CONF_SOC_SENSOR: "sensor.homevolt_soc",
        CONF_BATTERY_POWER_SENSOR: "sensor.homevolt_power",
    }

    battery_api = create_battery_api(hass, config)

    assert isinstance(battery_api, HomevoltBattery)

@pytest.fixture
def homevolt_battery():
    """Creates an instance of HomevoltBattery with a mocked Home Assistant."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock()
    return HomevoltBattery(
        hass=hass,
        device_id="test_device_id",
        soc_entity="sensor.homevolt_soc",
        grid_entity="sensor.homevolt_grid",
        battery_power_entity="sensor.homevolt_power",
        load_entity=None,
        status_entity=None,
    )

@pytest.mark.asyncio
async def test_apply_action_charge(homevolt_battery):
    """Test that CHARGE is translated to add_schedule with mode 'charge'."""
    await homevolt_battery.apply_action("CHARGE", target_kw=3.5)

    # 3.5 kW should be 3500 W
    service_data = homevolt_battery._hass.services.async_call.call_args[0][2]
    assert service_data["device_id"] == "test_device_id"
    assert service_data["mode"] == "charge"
    assert service_data["setpoint"] == 3500

@pytest.mark.asyncio
async def test_apply_action_discharge(homevolt_battery):
    """Test that DISCHARGE is translated to add_schedule with mode 'discharge'."""
    await homevolt_battery.apply_action("DISCHARGE", target_kw=2.0)

    service_data = homevolt_battery._hass.services.async_call.call_args[0][2]
    assert service_data["device_id"] == "test_device_id"
    assert service_data["mode"] == "discharge"
    assert service_data["setpoint"] == 2000

@pytest.mark.asyncio
async def test_apply_action_hold(homevolt_battery):
    """Test that HOLD is translated to add_schedule with mode 'manual' and 0 setpoint."""
    await homevolt_battery.apply_action("HOLD")

    service_data = homevolt_battery._hass.services.async_call.call_args[0][2]
    assert service_data["device_id"] == "test_device_id"
    assert service_data["mode"] == "manual"
    assert service_data["setpoint"] == 0

@pytest.mark.asyncio
async def test_apply_action_idle(homevolt_battery):
    """Test that IDLE is translated to add_schedule with mode 'auto'."""
    await homevolt_battery.apply_action("IDLE")

    service_data = homevolt_battery._hass.services.async_call.call_args[0][2]
    assert service_data["device_id"] == "test_device_id"
    assert service_data["mode"] == "auto"
    assert service_data["setpoint"] == 0

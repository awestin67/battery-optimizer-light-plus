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
from unittest.mock import MagicMock, patch
from custom_components.battery_optimizer_light_plus.sensor import (
    async_setup_entry,
    BatteryLightActionSensor,
    BatteryLightPowerSensor,
    BatteryLightReasonSensor,
    BatteryLightBufferSensor,
    BatteryLightPeakSensor,
    BatteryLightChargeTargetSensor,
    BatteryLightDischargeTargetSensor,
    BatteryLightVirtualLoadSensor,
    HuaweiWrapperSensor,
    SonnenInternalSensor,
    SonnenVirtualLoadSensor
)
from custom_components.battery_optimizer_light_plus.const import (
    DOMAIN,
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_GENERIC
)

@pytest.mark.asyncio
async def test_sensor_setup_entry_generic():
    hass = MagicMock()
    entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC})
    hass.data = {DOMAIN: {entry.entry_id: MagicMock()}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()
    assert len(async_add_entities.call_args[0][0]) == 9

@pytest.mark.asyncio
async def test_sensor_setup_entry_huawei():
    hass = MagicMock()
    entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI})
    coordinator = MagicMock()
    coordinator.config = {"working_mode_entity": "s.mode", "device_status_entity": "s.status"}
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    assert len(async_add_entities.call_args[0][0]) == 11

@pytest.mark.asyncio
async def test_sensor_setup_entry_sonnen():
    hass = MagicMock()
    entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN})
    coordinator = MagicMock()
    coordinator.battery_api.coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    assert len(async_add_entities.call_args[0][0]) == 15

def test_basic_sensors():
    coordinator = MagicMock()
    coordinator.api_key = "12345"
    coordinator.data = {
        "action": "CHARGE",
        "target_power_kw": 5.5,
        "reason": "Cheap price",
        "min_soc_buffer": 20.0,
        "peak_power_kw": 10.0
    }

    action_sensor = BatteryLightActionSensor(coordinator)
    assert action_sensor.state == "CHARGE"

    coordinator.peak_guard = MagicMock(is_solar_override=True)
    coordinator.peak_guard.is_active = False
    coordinator.data["action"] = "HOLD"
    assert action_sensor.state == "IDLE"
    coordinator.peak_guard.is_solar_override = False

    power_sensor = BatteryLightPowerSensor(coordinator)
    assert power_sensor.state == 5.5
    assert power_sensor.device_info["identifiers"] == {(DOMAIN, "12345")}

    reason_sensor = BatteryLightReasonSensor(coordinator)
    assert reason_sensor.state == "Cheap price"

    coordinator.peak_guard.is_active = True
    assert reason_sensor.state == "Local Peak Guard Triggered"

    coordinator.peak_guard.is_active = False
    coordinator.peak_guard.is_solar_override = True
    assert reason_sensor.state == "Solar Override (Local)"

    assert BatteryLightBufferSensor(coordinator).state == 20.0
    assert BatteryLightPeakSensor(coordinator).state == 10.0

    coordinator.data["action"] = "CHARGE"
    assert BatteryLightChargeTargetSensor(coordinator).state == 5500

    coordinator.data["action"] = "DISCHARGE"
    assert BatteryLightDischargeTargetSensor(coordinator).state == 5500

    # Testa felhantering när data är None
    coordinator.data = None
    assert BatteryLightActionSensor(coordinator).state == "UNKNOWN"
    assert BatteryLightPowerSensor(coordinator).state == 0.0
    assert BatteryLightBufferSensor(coordinator).state == 0.0
    assert BatteryLightPeakSensor(coordinator).state == 12.0
    assert BatteryLightChargeTargetSensor(coordinator).state == 0
    assert BatteryLightDischargeTargetSensor(coordinator).state == 0

    delattr(coordinator, "peak_guard")
    assert BatteryLightReasonSensor(coordinator).state == "Unknown"

@pytest.mark.asyncio
async def test_huawei_wrapper_sensor():
    coordinator = MagicMock(api_key="123")
    sensor = HuaweiWrapperSensor(coordinator, "sensor.test", "Test", "test_id", "mdi:test")

    state_obj = MagicMock(state="Active")
    coordinator.hass.states.get.return_value = state_obj
    assert sensor.state == "Active"

    state_obj.state = "unavailable"
    assert sensor.state is None

    sensor._source_entity = None
    assert sensor.state is None

    patch_target = "custom_components.battery_optimizer_light_plus.sensor.async_track_state_change_event"
    with patch(patch_target) as mock_track:
        sensor._source_entity = "sensor.test"
        await sensor.async_added_to_hass()
        mock_track.assert_called_once()

    sensor.async_write_ha_state = MagicMock()
    sensor._update_state(None)
    sensor.async_write_ha_state.assert_called_once()

def test_sonnen_internal_sensor():
    main_coordinator = MagicMock(api_key="123")
    sonnen_coord = MagicMock(data={"TestKey": "12.5", "StringKey": "Status"})

    sensor1 = SonnenInternalSensor(main_coordinator, sonnen_coord, "TestKey", "T", "W", "power")
    assert sensor1.state == 12.5
    assert sensor1.device_info["identifiers"] == {(DOMAIN, "123")}

    sensor2 = SonnenInternalSensor(main_coordinator, sonnen_coord, "StringKey", "T", None, None)
    assert sensor2.state == "Status"

    sensor3 = SonnenInternalSensor(main_coordinator, sonnen_coord, "MissingKey", "T", None, None)
    assert sensor3.state is None

    sonnen_coord.data["BadFloat"] = "NotAFloat"
    sensor4 = SonnenInternalSensor(main_coordinator, sonnen_coord, "BadFloat", "T", None, "power")
    assert sensor4.state == "NotAFloat"

def test_sonnen_virtual_load_sensor():
    main_coordinator = MagicMock(api_key="123")
    sonnen_coord = MagicMock(data={"Consumption_W": "2000", "Production_W": "500"})

    sensor = SonnenVirtualLoadSensor(main_coordinator, sonnen_coord)
    assert sensor.state == 1500.0
    assert sensor.device_info["identifiers"] == {(DOMAIN, "123")}

    sonnen_coord.data = {}
    assert sensor.state is None

    sonnen_coord.data = {"Consumption_W": "Bad", "Production_W": "Data"}
    assert sensor.state is None

def test_battery_light_virtual_load_sensor_extra():
    coordinator = MagicMock(api_key="123")
    delattr(coordinator, "peak_guard")
    sensor = BatteryLightVirtualLoadSensor(coordinator)

    assert sensor.device_info["identifiers"] == {(DOMAIN, "123")}
    assert sensor.state is None

    coordinator.peak_guard = MagicMock(config={"virtual_load_sensor": "sensor.custom_load"})
    state_obj = MagicMock(state="1234")
    coordinator.hass.states.get.return_value = state_obj

    assert sensor.state == 1234.0

    state_obj.state = "bad_val"
    assert sensor.state is None

    coordinator.peak_guard.config = {
        "virtual_load_sensor": None,
        "grid_sensor": "sensor.grid",
        "battery_power_sensor": "sensor.bat",
        "grid_sensor_invert": False
    }
    coordinator.hass.states.get.return_value = MagicMock(state="bad_val")
    assert sensor.state == 0.0

    coordinator.hass.states.get.return_value = None
    assert sensor.state == 0.0

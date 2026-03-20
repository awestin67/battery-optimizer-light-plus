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
from custom_components.battery_optimizer_light_plus.binary_sensor import (
    async_setup_entry, HuaweiConnectionSensor, SonnenConnectionSensor
)
from custom_components.battery_optimizer_light_plus.const import (
    DOMAIN, CONF_BATTERY_TYPE, BATTERY_TYPE_HUAWEI, BATTERY_TYPE_SONNEN
)

@pytest.mark.asyncio
async def test_binary_sensor_setup_entry_sonnen():
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN}
    coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert isinstance(entities[0], SonnenConnectionSensor)

@pytest.mark.asyncio
async def test_binary_sensor_setup_entry_huawei():
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI}
    coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: coordinator}}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    entities = async_add_entities.call_args[0][0]
    assert isinstance(entities[0], HuaweiConnectionSensor)

@pytest.mark.asyncio
async def test_huawei_connection_sensor():
    coordinator = MagicMock()
    coordinator.config = {"soc_sensor": "sensor.soc"}
    coordinator.hass.states.get.return_value = MagicMock(state="50")

    sensor = HuaweiConnectionSensor(coordinator)
    assert sensor.is_on is True

    coordinator.hass.states.get.return_value = MagicMock(state="unavailable")
    assert sensor.is_on is False

    patch_target = "custom_components.battery_optimizer_light_plus.binary_sensor.async_track_state_change_event"
    with patch(patch_target) as mock_track:
        await sensor.async_added_to_hass()
        mock_track.assert_called_once()

@pytest.mark.asyncio
async def test_huawei_connection_sensor_no_soc_entity():
    coordinator = MagicMock()
    coordinator.config = {"soc_sensor": None}

    sensor = HuaweiConnectionSensor(coordinator)
    assert sensor.is_on is False

    await sensor.async_added_to_hass() # Ska köras utan fel, men inte binda någon lyssnare

def test_huawei_connection_sensor_device_info():
    coordinator = MagicMock()
    coordinator.api_key = "12345"
    sensor = HuaweiConnectionSensor(coordinator)

    assert sensor.device_info["identifiers"] == {(DOMAIN, "12345")}
    assert sensor.device_info["name"] == "Battery Optimizer Light Plus"

def test_huawei_connection_sensor_update_state():
    coordinator = MagicMock()
    sensor = HuaweiConnectionSensor(coordinator)
    sensor.async_write_ha_state = MagicMock()

    sensor._update_state(None)
    sensor.async_write_ha_state.assert_called_once()

def test_sonnen_connection_sensor():
    main_coordinator = MagicMock()
    main_coordinator.api_key = "12345"
    sonnen_coord = MagicMock()

    sensor = SonnenConnectionSensor(main_coordinator, sonnen_coord)

    sonnen_coord.last_update_success = True
    assert sensor.is_on is True

    sonnen_coord.last_update_success = False
    assert sensor.is_on is False

def test_sonnen_connection_sensor_device_info():
    main_coordinator = MagicMock()
    main_coordinator.api_key = "12345"
    sonnen_coord = MagicMock()
    sensor = SonnenConnectionSensor(main_coordinator, sonnen_coord)

    assert sensor.device_info["identifiers"] == {(DOMAIN, "12345")}
    assert sensor.device_info["name"] == "Battery Optimizer Light Plus"

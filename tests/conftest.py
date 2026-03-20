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

import sys
import os
from unittest.mock import MagicMock, AsyncMock
import datetime

# --- MOCK HOME ASSISTANT ---
mock_hass = MagicMock()
mock_hass.callback = lambda func: func
sys.modules["homeassistant"] = mock_hass
sys.modules["homeassistant.core"] = mock_hass
sys.modules["homeassistant.helpers"] = mock_hass
sys.modules["homeassistant.helpers.event"] = mock_hass
sys.modules["homeassistant.helpers.aiohttp_client"] = mock_hass
sys.modules["homeassistant.helpers.entity"] = mock_hass
mock_hass.DeviceInfo = dict
sys.modules["homeassistant.helpers.selector"] = mock_hass
sys.modules["homeassistant.exceptions"] = mock_hass
sys.modules["homeassistant.components"] = mock_hass
sys.modules["homeassistant.loader"] = mock_hass

mock_config_entries = MagicMock()
class MockFlow:
    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_menu(self, **kwargs): return {"type": "menu", **kwargs}
    def async_show_form(self, **kwargs): return {"type": "form", **kwargs}
    def async_create_entry(self, **kwargs): return {"type": "create_entry", **kwargs}
class MockConfigFlow(MockFlow):
    pass
class MockOptionsFlow(MockFlow):
    pass
mock_config_entries.ConfigFlow = MockConfigFlow
mock_config_entries.OptionsFlow = MockOptionsFlow
sys.modules["homeassistant.config_entries"] = mock_config_entries
mock_hass.config_entries = mock_config_entries

mock_util = MagicMock()
mock_util.utcnow.side_effect = lambda: datetime.datetime.now(datetime.timezone.utc)
sys.modules["homeassistant.util"] = mock_util
sys.modules["homeassistant.util.dt"] = mock_util
mock_hass.util.dt = mock_util

mock_const = MagicMock()
mock_const.STATE_UNAVAILABLE = "unavailable"
mock_const.STATE_UNKNOWN = "unknown"
mock_const.EntityCategory = MagicMock()
mock_const.PERCENTAGE = "%"
sys.modules["homeassistant.const"] = mock_const

mock_uc = MagicMock()
class UpdateFailed(Exception):
    pass
mock_uc.UpdateFailed = UpdateFailed

class MockDataUpdateCoordinator:
    def __init__(self, hass, *args, **kwargs):
        self.hass = hass
        self.data = None
        self.async_config_entry_first_refresh = AsyncMock()

mock_uc.DataUpdateCoordinator = MockDataUpdateCoordinator

class MockEntity:
    def async_on_remove(self, func): pass
    def async_write_ha_state(self): pass
    async def async_added_to_hass(self): pass

class MockCoordinatorEntity(MockEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
mock_uc.CoordinatorEntity = MockCoordinatorEntity
sys.modules["homeassistant.helpers.update_coordinator"] = mock_uc

mock_sensor = MagicMock()
class MockSensorEntity(MockEntity):
    pass
mock_sensor.SensorEntity = MockSensorEntity
mock_sensor.SensorDeviceClass = MagicMock()
mock_sensor.SensorStateClass = MagicMock()
sys.modules["homeassistant.components.sensor"] = mock_sensor

mock_binary_sensor = MagicMock()
class MockBinarySensorEntity(MockEntity):
    pass
mock_binary_sensor.BinarySensorEntity = MockBinarySensorEntity
mock_binary_sensor.BinarySensorDeviceClass = MagicMock()
sys.modules["homeassistant.components.binary_sensor"] = mock_binary_sensor

mock_switch = MagicMock()
class MockSwitchEntity(MockEntity):
    pass
mock_switch.SwitchEntity = MockSwitchEntity
sys.modules["homeassistant.components.switch"] = mock_switch

# Lägg till rotmappen i sökvägen så vi kan importera komponenten i alla tester
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

from homeassistant.components.switch import SwitchEntity # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from .const import DOMAIN, CONF_BATTERY_TYPE, BATTERY_TYPE_SONNEN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_SONNEN:
        sonnen_coord = coordinator.battery_api.coordinator
        async_add_entities([SonnenManualModeSwitch(coordinator, sonnen_coord)])

class SonnenManualModeSwitch(CoordinatorEntity, SwitchEntity):
    """Strömbrytare för att växla Sonnen mellan Auto och Manuell."""
    def __init__(self, main_coordinator, sonnen_coord):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self._attr_name = "Sonnen Manuellt Läge"
        self._attr_unique_id = f"{main_coordinator.api_key}_sonnen_manual_mode"
        self._attr_icon = "mdi:toggle-switch"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.main_coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    @property
    def is_on(self):
        if self.coordinator.data and "OperatingMode" in self.coordinator.data:
            return str(self.coordinator.data["OperatingMode"]) == "1"
        return False

    async def async_turn_on(self, **kwargs):
        await self.main_coordinator.battery_api._api.async_set_operating_mode(1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.main_coordinator.battery_api._api.async_set_operating_mode(2)
        await self.coordinator.async_request_refresh()

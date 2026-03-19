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

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.event import async_track_state_change_event # type: ignore
from homeassistant.core import callback # type: ignore
from .const import DOMAIN, CONF_BATTERY_TYPE, BATTERY_TYPE_HUAWEI

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_HUAWEI:
        async_add_entities([HuaweiConnectionSensor(coordinator)])

class HuaweiConnectionSensor(BinarySensorEntity):
    """Visar om integrationen har kontakt med Huawei-utrustningen."""
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Huawei Solar Connection"
        self._attr_unique_id = f"{coordinator.api_key}_huawei_connection"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._soc_entity = coordinator.config.get("soc_sensor")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    @property
    def is_on(self):
        if self._soc_entity:
            state = self.coordinator.hass.states.get(self._soc_entity)
            if state and state.state not in ("unknown", "unavailable"):
                return True
        return False

    async def async_added_to_hass(self):
        if self._soc_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.coordinator.hass, [self._soc_entity], self._update_state
                )
            )

    @callback
    def _update_state(self, event):
        self.async_write_ha_state()

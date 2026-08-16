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
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore
from homeassistant.helpers.event import async_track_state_change_event # type: ignore
from homeassistant.core import callback # type: ignore
from homeassistant.const import EntityCategory # type: ignore
from .const import DOMAIN, CONF_BATTERY_TYPE, BATTERY_TYPE_HUAWEI, BATTERY_TYPE_SONNEN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BatteryOptimizerWaterHeaterBoostBinarySensor(coordinator, entry),
    ]

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_HUAWEI:
        entities.append(HuaweiConnectionSensor(coordinator))

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_SONNEN:
        sonnen_coord = coordinator.battery_api.coordinator
        entities.append(SonnenConnectionSensor(coordinator, sonnen_coord))

    async_add_entities(entities)

class BatteryOptimizerWaterHeaterBoostBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Indikerar om Varmvattenberedare / Plusvärme ska vara aktiv."""
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, entry=None):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = "Optimizer Light VVB Boost"
        api_key = getattr(coordinator, "api_key", "light_plus")
        self._attr_unique_id = f"{api_key}_water_heater_boost"
        self.entity_id = "binary_sensor.optimizer_light_vvb_boost"

    @property
    def device_info(self) -> DeviceInfo:
        api_key = getattr(self.coordinator, "api_key", "light_plus")
        return DeviceInfo(
            identifiers={(DOMAIN, api_key)},
            name="Battery Optimizer Light Plus",
            manufacturer="Awestin Consulting",
            model="Cloud Optimizer",
            configuration_url="https://battery-prod.awestinconsulting.se",
        )

    @property
    def is_on(self) -> bool:
        """Returnerar True om optimeraren beordrar VVB Boost."""
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("water_heater_boost", False))

    @property
    def extra_state_attributes(self):
        """Skickar med förklarande orsak som attribut."""
        if not self.coordinator.data:
            return {"reason": "Väntar på data"}
        return {
            "reason": self.coordinator.data.get("water_heater_reason", "Väntar på data"),
        }

class HuaweiConnectionSensor(BinarySensorEntity):
    """Visar om integrationen har kontakt med Huawei-utrustningen."""
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Huawei Solar Connection"
        self._attr_unique_id = f"{coordinator.api_key}_huawei_connection"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
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

class SonnenConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Visar om integrationen har kontakt med det lokala Sonnen API:et."""
    def __init__(self, main_coordinator, sonnen_coord):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self._attr_name = "Sonnen API Anslutning"
        self._attr_unique_id = f"{main_coordinator.api_key}_sonnen_connection"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.main_coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    @property
    def is_on(self):
        return self.coordinator.last_update_success

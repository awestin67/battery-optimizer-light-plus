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

"""Sonnen-specifika sensorer (registreras via SonnenBattery.get_extra_entities)."""
from homeassistant.components.sensor import (  # type: ignore
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfPower  # type: ignore

from ...const import DOMAIN


def build_sensor_entities(main_coordinator, sonnen_coord) -> list:
    """Skapar alla Sonnen-sensorer. unique_id/entity_id är oförändrade sedan tidigare versioner."""
    return [
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "USOC", "Sonnen Batterinivå",
            PERCENTAGE, SensorDeviceClass.BATTERY
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "Pac_total_W", "Sonnen Battery In/Out",
            UnitOfPower.WATT, SensorDeviceClass.POWER
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "Consumption_W", "Sonnen Husförbrukning",
            UnitOfPower.WATT, SensorDeviceClass.POWER
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "Production_W", "Sonnen Solproduktion",
            UnitOfPower.WATT, SensorDeviceClass.POWER
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "GridFeedIn_W", "Sonnen Grid In/Out",
            UnitOfPower.WATT, SensorDeviceClass.POWER, invert=True
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "SystemStatus", "Sonnen System Status",
            None, None, EntityCategory.DIAGNOSTIC
        ),
        SonnenInternalSensor(
            main_coordinator, sonnen_coord, "EM_USOC", "Sonnen Backup Reserv",
            PERCENTAGE, SensorDeviceClass.BATTERY, EntityCategory.DIAGNOSTIC
        ),
        SonnenVirtualLoadSensor(main_coordinator, sonnen_coord),
        SonnenControlModeSensor(main_coordinator, sonnen_coord),
    ]


class SonnenInternalSensor(CoordinatorEntity, SensorEntity):
    """Sensor som läser direkt från Sonnen-batteriets lokala API-polling."""
    def __init__(
        self,
        main_coordinator,
        sonnen_coord,
        key,
        name,
        unit,
        device_class,
        entity_category=None,
        invert=False,
    ):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self._key = key
        self._attr_name = name
        self._invert = invert
        self._attr_unique_id = f"{main_coordinator.api_key}_sonnen_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if device_class:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if entity_category:
            self._attr_entity_category = entity_category

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.main_coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    @property
    def state(self):
        if self.coordinator.data and self._key in self.coordinator.data:
            val = self.coordinator.data[self._key]
            try:
                # Försök konvertera till siffror om det är mätvärden
                parsed_val = float(val) if '.' in str(val) or self._attr_device_class else val
                if isinstance(parsed_val, float):
                    parsed_val = round(parsed_val, 1)
                if self._invert and isinstance(parsed_val, (int, float)):
                    return -parsed_val
                return parsed_val
            except ValueError:
                return val
        return None

class SonnenVirtualLoadSensor(CoordinatorEntity, SensorEntity):
    """Beräknad virtuell last baserad på sol och husförbrukning från Sonnen."""
    def __init__(self, main_coordinator, sonnen_coord):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self._attr_name = "Sonnen Virtual Load"
        self._attr_unique_id = f"{main_coordinator.api_key}_sonnen_virtual_load_internal"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.main_coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    @property
    def state(self):
        data = self.coordinator.data
        if data and "Consumption_W" in data and "Production_W" in data:
            try:
                return round(float(data["Consumption_W"]) - float(data["Production_W"]), 1)
            except ValueError:
                pass
        return None

class SonnenControlModeSensor(CoordinatorEntity, SensorEntity):
    """Diagnostiksensor för Sonnens styrläge (EMS Site Limits vs Legacy)."""

    def __init__(self, main_coordinator, sonnen_coord):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self.entity_id = "sensor.battery_optimizer_sonnen_control_mode"
        self._attr_name = "Sonnen Control Mode"
        self._attr_unique_id = f"{main_coordinator.api_key}_sonnen_control_mode"
        self._attr_icon = "mdi:tune-vertical"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.main_coordinator.api_key)},
            name="Battery Optimizer Light Plus",
        )

    def _is_passive(self) -> bool:
        """True om integrationen körs i passivt läge (extern styrenhet, t.ex. Homey)."""
        data = getattr(self.main_coordinator, "data", None)
        return isinstance(data, dict) and data.get("client_mode") == "PASSIVE"

    @property
    def state(self):
        battery_api = getattr(self.main_coordinator, "battery_api", None)
        # Fail-closed (ADR-043): Site Limits visas bara när en PUT-probe faktiskt lyckats.
        if getattr(battery_api, "supports_bess_export_limit", False) is True:
            return "Site Power Limits (EMS v1.35+)"
        # I passivt läge skickar HA aldrig någon PUT-probe, så verifiering sker aldrig här.
        # Den externa styrenheten (Homey) gör egen probe; utan verifiering visas Legacy.
        if not self._is_passive() and getattr(battery_api, "is_modern_ems", False) is True:
            return "Legacy (Site Limits ej verifierad)"
        return "Legacy (Manual Mode)"

    @property
    def extra_state_attributes(self):
        battery_api = getattr(self.main_coordinator, "battery_api", None)
        attrs = {
            "software_version": getattr(battery_api, "software_version", None),
            "client_mode": "PASSIVE" if self._is_passive() else "ACTIVE",
            "firmware_supports_site_limits": getattr(battery_api, "is_modern_ems", False) is True,
            "site_limits_verified": getattr(battery_api, "supports_bess_export_limit", False) is True,
            "active_gcp_import_limit": None,
            "active_gcp_export_limit": None,
            "active_bess_export_limit": None,
        }
        site_limits = None
        if self.coordinator.data and isinstance(self.coordinator.data, dict):
            site_limits = self.coordinator.data.get("site_limits")

        if isinstance(site_limits, dict):
            attrs["active_gcp_import_limit"] = site_limits.get("p_gcp_max_import_limit")
            attrs["active_gcp_export_limit"] = site_limits.get("p_gcp_max_export_limit")
            attrs["active_bess_export_limit"] = site_limits.get("p_bess_inv_max_export_limit")
            if "p_bess_inv_max_import_limit" in site_limits:
                attrs["active_bess_import_limit"] = site_limits.get("p_bess_inv_max_import_limit")

        return attrs

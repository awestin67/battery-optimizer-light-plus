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

from homeassistant.components.sensor import ( # type: ignore
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore
from homeassistant.const import ( # type: ignore
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
    EntityCategory,
    PERCENTAGE,
    UnitOfPower
)
from homeassistant.helpers.event import async_track_state_change_event # type: ignore
from homeassistant.core import callback # type: ignore
from .const import (
    DOMAIN,
    CONF_GRID_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_VIRTUAL_LOAD_SENSOR,
    CONF_GRID_SENSOR_INVERT,
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_SONNEN,
)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BatteryLightActionSensor(coordinator),
        BatteryLightPowerSensor(coordinator),
        BatteryLightReasonSensor(coordinator),
        BatteryLightBufferSensor(coordinator),
        BatteryLightPeakSensor(coordinator),
        BatteryLightStatusSensor(coordinator),
        BatteryLightChargeTargetSensor(coordinator),
        BatteryLightDischargeTargetSensor(coordinator),
    ]

    if entry.data.get(CONF_BATTERY_TYPE) != BATTERY_TYPE_SONNEN:
        entities.append(BatteryLightVirtualLoadSensor(coordinator))

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_HUAWEI:
        working_mode_ent = coordinator.config.get("working_mode_entity")
        if working_mode_ent:
            entities.append(
                HuaweiWrapperSensor(
                    coordinator, working_mode_ent, "Huawei Working Mode", "huawei_working_mode", "mdi:cog-sync"
                )
            )

        status_ent = coordinator.config.get("device_status_entity")
        if status_ent:
            entities.append(
                HuaweiWrapperSensor(
                    coordinator, status_ent, "Huawei Device Status", "huawei_device_status", "mdi:information-outline"
                )
            )

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_SONNEN:
        sonnen_coord = coordinator.battery_api.coordinator
        entities.extend([
            SonnenInternalSensor(
                coordinator, sonnen_coord, "USOC", "Sonnen Batterinivå",
                PERCENTAGE, SensorDeviceClass.BATTERY
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "Pac_total_W", "Sonnen Battery In/Out",
                UnitOfPower.WATT, SensorDeviceClass.POWER
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "Consumption_W", "Sonnen Husförbrukning",
                UnitOfPower.WATT, SensorDeviceClass.POWER
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "Production_W", "Sonnen Solproduktion",
                UnitOfPower.WATT, SensorDeviceClass.POWER
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "GridFeedIn_W", "Sonnen Nätutbyte",
                UnitOfPower.WATT, SensorDeviceClass.POWER
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "SystemStatus", "Sonnen System Status",
                None, None, EntityCategory.DIAGNOSTIC
            ),
            SonnenVirtualLoadSensor(coordinator, sonnen_coord),
        ])

    async_add_entities(entities)

class BatteryOptimizerSensorBase(CoordinatorEntity, SensorEntity):
    """Gemensam basklass för att gruppera sensorer under en Device."""
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.api_key)},
            name="Battery Optimizer Light Plus",
            manufacturer="Awestin Consulting",
            model="Cloud Optimizer",
            configuration_url="https://battery-prod.awestinconsulting.se",
        )

class BatteryLightActionSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Action"
        self._attr_unique_id = f"{coordinator.api_key}_light_action"
        self._attr_icon = "mdi:lightning-bolt-circle"

    @property
    def state(self):
        raw_action = (self.coordinator.data or {}).get("action", "UNKNOWN")

        # Om PeakGuard har aktiverat Solar Override, visa IDLE (Auto) istället för HOLD
        if hasattr(self.coordinator, "peak_guard") and self.coordinator.peak_guard.is_solar_override:
            if raw_action == "HOLD":
                return "IDLE"
        return raw_action

class BatteryLightPowerSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Power"
        self._attr_unique_id = f"{coordinator.api_key}_light_power"
        self._attr_unit_of_measurement = "kW"
        self._attr_icon = "mdi:flash"

        # Talar om för HA att det är effekt -> Ger rätt grafer och färger
        self._attr_device_class = SensorDeviceClass.POWER
        # Talar om att det är ett mätvärde -> Sparar statistik för långtidshistorik
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        return (self.coordinator.data or {}).get("target_power_kw", 0.0)

class BatteryLightReasonSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Reason"
        self._attr_unique_id = f"{coordinator.api_key}_light_reason"
        self._attr_icon = "mdi:text-box-outline"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        # 1. Kolla först om den lokala effektvakten jobbar
        # (Detta skriver över molnets status, vilket är korrekt eftersom lokalt skydd har prio)
        if hasattr(self.coordinator, "peak_guard"):
            pg = self.coordinator.peak_guard
            if pg.is_active:
                return "Local Peak Guard Triggered"
            if pg.is_solar_override:
                return "Solar Override (Local)"

        # 2. Annars visa vad molnet säger (t.ex. "Charging due to cheap price")
        return (self.coordinator.data or {}).get("reason", "Unknown")

class BatteryLightBufferSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Buffer Target"
        self._attr_unique_id = f"{coordinator.api_key}_light_buffer"
        self._attr_unit_of_measurement = "%"
        self._attr_icon = "mdi:shield-check"

        # Visar batteri-procent snyggt i HA
        self._attr_device_class = SensorDeviceClass.BATTERY

    @property
    def state(self):
        # Hämtar 'min_soc_buffer' från backend JSON. Default 0.0 om det saknas.
        return (self.coordinator.data or {}).get("min_soc_buffer", 0.0)

class BatteryLightPeakSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Peak Limit"
        self._attr_unique_id = f"{coordinator.api_key}_light_peak_limit"
        self._attr_unit_of_measurement = "kW"
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_device_class = SensorDeviceClass.POWER

    @property
    def state(self):
        # Hämta värdet från backend. Default 12.0 (högt) om det saknas för att inte trigga i onödan.
        return (self.coordinator.data or {}).get("peak_power_kw", 12.0)

class BatteryLightStatusSensor(BatteryOptimizerSensorBase):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light PeakGuard Status"
        self._attr_unique_id = f"{coordinator.api_key}_peakguard_status"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        # Hämtar data från coordinator och lokal peak_guard instans. Först säkerställ att data finns.
        data = self.coordinator.data or {}
        is_active = data.get("is_peak_shaving_active", True)
        pg_status = data.get("peakguard_status")

        is_triggered = False
        in_maintenance = False
        maintenance_reason = None
        is_solar_override = False

        if hasattr(self.coordinator, "peak_guard"):
            pg = self.coordinator.peak_guard
            is_triggered = pg.is_active
            in_maintenance = pg.in_maintenance
            maintenance_reason = pg.maintenance_reason
            is_solar_override = pg.is_solar_override

        if in_maintenance:
            return f"Maintenance mode detected ({maintenance_reason}). Pausing control."

        if is_solar_override:
            return "Solar Override Active"

        if is_triggered:
            return "Triggered"

        if pg_status:
            if pg_status == "Active":
                return "Monitoring"
            return pg_status

        return "Monitoring" if is_active else "Disabled"

    @property
    def icon(self):
        """Returnerar en dynamisk ikon baserat på status."""
        status = self.state
        if status == "Disabled" or status == "Off":
            return "mdi:shield-off"
        if "Paused" in status:
            return "mdi:pause-circle-outline"
        if status == "Triggered":
            return "mdi:shield-alert"
        if "Maintenance" in status:
            return "mdi:tools"
        if "Solar Override" in status:
            return "mdi:solar-panel"
        return "mdi:shield-search"

class BatteryLightVirtualLoadSensor(SensorEntity):
    """Sensor som visar den beräknade virtuella lasten (för verifiering)."""
    def __init__(self, coordinator):
        # Vi ärver inte från CoordinatorEntity eftersom vi vill polla oftare (default 30s)
        # eller bara visa beräknat värde, oberoende av moln-uppdateringar.
        self.coordinator = coordinator
        self._attr_name = "Optimizer Light Virtual Load"
        self._attr_unique_id = f"{coordinator.api_key}_virtual_load"
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:home-lightning-bolt-outline"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.api_key)},
            name="Battery Optimizer Light Plus",
            manufacturer="Awestin Consulting",
            model="Cloud Optimizer",
            configuration_url="https://battery-prod.awestinconsulting.se",
        )

    @property
    def state(self):
        if not hasattr(self.coordinator, "peak_guard"):
            return None

        config = self.coordinator.peak_guard.config
        hass = self.coordinator.hass

        # 1. Om en specifik sensor är vald, visa dess värde
        virtual_load_id = config.get(CONF_VIRTUAL_LOAD_SENSOR)
        if virtual_load_id:
            state = hass.states.get(virtual_load_id)
            if state and state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                try:
                    return float(state.state)
                except ValueError:
                    pass
            return None

        # 2. Annars beräkna: Grid + Batteri
        grid_id = config.get(CONF_GRID_SENSOR)
        bat_id = config.get(CONF_BATTERY_POWER_SENSOR)
        invert_grid = config.get(CONF_GRID_SENSOR_INVERT, False)

        grid_val = 0.0
        bat_val = 0.0

        if grid_id:
            state = hass.states.get(grid_id)
            if state and state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                try:
                    grid_val = float(state.state)
                except ValueError:
                    pass

        if bat_id:
            state = hass.states.get(bat_id)
            if state and state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                try:
                    bat_val = float(state.state)
                except ValueError:
                    pass

        if invert_grid:
            grid_val = -grid_val

        return float(grid_val + bat_val)

class BatteryLightChargeTargetSensor(BatteryOptimizerSensorBase):
    """Sensor som visar önskad laddningseffekt i Watt (för styrning)."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Charge Target"
        self._attr_unique_id = f"{coordinator.api_key}_light_charge_target"
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-arrow-up"

    @property
    def state(self):
        data = self.coordinator.data or {}
        action = data.get("action", "IDLE")
        if action == "CHARGE":
            kw = data.get("target_power_kw", 0.0)
            return int(kw * 1000)
        return 0

class HuaweiWrapperSensor(BatteryOptimizerSensorBase):
    """Wrapper för att visa Huawei-specifika entiteter snyggt integrerat."""
    def __init__(self, coordinator, entity_id, name, id_suffix, icon):
        super().__init__(coordinator)
        self._source_entity = entity_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.api_key}_{id_suffix}"
        self._attr_icon = icon

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._source_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.coordinator.hass, [self._source_entity], self._update_state
                )
            )

    @callback
    def _update_state(self, event):
        self.async_write_ha_state()

    @property
    def state(self):
        if self._source_entity:
            state_obj = self.coordinator.hass.states.get(self._source_entity)
            if state_obj and state_obj.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return state_obj.state
        return None

class SonnenInternalSensor(CoordinatorEntity, SensorEntity):
    """Sensor som läser direkt från Sonnen-batteriets lokala API-polling."""
    def __init__(self, main_coordinator, sonnen_coord, key, name, unit, device_class, entity_category=None):
        super().__init__(sonnen_coord)
        self.main_coordinator = main_coordinator
        self._key = key
        self._attr_name = name
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
                return float(val) if '.' in str(val) or self._attr_device_class else val
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
                return float(data["Consumption_W"]) - float(data["Production_W"])
            except ValueError:
                pass
        return None

class BatteryLightDischargeTargetSensor(BatteryOptimizerSensorBase):
    """Sensor som visar önskad urladdningseffekt i Watt (för styrning)."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Discharge Target"
        self._attr_unique_id = f"{coordinator.api_key}_light_discharge_target"
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-arrow-down"

    @property
    def state(self):
        data = self.coordinator.data or {}
        action = data.get("action", "IDLE")
        if action == "DISCHARGE":
            kw = data.get("target_power_kw", 0.0)
            return int(kw * 1000)
        return 0

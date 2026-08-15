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
import homeassistant.util.dt as dt_util
from .const import (
    DOMAIN,
    CONF_SOC_SENSOR,
    CONF_GRID_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_VIRTUAL_LOAD_SENSOR,
    CONF_GRID_SENSOR_INVERT,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_SONNEN,
)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BatteryLightActionSensor(coordinator),
        BatteryLightReasonSensor(coordinator),
        BatteryLightBufferSensor(coordinator),
        BatteryLightPeakSensor(coordinator),
        BatteryLightStatusSensor(coordinator),
        BatteryLightChargeTargetSensor(coordinator),
        BatteryLightDischargeTargetSensor(coordinator),
        BatteryLightHouseConsumptionSensor(coordinator),
        BatteryLightGraphDataSensor(coordinator),
        BatteryLightDailySavingsSensor(coordinator),
        BatteryLightAISummarySensor(coordinator),
        BatteryLightNextActionSensor(coordinator),
        BatteryLightNextActionTimeSensor(coordinator),
        BatteryLightDynamicExportLimitSensor(coordinator),
        BatteryLightEVScheduleSensor(coordinator),
        BatteryOptimizerWaterHeaterReasonSensor(coordinator, entry),
    ]

    if entry.data.get(CONF_BATTERY_TYPE) != BATTERY_TYPE_SONNEN:
        entities.append(BatteryLightVirtualLoadSensor(coordinator))

    if entry.data.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_HUAWEI:
        status_ent = coordinator.config.get("device_status_entity")
        if status_ent:
            entities.append(
                HuaweiWrapperSensor(
                    coordinator, status_ent, "Huawei Device Status", "huawei_device_status", "mdi:information-outline",
                    entity_category=EntityCategory.DIAGNOSTIC
                )
            )

        bat_ent = coordinator.config.get(CONF_BATTERY_POWER_SENSOR)
        if bat_ent:
            entities.append(
                HuaweiWrapperSensor(
                    coordinator, bat_ent, "Huawei Solar Battery In/Out",
                    "huawei_battery_in_out", "mdi:battery-sync",
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT, unit=UnitOfPower.WATT
                )
            )

        soc_ent = coordinator.config.get(CONF_SOC_SENSOR)
        if soc_ent:
            entities.append(
                HuaweiWrapperSensor(
                    coordinator, soc_ent, "Huawei Solar SoC", "huawei_soc", "mdi:battery-50",
                    device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT, unit=PERCENTAGE
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
                coordinator, sonnen_coord, "GridFeedIn_W", "Sonnen Grid In/Out",
                UnitOfPower.WATT, SensorDeviceClass.POWER, invert=True
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "SystemStatus", "Sonnen System Status",
                None, None, EntityCategory.DIAGNOSTIC
            ),
            SonnenInternalSensor(
                coordinator, sonnen_coord, "EM_USOC", "Sonnen Backup Reserv",
                PERCENTAGE, SensorDeviceClass.BATTERY, EntityCategory.DIAGNOSTIC
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
        val = (self.coordinator.data or {}).get("min_soc_buffer", 0.0)
        try:
            return round(float(val), 1)
        except (ValueError, TypeError):
            return val

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
        val = (self.coordinator.data or {}).get("peak_power_kw", 12.0)
        try:
            return round(float(val), 1)
        except (ValueError, TypeError):
            return val

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

        client_mode = data.get("client_mode", "ACTIVE")
        if client_mode == "PASSIVE":
            return "Passive (Read-Only)"

        def _parse_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("false", "0", "no", "off", "inactive", ""):
                    return False
                if v in ("true", "1", "yes", "on", "active"):
                    return True
            return bool(val)

        global_active = _parse_bool(data.get("is_active"), True)
        is_active = _parse_bool(data.get("is_peak_shaving_active"), True)
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

        # Om hela optimeraren är avstängd globalt
        if not global_active:
            return "Disabled"

        # Om Peak Shaving är inaktivt (t.ex. global optimerare avstängd)
        # ska vi visa "Disabled" (eller t.ex. "Paused" om det skickas explicit).
        if not is_active:
            if pg_status and pg_status.strip().lower() not in ("active", "monitoring"):
                return pg_status
            return "Disabled"

        if pg_status:
            if pg_status == "Active":
                return "Monitoring"
            return pg_status

        return "Monitoring"

    @property
    def icon(self):
        """Returnerar en dynamisk ikon baserat på status."""
        status = self.state
        if status == "Passive (Read-Only)":
            return "mdi:eye-outline"
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

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "client_mode": data.get("client_mode", "ACTIVE"),
            "peakguard_status": data.get("peakguard_status"),
            "is_peak_shaving_active": data.get("is_peak_shaving_active"),
            "min_soc_buffer": data.get("min_soc_buffer"),
            "next_action": data.get("next_action"),
            "next_action_time": data.get("next_action_time"),
        }

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
                    return round(float(state.state), 1)
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
                    if config.get(CONF_BATTERY_SENSOR_INVERT, False):
                        bat_val = -bat_val
                except ValueError:
                    pass

        if invert_grid:
            grid_val = -grid_val

        return round(grid_val + bat_val, 1)

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
            return int(round(kw * 1000))
        return 0

class BatteryLightHouseConsumptionSensor(BatteryOptimizerSensorBase):
    """Sensor som visar den uträknade husförbrukningen (Watt) som skickas till molnet."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_house_consumption"
        self._attr_name = "Optimizer Light House Consumption"
        self._attr_unique_id = f"{coordinator.api_key}_light_house_consumption"
        self._attr_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:home-lightning-bolt"

    @property
    def state(self):
        val = getattr(self.coordinator, "current_load_w", None)
        if val is not None:
            return round(val, 1)
        return None

class HuaweiWrapperSensor(BatteryOptimizerSensorBase):
    """Wrapper för att visa Huawei-specifika entiteter snyggt integrerat."""
    def __init__(
        self, coordinator, entity_id, name, id_suffix, icon,
        entity_category=None, device_class=None, state_class=None, unit=None
    ):
        super().__init__(coordinator)
        self._source_entity = entity_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.api_key}_{id_suffix}"
        self._attr_icon = icon
        if entity_category:
            self._attr_entity_category = entity_category
        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class
        if unit:
            self._attr_native_unit_of_measurement = unit

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
                if getattr(self, "_attr_state_class", None) == SensorStateClass.MEASUREMENT:
                    try:
                        return round(float(state_obj.state), 1)
                    except ValueError:
                        pass
                return state_obj.state
        return None

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
            return int(round(kw * 1000))
        return 0

class BatteryLightGraphDataSensor(CoordinatorEntity, SensorEntity):
    """Sensor som håller grafdata (historik och prognos) från molnet för ApexCharts."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Battery Optimizer Graph Data"
        self._attr_unique_id = f"{coordinator.api_key}_graph_data"
        self._attr_icon = "mdi:chart-line"

    @property
    def state(self):
        """Returnerar OK om vi har fått data från servern, annars Waiting for data."""
        if self.coordinator.data and self.coordinator.data.get("graph_data"):
            return "OK"
        return "Waiting for data"

    @property
    def extra_state_attributes(self):
        """
        Tvingar fram ett state-change-event i Home Assistant genom att returnera
        en tidsstämpel som uppdateras vid varje lyckad hämtning. Detta triggar
        ApexCharts att faktiskt hämta den nya datan från vårt interna API.
        """
        if self.coordinator.data:
            return {
                "last_update_time": self.coordinator.data.get("last_update_time")
            }
        return {}

class BatteryLightDailySavingsSensor(BatteryOptimizerSensorBase):
    """Sensor som beräknar och visar dagens totala besparingar baserat på historikdatan."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Optimizer Light Daily Savings"
        self._attr_unique_id = f"{coordinator.api_key}_daily_savings"
        self._attr_native_unit_of_measurement = "SEK"
        self._attr_icon = "mdi:piggy-bank"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def state(self):
        graph_data = (self.coordinator.data or {}).get("graph_data", {})
        history = graph_data.get("history", [])

        if not history:
            return 0.0

        total_savings = 0.0
        today_date = dt_util.now().date()

        for entry in history:
            timestamp_str = entry.get("timestamp")
            if timestamp_str:
                dt_obj = dt_util.parse_datetime(timestamp_str)
                if dt_obj and dt_util.as_local(dt_obj).date() == today_date:
                    total_savings += float(entry.get("savings_sek", 0.0))

        return round(total_savings, 2)

class BatteryLightAISummarySensor(BatteryOptimizerSensorBase):
    """Sensor som visar den dagliga AI-sammanfattningen."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_ai_summary"
        self._attr_unique_id = f"{coordinator.api_key}_ai_summary"
        self._attr_name = "Optimizer Light AI Summary"
        self._attr_icon = "mdi:robot-outline"

    @property
    def state(self):
        """Returnerar en kort status pga 255-teckensgränsen i Home Assistant."""
        if self.coordinator.data and self.coordinator.data.get("ai_summary"):
            return "Tillgänglig"
        return "Väntar på data"

    @property
    def extra_state_attributes(self):
        """Själva sammanfattningen sparas som ett attribut så den inte klipps av."""
        if self.coordinator.data:
            return {
                "summary_text": self.coordinator.data.get("ai_summary", "Ingen AI-sammanfattning tillgänglig ännu.")
            }
        return {}

class BatteryLightNextActionSensor(BatteryOptimizerSensorBase):
    """Sensor som visar nästa kommande åtgärd från molnet."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_next_action"
        self._attr_name = "Optimizer Light Next Action"
        self._attr_unique_id = f"{coordinator.api_key}_light_next_action"
        self._attr_icon = "mdi:calendar-arrow-right"

    @property
    def state(self):
        return (self.coordinator.data or {}).get("next_action", "UNKNOWN")

class BatteryLightNextActionTimeSensor(BatteryOptimizerSensorBase):
    """Sensor som visar tiden för nästa kommande åtgärd från molnet."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_next_action_time"
        self._attr_name = "Optimizer Light Next Action Time"
        self._attr_unique_id = f"{coordinator.api_key}_light_next_action_time"
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def state(self):
        time_str = (self.coordinator.data or {}).get("next_action_time")
        if not time_str or time_str == "None":
            return None
        return dt_util.parse_datetime(time_str)

    @property
    def extra_state_attributes(self):
        return {
            "next_action": (self.coordinator.data or {}).get("next_action")
        }

class BatteryLightDynamicExportLimitSensor(BatteryOptimizerSensorBase):
    """Sensor som visar dynamisk exportgräns (Zero Export) i kW."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_dynamic_export_limit"
        self._attr_name = "Optimizer Light Dynamic Export Limit"
        self._attr_unique_id = f"{coordinator.api_key}_light_dynamic_export_limit"
        self._attr_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_icon = "mdi:transmission-tower-off"

    @property
    def state(self):
        val = (self.coordinator.data or {}).get("dynamic_export_limit_kw")
        if val is None:
            return None
        try:
            return round(float(val), 2)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self):
        val = (self.coordinator.data or {}).get("dynamic_export_limit_kw")
        return {
            "limit_active": val is not None,
            "status_text": "Unlimited" if val is None else f"{val} kW"
        }

class BatteryLightEVScheduleSensor(BatteryOptimizerSensorBase):
    """Sensor som exponerar molnets tidslinje för EV-laddning så användaren kan skapa automations."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.entity_id = "sensor.optimizer_light_ev_schedule"
        self._attr_name = "Optimizer Light EV Schedule"
        self._attr_unique_id = f"{coordinator.api_key}_ev_schedule"
        self._attr_icon = "mdi:ev-station"

    @property
    def state(self):
        schedules = getattr(self.coordinator, "ev_schedules", {})
        active_count = sum(1 for plan in schedules.values() if plan)
        if active_count == 0:
            return "Inga scheman"
        return f"{active_count} bilar planerade"

    @property
    def extra_state_attributes(self):
        schedules = getattr(self.coordinator, "ev_schedules", {})
        return {
            "schedules": schedules
        }

class BatteryOptimizerWaterHeaterReasonSensor(BatteryOptimizerSensorBase):
    """Visar varför VVB körs eller pausas."""
    _attr_has_entity_name = True
    _attr_translation_key = "water_heater_reason"
    _attr_icon = "mdi:water-boiler-alert"

    def __init__(self, coordinator, entry=None):
        super().__init__(coordinator)
        self.entry = entry
        entry_id = getattr(entry, "entry_id", None) if entry else None
        if entry_id:
            self._attr_unique_id = f"{entry_id}_water_heater_reason"
        else:
            api_key = getattr(coordinator, "api_key", "light_plus")
            self._attr_unique_id = f"{api_key}_water_heater_reason"

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "Okänd"
        return str(self.coordinator.data.get("water_heater_reason", "Normal"))

    @property
    def state(self) -> str:
        return self.native_value

BatteryLightWaterHeaterReasonSensor = BatteryOptimizerWaterHeaterReasonSensor


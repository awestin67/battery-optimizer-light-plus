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

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
)
from .const import (
    DOMAIN,
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_GENERIC,
    BATTERY_TYPE_HOMEVOLT,
    BATTERY_TYPE_SOLIS_MODBUS,
    BATTERY_TYPE_SIGENERGY,
    BATTERY_TYPE_SOLINTEG,
    CONF_API_URL,
    DEFAULT_API_URL,
    CONF_API_KEY,
    CONF_SOC_SENSOR,
    CONF_GRID_SENSOR,
    CONF_GRID_SENSOR_INVERT,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_BATTERY_STATUS_SENSOR,
    CONF_BATTERY_STATUS_KEYWORDS,
    CONF_VIRTUAL_LOAD_SENSOR,
    CONF_EV_CHARGING_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_EXTERNAL_CONTROL_SENSOR,
    CONF_WATER_HEATER_SWITCH,
    CONF_WATER_HEATER_TEMP_SENSOR,
    CONF_MIN_SOC,
    DEFAULT_BATTERY_STATUS_KEYWORDS,
    CONF_HOST,
    CONF_API_TOKEN,
    CONF_PORT,
    DEFAULT_PORT,
    CONF_BATTERY_DEVICE_ID,
    CONF_DEVICE_STATUS_ENTITY,
    CONF_MAX_DISCHARGE_ENTITY,
    CONF_GRAPH_HISTORY_HOURS,
    CONF_EV_C1_NAME,
    CONF_EV_C1_TARGET_KWH,
    CONF_EV_C1_DEPART_TIME,
    CONF_EV_C1_MAX_KW,
    CONF_EV_C1_CABLE_CONNECTED,
    CONF_EV_C1_IS_CHARGING,
    CONF_EV_C2_NAME,
    CONF_EV_C2_TARGET_KWH,
    CONF_EV_C2_DEPART_TIME,
    CONF_EV_C2_MAX_KW,
    CONF_EV_C2_CABLE_CONNECTED,
    CONF_EV_C2_IS_CHARGING,
)

_LOGGER = logging.getLogger(__name__)

def _strip_none_values(data: dict) -> None:
    """Ta bort alla nycklar med None eller tomma strängar från data för att undvika valideringsfel i HA."""
    keys_to_remove = [k for k, v in data.items() if v is None or v == ""]
    for k in keys_to_remove:
        del data[k]

def _opt(key, default_val=vol.UNDEFINED):
    """Skapar ett vol.Optional där default-värdet läggs som suggested_value.
    Detta förhindrar att voluptuous tvingar tillbaka raderade värden."""
    if default_val is not vol.UNDEFINED and default_val is not None and default_val != "":
        return vol.Optional(key, description={"suggested_value": default_val})
    return vol.Optional(key)

def async_auto_discover_huawei_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Huawei device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    discovery_map = {
        CONF_SOC_SENSOR: ("sensor", ("storage_state_of_capacity", "battery_state_of_capacity")),
        CONF_BATTERY_POWER_SENSOR: ("sensor", ("storage_charge_discharge_power", "battery_charge_discharge_power")),
        CONF_GRID_SENSOR: ("sensor", ("power_meter_active_power",)),
        CONF_DEVICE_STATUS_ENTITY: ("sensor", ("storage_running_status", "running_status", "device_status")),
        CONF_MAX_DISCHARGE_ENTITY: ("number", ("storage_maximum_discharge_power", "storage_maximum_discharging_power", "battery_maximum_discharge_power", "battery_maximum_discharging_power", "maximum_discharging_power")),
    }

    for conf_key, (domain, translation_keys) in discovery_map.items():
        for entry in entries:
            if entry.domain == domain and entry.translation_key in translation_keys:
                found_entities[conf_key] = entry.entity_id
                break

    return found_entities

def async_auto_discover_homevolt_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Homevolt device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    for entry in entries:
        uid = entry.unique_id

        if uid.startswith("homevolt_local_total_soc_"):
            found_entities[CONF_SOC_SENSOR] = entry.entity_id

        elif uid.startswith("homevolt_local_power_"):
            found_entities[CONF_BATTERY_POWER_SENSOR] = entry.entity_id

        elif uid.startswith("homevolt_local_grid_power_"):
            found_entities[CONF_GRID_SENSOR] = entry.entity_id

        elif uid.startswith("homevolt_local_load_power_"):
            found_entities[CONF_VIRTUAL_LOAD_SENSOR] = entry.entity_id

        elif uid.startswith("homevolt_local_ems_") and "status" not in uid and "error" not in uid and "temp" not in uid and "energy" not in uid:
            if CONF_DEVICE_STATUS_ENTITY not in found_entities:
                found_entities[CONF_DEVICE_STATUS_ENTITY] = entry.entity_id

    return found_entities

def async_auto_discover_solis_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Solis device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    # 1. Sök i första hand efter de exakta unika ID:n som används för Solis S6 Hybrid (hybrid_sensors.py)
    discovery_map = {
        CONF_SOC_SENSOR: ["solis_modbus_inverter_battery_soc"],
        CONF_GRID_SENSOR: ["solis_modbus_inverter_grid_power_net", "solis_modbus_inverter_ac_grid_port_power"],
        CONF_BATTERY_POWER_SENSOR: ["solis_modbus_inverter_battery_power_combined", "solis_modbus_inverter_battery_power"],
        CONF_DEVICE_STATUS_ENTITY: ["solis_modbus_inverter_current_status_string", "solis_modbus_inverter_current_status"],
    }

    for conf_key, unique_ids in discovery_map.items():
        for entry in entries:
            if any(uid in entry.unique_id for uid in unique_ids):
                found_entities[conf_key] = entry.entity_id
                break

    # 2. Fallback till mer generella sökord om vi saknar någon sensor
    for entry in entries:
        ent_id = entry.entity_id
        if CONF_SOC_SENSOR not in found_entities and "battery_soc" in ent_id:
            found_entities[CONF_SOC_SENSOR] = ent_id
        elif CONF_GRID_SENSOR not in found_entities and "grid" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_GRID_SENSOR] = ent_id
        elif CONF_BATTERY_POWER_SENSOR not in found_entities and "battery" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_BATTERY_POWER_SENSOR] = ent_id
        elif CONF_DEVICE_STATUS_ENTITY not in found_entities and "status" in ent_id and "sensor." in ent_id:
            found_entities[CONF_DEVICE_STATUS_ENTITY] = ent_id

    return found_entities

def async_auto_discover_sigenergy_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Sigenergy device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    for entry in entries:
        ent_id = entry.entity_id
        if CONF_SOC_SENSOR not in found_entities and "soc" in ent_id and "sensor." in ent_id:
            found_entities[CONF_SOC_SENSOR] = ent_id
        elif CONF_GRID_SENSOR not in found_entities and "grid" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_GRID_SENSOR] = ent_id
        elif CONF_BATTERY_POWER_SENSOR not in found_entities and "battery" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_BATTERY_POWER_SENSOR] = ent_id
        elif CONF_DEVICE_STATUS_ENTITY not in found_entities and "status" in ent_id and "sensor." in ent_id:
            found_entities[CONF_DEVICE_STATUS_ENTITY] = ent_id

    return found_entities

def async_auto_discover_solinteg_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Solinteg device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    # SolaX Modbus unika ID:n för bl.a. Solinteg
    discovery_map = {
        CONF_SOC_SENSOR: ["_battery_capacity", "_battery_soc"],
        CONF_GRID_SENSOR: ["_measured_power", "_grid_power_net", "_grid_power"],
        CONF_BATTERY_POWER_SENSOR: ["_battery_power_charge", "_battery_power", "_battery_power_combined"],
        CONF_DEVICE_STATUS_ENTITY: ["_inverter_status"],
    }

    for conf_key, unique_ids in discovery_map.items():
        for entry in entries:
            if any(uid in entry.unique_id for uid in unique_ids):
                found_entities[conf_key] = entry.entity_id
                break

    for entry in entries:
        ent_id = entry.entity_id
        if CONF_SOC_SENSOR not in found_entities and "soc" in ent_id and "sensor." in ent_id:
            found_entities[CONF_SOC_SENSOR] = ent_id
        elif CONF_GRID_SENSOR not in found_entities and "grid" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_GRID_SENSOR] = ent_id
        elif CONF_BATTERY_POWER_SENSOR not in found_entities and "battery" in ent_id and "power" in ent_id and "sensor." in ent_id:
            found_entities[CONF_BATTERY_POWER_SENSOR] = ent_id

    return found_entities

class BatteryOptimizerLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Optimizer Light."""
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user selects the battery type."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["sonnen", "huawei", "homevolt", "solis_modbus", "sigenergy", "solinteg", "generic"]
        )

    async def async_step_sonnen(self, user_input=None):
        """Handle the Sonnen battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_SONNEN
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="sonnen",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_API_TOKEN): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            })
        )

    async def async_step_huawei(self, user_input=None):
        """Handle the Huawei battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_HUAWEI
        self.data[CONF_BATTERY_SENSOR_INVERT] = True

        if user_input is not None:
            # Auto-discover entities from the selected device
            discovered_entities = async_auto_discover_huawei_entities(self.hass, user_input[CONF_BATTERY_DEVICE_ID])
            if discovered_entities:
                _LOGGER.info(f"Auto-discovered Huawei entities: {discovered_entities}")
                self.data.update(discovered_entities)

            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="huawei",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="huawei_solar")
                ),
            })
        )

    async def async_step_homevolt(self, user_input=None):
        """Handle the Homevolt battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_HOMEVOLT
        self.data[CONF_BATTERY_SENSOR_INVERT] = False
        self.data[CONF_GRID_SENSOR_INVERT] = False

        if user_input is not None:
            # Auto-discover entities from the selected device
            discovered_entities = async_auto_discover_homevolt_entities(self.hass, user_input[CONF_BATTERY_DEVICE_ID])
            if discovered_entities:
                _LOGGER.info(f"Auto-discovered Homevolt entities: {discovered_entities}")
                self.data.update(discovered_entities)

            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="homevolt",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="homevolt_local")
                ),
            })
        )

    async def async_step_solis_modbus(self, user_input=None):
        """Handle the Solis Modbus battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_SOLIS_MODBUS

        if user_input is not None:
            discovered_entities = async_auto_discover_solis_entities(self.hass, user_input[CONF_BATTERY_DEVICE_ID])
            if discovered_entities:
                _LOGGER.info(f"Auto-discovered Solis entities: {discovered_entities}")
                self.data.update(discovered_entities)

            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="solis_modbus",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="solis_modbus")
                ),
            })
        )

    async def async_step_sigenergy(self, user_input=None):
        """Handle the Sigenergy battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_SIGENERGY

        if user_input is not None:
            discovered_entities = async_auto_discover_sigenergy_entities(self.hass, user_input[CONF_BATTERY_DEVICE_ID])
            if discovered_entities:
                _LOGGER.info(f"Auto-discovered Sigenergy entities: {discovered_entities}")
                self.data.update(discovered_entities)

            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="sigenergy",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(selector.DeviceSelectorConfig()),
            })
        )

    async def async_step_solinteg(self, user_input=None):
        """Handle the Solinteg battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_SOLINTEG

        if user_input is not None:
            discovered_entities = async_auto_discover_solinteg_entities(self.hass, user_input[CONF_BATTERY_DEVICE_ID])
            if discovered_entities:
                _LOGGER.info(f"Auto-discovered Solinteg entities: {discovered_entities}")
                self.data.update(discovered_entities)

            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="solinteg",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(selector.DeviceSelectorConfig()),
            })
        )

    async def async_step_generic(self, user_input=None):
        """Handle the Generic battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_GENERIC
        return await self.async_step_common()

    async def async_step_common(self, user_input=None):
        """Handle the common configuration step for all battery types."""
        if user_input is not None:
            if CONF_API_URL in user_input and user_input[CONF_API_URL]:
                url = str(user_input[CONF_API_URL]).strip()
                if url and not (url.startswith("http://") or url.startswith("https://")):
                    url = f"https://{url}"
                user_input[CONF_API_URL] = url

            self.data.update(user_input)
            _strip_none_values(self.data)

            # Förhindra att användaren lägger till samma API-nyckel två gånger
            api_key = self.data.get(CONF_API_KEY)
            if api_key:
                await self.async_set_unique_id(api_key)
                self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Battery Optimizer Light", data=self.data)

        battery_type = self.data.get(CONF_BATTERY_TYPE)

        def get_val(key, default_fallback=vol.UNDEFINED):
            val = self.data.get(key)
            return val if val is not None else default_fallback

        schema_dict = {
            vol.Required(CONF_API_URL, default=DEFAULT_API_URL): TextSelector(TextSelectorConfig(type="url")),
            vol.Required(CONF_API_KEY): TextSelector(),
            _opt(
                CONF_EV_CHARGING_SENSOR, get_val(CONF_EV_CHARGING_SENSOR)
            ): EntitySelector(EntitySelectorConfig()),
            _opt(
                CONF_SOLAR_SENSOR, get_val(CONF_SOLAR_SENSOR)
            ): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            _opt(
                CONF_EXTERNAL_CONTROL_SENSOR, get_val(CONF_EXTERNAL_CONTROL_SENSOR)
            ): EntitySelector(EntitySelectorConfig()),
            _opt(
                CONF_WATER_HEATER_SWITCH, get_val(CONF_WATER_HEATER_SWITCH)
            ): EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"])),
            _opt(
                CONF_WATER_HEATER_TEMP_SENSOR, get_val(CONF_WATER_HEATER_TEMP_SENSOR)
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional("enable_solar_override", default=get_val("enable_solar_override", False)): bool,
            vol.Optional(CONF_GRAPH_HISTORY_HOURS, default=get_val(CONF_GRAPH_HISTORY_HOURS, "24")): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["12", "24", "48", "72", "168"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="graph_history_hours",
                )
            ),
        }

        # Göm de flesta manuella sensorerna om man använder Sonnen!
        if battery_type not in [BATTERY_TYPE_SONNEN]:
            schema_dict[vol.Required(
                CONF_SOC_SENSOR, default=get_val(CONF_SOC_SENSOR)
            )] = EntitySelector(EntitySelectorConfig(domain="sensor"))

            schema_dict[_opt(
                CONF_GRID_SENSOR, get_val(CONF_GRID_SENSOR)
            )] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power"))

            if battery_type != BATTERY_TYPE_HOMEVOLT:
                schema_dict[vol.Optional(CONF_GRID_SENSOR_INVERT, default=False)] = bool

            schema_dict[vol.Required(
                CONF_BATTERY_POWER_SENSOR, default=get_val(CONF_BATTERY_POWER_SENSOR)
            )] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power"))

            if battery_type not in [BATTERY_TYPE_HUAWEI, BATTERY_TYPE_HOMEVOLT]:
                schema_dict[vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=False)] = bool

            schema_dict[_opt(
                CONF_BATTERY_STATUS_SENSOR, get_val(CONF_BATTERY_STATUS_SENSOR)
            )] = EntitySelector(EntitySelectorConfig(domain="sensor"))

            schema_dict[_opt(
                CONF_BATTERY_STATUS_KEYWORDS, get_val(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)
            )] = TextSelector(TextSelectorConfig(multiline=True))

            schema_dict[_opt(
                CONF_VIRTUAL_LOAD_SENSOR, get_val(CONF_VIRTUAL_LOAD_SENSOR)
            )] = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power"))

            if battery_type == BATTERY_TYPE_GENERIC:
                schema_dict[vol.Optional(
                    CONF_MIN_SOC, default=get_val(CONF_MIN_SOC, 0.0)
                )] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="%"
                    )
                )

            if battery_type in [BATTERY_TYPE_HUAWEI, BATTERY_TYPE_SOLIS_MODBUS, BATTERY_TYPE_SIGENERGY, BATTERY_TYPE_SOLINTEG]:
                schema_dict.update({
                    _opt(
                        CONF_DEVICE_STATUS_ENTITY, get_val(CONF_DEVICE_STATUS_ENTITY)
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                })

            if battery_type == BATTERY_TYPE_HUAWEI:
                schema_dict.update({
                    _opt(
                        CONF_MAX_DISCHARGE_ENTITY, get_val(CONF_MAX_DISCHARGE_ENTITY)
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
                })

        return self.async_show_form(step_id="common", data_schema=vol.Schema(schema_dict))
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return BatteryOptimizerLightOptionsFlow(config_entry)

class BatteryOptimizerLightOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Battery Optimizer Light."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialize options flow."""
        if config_entry is not None:
            self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        if hasattr(self, "_config_entry"):
            return self._config_entry
        return super().config_entry

    @config_entry.setter
    def config_entry(self, entry: config_entries.ConfigEntry) -> None:
        """Set the config entry."""
        self._config_entry = entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            battery_type = self.config_entry.data.get(CONF_BATTERY_TYPE)
            new_data = dict(self.config_entry.data)

            # Rensa bort tomma strängar från user_input (När användaren suddar fält i gränssnittet)
            user_input = {k: v for k, v in user_input.items() if v != ""}

            # Fält som är frivilliga (optional) och kan tömmas av användaren i inställningarna.
            # Home Assistant utelämnar dessa helt från user_input om de rensas via gränssnittet.
            clearable_keys = [
                CONF_EV_CHARGING_SENSOR,
                CONF_EXTERNAL_CONTROL_SENSOR,
                CONF_GRID_SENSOR,
                CONF_BATTERY_STATUS_SENSOR,
                CONF_BATTERY_STATUS_KEYWORDS,
                CONF_VIRTUAL_LOAD_SENSOR,
                CONF_DEVICE_STATUS_ENTITY,
                CONF_MAX_DISCHARGE_ENTITY,
                CONF_SOLAR_SENSOR,
                CONF_WATER_HEATER_SWITCH,
                CONF_WATER_HEATER_TEMP_SENSOR,
                CONF_EV_C1_NAME,
                CONF_EV_C1_TARGET_KWH,
                CONF_EV_C1_DEPART_TIME,
                CONF_EV_C1_MAX_KW,
                CONF_EV_C1_CABLE_CONNECTED,
                CONF_EV_C1_IS_CHARGING,
                CONF_EV_C2_NAME,
                CONF_EV_C2_TARGET_KWH,
                CONF_EV_C2_DEPART_TIME,
                CONF_EV_C2_MAX_KW,
                CONF_EV_C2_CABLE_CONNECTED,
                CONF_EV_C2_IS_CHARGING,
            ]

            for key in clearable_keys:
                if key in new_data and key not in user_input:
                    new_data.pop(key)

            if CONF_API_URL in user_input and user_input[CONF_API_URL]:
                url = str(user_input[CONF_API_URL]).strip()
                if url and not (url.startswith("http://") or url.startswith("https://")):
                    url = f"https://{url}"
                user_input[CONF_API_URL] = url

            new_data.update(user_input)

            if battery_type == BATTERY_TYPE_HUAWEI:
                new_data[CONF_BATTERY_SENSOR_INVERT] = True
            elif battery_type == BATTERY_TYPE_HOMEVOLT:
                new_data[CONF_BATTERY_SENSOR_INVERT] = False
                new_data[CONF_GRID_SENSOR_INVERT] = False
            _strip_none_values(new_data)
            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        # Get the battery type from the config entry
        battery_type = self.config_entry.data.get(CONF_BATTERY_TYPE)

        # Auto-discover om vi saknar värden och det är en Huawei
        discovered = {}
        if battery_type == BATTERY_TYPE_HUAWEI:
            device_id = self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)
            if device_id:
                discovered = async_auto_discover_huawei_entities(self.hass, device_id)
        elif battery_type == BATTERY_TYPE_HOMEVOLT:
            device_id = self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)
            if device_id:
                discovered = async_auto_discover_homevolt_entities(self.hass, device_id)
        elif battery_type == BATTERY_TYPE_SOLIS_MODBUS:
            device_id = self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)
            if device_id:
                discovered = async_auto_discover_solis_entities(self.hass, device_id)
        elif battery_type == BATTERY_TYPE_SIGENERGY:
            device_id = self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)
            if device_id:
                discovered = async_auto_discover_sigenergy_entities(self.hass, device_id)
        elif battery_type == BATTERY_TYPE_SOLINTEG:
            device_id = self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)
            if device_id:
                discovered = async_auto_discover_solinteg_entities(self.hass, device_id)

        def get_default(key, default_fallback=vol.UNDEFINED):
            val = self.config_entry.data.get(key)
            if val is not None:
                return val
            return discovered.get(key, default_fallback)

        # Start with the generic schema
        schema_fields = {
            vol.Required(CONF_API_URL, default=get_default(CONF_API_URL, DEFAULT_API_URL)): TextSelector(
                TextSelectorConfig(type="url")
            ),
            vol.Required(CONF_API_KEY, default=get_default(CONF_API_KEY)): TextSelector(),
            _opt(CONF_EV_CHARGING_SENSOR, get_default(CONF_EV_CHARGING_SENSOR)): EntitySelector(
                EntitySelectorConfig()
            ),
            _opt(CONF_SOLAR_SENSOR, get_default(CONF_SOLAR_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            _opt(CONF_EXTERNAL_CONTROL_SENSOR, get_default(CONF_EXTERNAL_CONTROL_SENSOR)): EntitySelector(
                EntitySelectorConfig()
            ),
            _opt(CONF_WATER_HEATER_SWITCH, get_default(CONF_WATER_HEATER_SWITCH)): EntitySelector(
                EntitySelectorConfig(domain=["switch", "input_boolean"])
            ),
            _opt(CONF_WATER_HEATER_TEMP_SENSOR, get_default(CONF_WATER_HEATER_TEMP_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            _opt(CONF_VIRTUAL_LOAD_SENSOR, get_default(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Optional("enable_solar_override", default=get_default("enable_solar_override", False)): bool,
            vol.Optional(CONF_GRAPH_HISTORY_HOURS, default=get_default(CONF_GRAPH_HISTORY_HOURS, "24")): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["12", "24", "48", "72", "168"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="graph_history_hours",
                )
            ),
        }

        if battery_type == BATTERY_TYPE_SONNEN:
            schema_fields.update({
                vol.Required(CONF_HOST, default=get_default(CONF_HOST)): str,
                vol.Required(CONF_API_TOKEN, default=get_default(CONF_API_TOKEN)): str,
                vol.Optional(CONF_PORT, default=get_default(CONF_PORT, DEFAULT_PORT)): int,
            })
        elif battery_type == BATTERY_TYPE_HUAWEI:
            schema_fields.update({
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                _opt(CONF_BATTERY_STATUS_SENSOR, get_default(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
            })
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="huawei_solar")
                ),
                _opt(CONF_DEVICE_STATUS_ENTITY, get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _opt(CONF_MAX_DISCHARGE_ENTITY, get_default(CONF_MAX_DISCHARGE_ENTITY)): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
            })
        elif battery_type == BATTERY_TYPE_HOMEVOLT:
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="homevolt_local")
                ),
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=get_default(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                _opt(CONF_DEVICE_STATUS_ENTITY, get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
            })
        elif battery_type == BATTERY_TYPE_SOLIS_MODBUS:
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="solis_modbus")
                ),
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=get_default(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                _opt(CONF_DEVICE_STATUS_ENTITY, get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
            })
        elif battery_type == BATTERY_TYPE_SIGENERGY:
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                _opt(CONF_DEVICE_STATUS_ENTITY, get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
            })
        elif battery_type == BATTERY_TYPE_SOLINTEG:
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig()
                ),
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=get_default(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                _opt(CONF_DEVICE_STATUS_ENTITY, get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
            })
        else:
            # GENERIC
            schema_fields.update({
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_GRID_SENSOR, get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=get_default(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                _opt(CONF_BATTERY_STATUS_SENSOR, get_default(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                _opt(CONF_BATTERY_STATUS_KEYWORDS, get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
                _opt(CONF_VIRTUAL_LOAD_SENSOR, get_default(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_MIN_SOC, default=get_default(CONF_MIN_SOC, 0.0)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="%")
                ),
            })

        # Lägg till EV fält oavsett batterityp
        schema_fields.update({
            # Car 1
            _opt(CONF_EV_C1_NAME, get_default(CONF_EV_C1_NAME)): selector.TextSelector(selector.TextSelectorConfig()),
            _opt(CONF_EV_C1_TARGET_KWH, get_default(CONF_EV_C1_TARGET_KWH)): EntitySelector(EntitySelectorConfig(domain="input_number")),
            _opt(CONF_EV_C1_DEPART_TIME, get_default(CONF_EV_C1_DEPART_TIME)): EntitySelector(EntitySelectorConfig(domain="input_datetime")),
            _opt(CONF_EV_C1_MAX_KW, get_default(CONF_EV_C1_MAX_KW)): EntitySelector(EntitySelectorConfig(domain="input_number")),
            _opt(CONF_EV_C1_CABLE_CONNECTED, get_default(CONF_EV_C1_CABLE_CONNECTED)): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
            _opt(CONF_EV_C1_IS_CHARGING, get_default(CONF_EV_C1_IS_CHARGING)): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),

            # Car 2
            _opt(CONF_EV_C2_NAME, get_default(CONF_EV_C2_NAME)): selector.TextSelector(selector.TextSelectorConfig()),
            _opt(CONF_EV_C2_TARGET_KWH, get_default(CONF_EV_C2_TARGET_KWH)): EntitySelector(EntitySelectorConfig(domain="input_number")),
            _opt(CONF_EV_C2_DEPART_TIME, get_default(CONF_EV_C2_DEPART_TIME)): EntitySelector(EntitySelectorConfig(domain="input_datetime")),
            _opt(CONF_EV_C2_MAX_KW, get_default(CONF_EV_C2_MAX_KW)): EntitySelector(EntitySelectorConfig(domain="input_number")),
            _opt(CONF_EV_C2_CABLE_CONNECTED, get_default(CONF_EV_C2_CABLE_CONNECTED)): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
            _opt(CONF_EV_C2_IS_CHARGING, get_default(CONF_EV_C2_IS_CHARGING)): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
        })

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_fields))

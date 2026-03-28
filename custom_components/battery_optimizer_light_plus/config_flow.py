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
    CONF_CONSUMPTION_FORECAST_SENSOR,
    DEFAULT_BATTERY_STATUS_KEYWORDS,
    CONF_HOST,
    CONF_API_TOKEN,
    CONF_PORT,
    DEFAULT_PORT,
    CONF_BATTERY_DEVICE_ID,
    CONF_WORKING_MODE_ENTITY,
    CONF_DEVICE_STATUS_ENTITY,
)

_LOGGER = logging.getLogger(__name__)

def async_auto_discover_huawei_entities(hass, device_id: str) -> dict:
    """Attempt to auto-discover standard entities for a Huawei device."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)
    found_entities = {}

    discovery_map = {
        CONF_SOC_SENSOR: ("sensor", "storage_state_of_capacity"),
        CONF_BATTERY_POWER_SENSOR: ("sensor", "storage_charge_discharge_power"),
        CONF_GRID_SENSOR: ("sensor", "grid_active_power"),
        CONF_WORKING_MODE_ENTITY: ("select", "storage_working_mode"),
        CONF_DEVICE_STATUS_ENTITY: ("sensor", "device_status"),
    }

    for conf_key, (domain, translation_key) in discovery_map.items():
        for entry in entries:
            if entry.domain == domain and entry.translation_key == translation_key:
                found_entities[conf_key] = entry.entity_id
                break

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
            menu_options=["sonnen", "huawei", "generic"]
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

    async def async_step_generic(self, user_input=None):
        """Handle the Generic battery configuration step."""
        self.data[CONF_BATTERY_TYPE] = BATTERY_TYPE_GENERIC
        return await self.async_step_common()

    async def async_step_common(self, user_input=None):
        """Handle the common configuration step for all battery types."""
        if user_input is not None:
            self.data.update(user_input)
            return self.async_create_entry(title="Battery Optimizer Light", data=self.data)

        battery_type = self.data.get(CONF_BATTERY_TYPE)

        schema_dict = {
            vol.Required(CONF_API_URL, default=DEFAULT_API_URL): TextSelector(TextSelectorConfig(type="url")),
            vol.Required(CONF_API_KEY): TextSelector(),
            vol.Optional(
                CONF_CONSUMPTION_FORECAST_SENSOR,
                default=self.data.get(CONF_CONSUMPTION_FORECAST_SENSOR)
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
        }

        # Göm de flesta manuella sensorerna om man använder Sonnen!
        if battery_type != BATTERY_TYPE_SONNEN:
            schema_dict.update({
                vol.Required(
                    CONF_SOC_SENSOR,
                    default=self.data.get(CONF_SOC_SENSOR)
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    CONF_GRID_SENSOR,
                    default=self.data.get(CONF_GRID_SENSOR)
                ): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=False): bool,
                vol.Required(
                    CONF_BATTERY_POWER_SENSOR,
                    default=self.data.get(CONF_BATTERY_POWER_SENSOR)
                ): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(
                    CONF_BATTERY_STATUS_SENSOR,
                    default=self.data.get(CONF_BATTERY_STATUS_SENSOR)
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    CONF_BATTERY_STATUS_KEYWORDS,
                    default=DEFAULT_BATTERY_STATUS_KEYWORDS
                ): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(
                    CONF_VIRTUAL_LOAD_SENSOR,
                    default=self.data.get(CONF_VIRTUAL_LOAD_SENSOR)
                ): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            })
            # Huawei hårdkodar battery_sensor_invert=True, visa inte i UI
            if battery_type != BATTERY_TYPE_HUAWEI:
                schema_dict[vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=False)] = bool

            if battery_type == BATTERY_TYPE_HUAWEI:
                schema_dict.update({
                    vol.Required(
                        CONF_WORKING_MODE_ENTITY,
                        default=self.data.get(CONF_WORKING_MODE_ENTITY)
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="select")),
                    vol.Optional(
                        CONF_DEVICE_STATUS_ENTITY,
                        default=self.data.get(CONF_DEVICE_STATUS_ENTITY)
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                })

        return self.async_show_form(step_id="common", data_schema=vol.Schema(schema_dict))


    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return BatteryOptimizerLightOptionsFlow()


class BatteryOptimizerLightOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Battery Optimizer Light."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            battery_type = self.config_entry.data.get(CONF_BATTERY_TYPE)
            new_data = {**self.config_entry.data, **user_input}
            if battery_type == BATTERY_TYPE_HUAWEI:
                new_data[CONF_BATTERY_SENSOR_INVERT] = True
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
            vol.Optional(CONF_CONSUMPTION_FORECAST_SENSOR, default=get_default(CONF_CONSUMPTION_FORECAST_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor")
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
                vol.Optional(CONF_GRID_SENSOR, default=get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_STATUS_SENSOR, default=get_default(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_BATTERY_STATUS_KEYWORDS, default=get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_VIRTUAL_LOAD_SENSOR, default=get_default(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            })
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=get_default(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="huawei_solar")
                ),
                vol.Required(CONF_WORKING_MODE_ENTITY, default=get_default(CONF_WORKING_MODE_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Optional(CONF_DEVICE_STATUS_ENTITY, default=get_default(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            })
        else:
            # GENERIC
            schema_fields.update({
                vol.Required(CONF_SOC_SENSOR, default=get_default(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_GRID_SENSOR, default=get_default(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=get_default(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=get_default(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=get_default(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                vol.Optional(CONF_BATTERY_STATUS_SENSOR, default=get_default(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_BATTERY_STATUS_KEYWORDS, default=get_default(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_VIRTUAL_LOAD_SENSOR, default=get_default(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            })

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_fields))

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

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
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
        if user_input is not None:
            self.data.update(user_input)
            return await self.async_step_common()

        return self.async_show_form(
            step_id="huawei",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="huawei_solar")
                ),
                vol.Required(CONF_WORKING_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Optional(CONF_DEVICE_STATUS_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
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
            vol.Optional(CONF_CONSUMPTION_FORECAST_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor")),
        }

        # Göm de flesta manuella sensorerna om man använder Sonnen!
        if battery_type != BATTERY_TYPE_SONNEN:
            schema_dict.update({
                vol.Required(CONF_SOC_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_GRID_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=False): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=False): bool,
                vol.Optional(CONF_BATTERY_STATUS_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_BATTERY_STATUS_KEYWORDS, default=DEFAULT_BATTERY_STATUS_KEYWORDS): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_VIRTUAL_LOAD_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
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
            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, **user_input}
            )
            return self.async_create_entry(title="", data={})

        # Get the battery type from the config entry
        battery_type = self.config_entry.data.get(CONF_BATTERY_TYPE)

        # Start with the generic schema
        schema_fields = {
            vol.Required(CONF_API_URL, default=self.config_entry.data.get(CONF_API_URL, DEFAULT_API_URL)): TextSelector(
                TextSelectorConfig(type="url")
            ),
            vol.Required(CONF_API_KEY, default=self.config_entry.data.get(CONF_API_KEY)): TextSelector(),
            vol.Optional(CONF_CONSUMPTION_FORECAST_SENSOR, default=self.config_entry.data.get(CONF_CONSUMPTION_FORECAST_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
        }

        if battery_type == BATTERY_TYPE_SONNEN:
            schema_fields.update({
                vol.Required(CONF_HOST, default=self.config_entry.data.get(CONF_HOST)): str,
                vol.Required(CONF_API_TOKEN, default=self.config_entry.data.get(CONF_API_TOKEN)): str,
                vol.Optional(CONF_PORT, default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)): int,
            })
        elif battery_type == BATTERY_TYPE_HUAWEI:
            schema_fields.update({
                vol.Required(CONF_SOC_SENSOR, default=self.config_entry.data.get(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_GRID_SENSOR, default=self.config_entry.data.get(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=self.config_entry.data.get(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=self.config_entry.data.get(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=self.config_entry.data.get(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                vol.Optional(CONF_BATTERY_STATUS_SENSOR, default=self.config_entry.data.get(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_BATTERY_STATUS_KEYWORDS, default=self.config_entry.data.get(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_VIRTUAL_LOAD_SENSOR, default=self.config_entry.data.get(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            })
            schema_fields.update({
                vol.Required(CONF_BATTERY_DEVICE_ID, default=self.config_entry.data.get(CONF_BATTERY_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="huawei_solar")
                ),
                vol.Required(CONF_WORKING_MODE_ENTITY, default=self.config_entry.data.get(CONF_WORKING_MODE_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Optional(CONF_DEVICE_STATUS_ENTITY, default=self.config_entry.data.get(CONF_DEVICE_STATUS_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            })
        else:
            # GENERIC
            schema_fields.update({
                vol.Required(CONF_SOC_SENSOR, default=self.config_entry.data.get(CONF_SOC_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_GRID_SENSOR, default=self.config_entry.data.get(CONF_GRID_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_GRID_SENSOR_INVERT, default=self.config_entry.data.get(CONF_GRID_SENSOR_INVERT, False)): bool,
                vol.Required(CONF_BATTERY_POWER_SENSOR, default=self.config_entry.data.get(CONF_BATTERY_POWER_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
                vol.Optional(CONF_BATTERY_SENSOR_INVERT, default=self.config_entry.data.get(CONF_BATTERY_SENSOR_INVERT, False)): bool,
                vol.Optional(CONF_BATTERY_STATUS_SENSOR, default=self.config_entry.data.get(CONF_BATTERY_STATUS_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_BATTERY_STATUS_KEYWORDS, default=self.config_entry.data.get(CONF_BATTERY_STATUS_KEYWORDS, DEFAULT_BATTERY_STATUS_KEYWORDS)): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_VIRTUAL_LOAD_SENSOR, default=self.config_entry.data.get(CONF_VIRTUAL_LOAD_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor", device_class="power")),
            })

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_fields))

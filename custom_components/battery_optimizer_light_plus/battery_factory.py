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

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    BATTERY_TYPE_HUAWEI,
    CONF_HOST,
    CONF_PORT,
    CONF_API_TOKEN,
    CONF_BATTERY_DEVICE_ID,
    CONF_WORKING_MODE_ENTITY,
    CONF_DEVICE_STATUS_ENTITY,
    CONF_SOC_SENSOR,
)
from .batteries.base import BatteryApi
from .batteries.sonnen.sonnen import SonnenBattery
from .batteries.sonnen.api import SonnenAPI
from .batteries.huawei.huawei import HuaweiBattery


def create_battery_api(hass: HomeAssistant, config: dict) -> BatteryApi:
    """Factory to create a battery api instance."""
    battery_type = config.get(CONF_BATTERY_TYPE)

    if battery_type == BATTERY_TYPE_SONNEN:
        session = async_get_clientsession(hass)
        sonnen_api = SonnenAPI(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            token=config[CONF_API_TOKEN],
            session=session,
        )
        return SonnenBattery(
            hass=hass,
            api=sonnen_api,
            soc_entity=config[CONF_SOC_SENSOR],
        )

    if battery_type == BATTERY_TYPE_HUAWEI:
        return HuaweiBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            working_mode_entity=config[CONF_WORKING_MODE_ENTITY],
            soc_entity=config[CONF_SOC_SENSOR],
            device_status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
        )

    from .batteries.generic import GenericBattery
    return GenericBattery(hass, config.get(CONF_SOC_SENSOR))

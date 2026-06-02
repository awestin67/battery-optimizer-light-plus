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
    BATTERY_TYPE_HOMEVOLT,
    BATTERY_TYPE_SOLIS_MODBUS,
    BATTERY_TYPE_SIGENERGY,
    BATTERY_TYPE_SOLINTEG,
    CONF_HOST,
    CONF_PORT,
    CONF_API_TOKEN,
    CONF_BATTERY_DEVICE_ID,
    CONF_DEVICE_STATUS_ENTITY,
    CONF_MAX_DISCHARGE_ENTITY,
    CONF_SOC_SENSOR,
    CONF_GRID_SENSOR,
    CONF_GRID_SENSOR_INVERT,
    CONF_BATTERY_POWER_SENSOR,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_VIRTUAL_LOAD_SENSOR,
)
from .batteries.base import BatteryApi


def create_battery_api(hass: HomeAssistant, config: dict) -> BatteryApi:
    """Factory to create a battery api instance."""
    battery_type = config.get(CONF_BATTERY_TYPE)

    if battery_type == BATTERY_TYPE_SONNEN:
        from .batteries.sonnen.api import SonnenAPI
        from .batteries.sonnen.sonnen import SonnenBattery

        session = async_get_clientsession(hass)
        sonnen_api = SonnenAPI(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            token=config[CONF_API_TOKEN],
            session=session,
        )
        battery = SonnenBattery(
            hass=hass,
            api=sonnen_api,
            soc_entity=config.get(CONF_SOC_SENSOR),
        )

    elif battery_type == BATTERY_TYPE_HUAWEI:
        from .batteries.huawei.huawei import HuaweiBattery

        battery = HuaweiBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            soc_entity=config[CONF_SOC_SENSOR],
            device_status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
            max_discharge_entity=config.get(CONF_MAX_DISCHARGE_ENTITY),
            grid_entity=config.get(CONF_GRID_SENSOR),
            invert_grid=config.get(CONF_GRID_SENSOR_INVERT, False),
        )

    elif battery_type == BATTERY_TYPE_HOMEVOLT:
        from .batteries.homevolt.homevolt import HomevoltBattery

        battery = HomevoltBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            soc_entity=config[CONF_SOC_SENSOR],
            grid_entity=config.get(CONF_GRID_SENSOR),
            battery_power_entity=config[CONF_BATTERY_POWER_SENSOR],
            load_entity=config.get(CONF_VIRTUAL_LOAD_SENSOR),
            status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
        )

    elif battery_type == BATTERY_TYPE_SOLIS_MODBUS:
        from .batteries.solis_modbus.solis_modbus import SolisModbusBattery

        battery = SolisModbusBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            soc_entity=config.get(CONF_SOC_SENSOR),
            device_status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
            max_discharge_entity=config.get(CONF_MAX_DISCHARGE_ENTITY),
            grid_entity=config.get(CONF_GRID_SENSOR),
            invert_grid=config.get(CONF_GRID_SENSOR_INVERT, False),
        )

    elif battery_type == BATTERY_TYPE_SIGENERGY:
        from .batteries.sigenergy.sigenergy import SigenergyBattery

        battery = SigenergyBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            soc_entity=config.get(CONF_SOC_SENSOR),
            device_status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
            max_discharge_entity=config.get(CONF_MAX_DISCHARGE_ENTITY),
            grid_entity=config.get(CONF_GRID_SENSOR),
            invert_grid=config.get(CONF_GRID_SENSOR_INVERT, False),
        )

    elif battery_type == BATTERY_TYPE_SOLINTEG:
        from .batteries.solinteg.solinteg import SolintegBattery

        battery = SolintegBattery(
            hass=hass,
            device_id=config[CONF_BATTERY_DEVICE_ID],
            soc_entity=config.get(CONF_SOC_SENSOR),
            device_status_entity=config.get(CONF_DEVICE_STATUS_ENTITY),
            max_discharge_entity=config.get(CONF_MAX_DISCHARGE_ENTITY),
            grid_entity=config.get(CONF_GRID_SENSOR),
            invert_grid=config.get(CONF_GRID_SENSOR_INVERT, False),
            invert_battery=config.get(CONF_BATTERY_SENSOR_INVERT, False),
        )
    else:
        from .batteries.generic import GenericBattery
        battery = GenericBattery(hass, config.get(CONF_SOC_SENSOR))

    battery._offgrid_sensor = config.get("offgrid_sensor")
    return battery

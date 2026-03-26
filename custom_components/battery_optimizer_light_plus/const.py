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

# const.py
DOMAIN = "battery_optimizer_light_plus"

# Batterityper
CONF_BATTERY_TYPE = "battery_type"
BATTERY_TYPE_SONNEN = "sonnen"
BATTERY_TYPE_HUAWEI = "huawei"
BATTERY_TYPE_GENERIC = "generic"

# Konfiguration
CONF_API_KEY = "api_key"
CONF_API_URL = "api_url"

# Gemensam konfiguration
CONF_AUTO_CONTROL = "auto_control"

# Sonnen-specifik konfiguration
CONF_HOST = "host"
CONF_API_TOKEN = "api_token"
CONF_PORT = "port"
DEFAULT_PORT = 80

# Huawei-specifik konfiguration
CONF_BATTERY_DEVICE_ID = "battery_device_id"
CONF_WORKING_MODE_ENTITY = "working_mode_entity"
CONF_DEVICE_STATUS_ENTITY = "device_status_entity"

# Sensorer
CONF_SOC_SENSOR = "soc_sensor"
CONF_GRID_SENSOR = "grid_sensor"    # Mätare för husets totala förbrukning (Watt)
CONF_GRID_SENSOR_INVERT = "grid_sensor_invert" # Om mätaren visar positivt vid export
CONF_BATTERY_POWER_SENSOR = "battery_power_sensor" # Batteriets nuvarande effekt (Watt)
CONF_BATTERY_SENSOR_INVERT = "battery_sensor_invert" # Om batteriet visar positivt vid laddning
CONF_BATTERY_STATUS_SENSOR = "battery_status_sensor" # Sensor för driftstatus (t.ex. Operating Mode)
CONF_BATTERY_STATUS_KEYWORDS = "battery_status_keywords" # Nyckelord för underhållsläge
CONF_VIRTUAL_LOAD_SENSOR = "virtual_load_sensor" # Virtuell last (Husets netto utan batteri)
CONF_CONSUMPTION_FORECAST_SENSOR = "consumption_forecast_sensor" # Prognos för morgondagens förbrukning (kWh)

DEFAULT_API_URL = "https://battery-light-production.up.railway.app"
DEFAULT_BATTERY_STATUS_KEYWORDS = "battery_care, puls_orange, calibration, firmware_update, solid_red, warning_internet"

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

import pytest
from unittest.mock import MagicMock
from custom_components.battery_optimizer_light_plus.config_flow import (
    BatteryOptimizerLightConfigFlow,
    BatteryOptimizerLightOptionsFlow,
)
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_GENERIC,
)

@pytest.mark.asyncio
async def test_config_flow_user():
    """Testar att första steget visar menyn."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_user()
    assert result["type"] == "menu"
    assert result["step_id"] == "user"

@pytest.mark.asyncio
async def test_config_flow_huawei():
    """Testar att Huawei-steget går vidare till common."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Första anropet visar formuläret
    result = await flow.async_step_huawei()
    assert result["type"] == "form"
    assert result["step_id"] == "huawei"

    # Andra anropet fyller i formuläret och går vidare till common
    result2 = await flow.async_step_huawei({"battery_device_id": "test_id", "working_mode_entity": "select.mode"})
    assert result2["type"] == "form"
    assert result2["step_id"] == "common"
    assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_HUAWEI

@pytest.mark.asyncio
async def test_config_flow_generic():
    """Testar att Generic-steget sätter typen och går till common."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_generic()
    assert result["type"] == "form"
    assert result["step_id"] == "common"
    assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_GENERIC

@pytest.mark.asyncio
async def test_config_flow_common_submit():
    """Testar att fylla i common skapar en config entry."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN}

    result = await flow.async_step_common({"api_key": "123", "api_url": "http://test"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Battery Optimizer Light"

@pytest.mark.asyncio
async def test_config_flow_sonnen():
    """Testar att Sonnen-steget går vidare till common."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Första anropet visar formuläret
    result_form = await flow.async_step_sonnen()
    assert result_form["type"] == "form"
    assert result_form["step_id"] == "sonnen"

    result = await flow.async_step_sonnen({"host": "1.2.3.4", "api_token": "token"})
    assert result["type"] == "form"
    assert result["step_id"] == "common"
    assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_SONNEN

def test_async_get_options_flow():
    """Testar att metoden för att hämta options flow returnerar rätt klass."""
    entry = MagicMock()
    flow = BatteryOptimizerLightConfigFlow.async_get_options_flow(entry)
    assert isinstance(flow, BatteryOptimizerLightOptionsFlow)

@pytest.mark.asyncio
async def test_options_flow_huawei_and_generic():
    """Testar inställningar för andra batterityper för att öka täckningen."""
    config_entry = MagicMock()
    flow = BatteryOptimizerLightOptionsFlow()
    flow.hass = MagicMock()

    config_entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI, "api_url": "http://test"}
    flow.config_entry = config_entry
    assert (await flow.async_step_init())["type"] == "form"

    config_entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC, "api_url": "http://test"}
    flow.config_entry = config_entry
    assert (await flow.async_step_init())["type"] == "form"

@pytest.mark.asyncio
async def test_options_flow_submit():
    """Testar att spara inställningar."""
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN})
    flow.hass = MagicMock()

    result = await flow.async_step_init({"api_key": "new_key"})
    assert result["type"] == "create_entry"
    flow.hass.config_entries.async_update_entry.assert_called_once()

@pytest.mark.asyncio
async def test_options_flow():
    """Testar att inställningarna kan öppnas för en befintlig konfiguration."""
    config_entry = MagicMock()
    config_entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN, "api_url": "http://test"}

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()

    result = await flow.async_step_init()
    assert result["type"] == "form"

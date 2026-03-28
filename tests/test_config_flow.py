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
from unittest.mock import MagicMock, patch
from custom_components.battery_optimizer_light_plus.config_flow import (
    BatteryOptimizerLightConfigFlow,
    BatteryOptimizerLightOptionsFlow,
)
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    BATTERY_TYPE_HUAWEI,
    BATTERY_TYPE_GENERIC,
    BATTERY_TYPE_HOMEVOLT,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_GRID_SENSOR_INVERT,
)

HUAWEI_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_huawei_entities"
)
HOMEVOLT_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_homevolt_entities"
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

    # Andra anropet fyller i formuläret, mockar auto-discovery, och går vidare
    with patch(HUAWEI_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.discovered_soc"}
        result2 = await flow.async_step_huawei({"battery_device_id": "test_id"})

        assert result2["type"] == "form"
        assert result2["step_id"] == "common"
        assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_HUAWEI
        assert flow.data["soc_sensor"] == "sensor.discovered_soc", "Auto-discovery data sparades inte!"

@pytest.mark.asyncio
async def test_config_flow_homevolt():
    """Testar att Homevolt-steget går vidare till common."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Första anropet visar formuläret
    result = await flow.async_step_homevolt()
    assert result["type"] == "form"
    assert result["step_id"] == "homevolt"

    # Andra anropet fyller i formuläret, mockar auto-discovery, och går vidare
    with patch(HOMEVOLT_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.discovered_soc"}
        result2 = await flow.async_step_homevolt({"battery_device_id": "test_id"})

        assert result2["type"] == "form"
        assert result2["step_id"] == "common"
        assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_HOMEVOLT
        assert flow.data["soc_sensor"] == "sensor.discovered_soc", "Auto-discovery data sparades inte!"

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
    with patch(HUAWEI_DISCOVERY_PATH, return_value={}):
        assert (await flow.async_step_init())["type"] == "form"

    config_entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_HOMEVOLT, "api_url": "http://test"}
    flow.config_entry = config_entry
    with patch(HOMEVOLT_DISCOVERY_PATH, return_value={}):
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

@pytest.mark.asyncio
async def test_options_flow_with_none_values():
    """Testar att formuläret inte kraschar när valfria sensorer sparats som None."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC,
        "api_url": "http://test",
        "virtual_load_sensor": None,
        "battery_status_sensor": None
    }
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_huawei_uses_auto_discovered_defaults():
    """Testar att OptionsFlow använder auto-discovery för att förifylla saknade fält."""
    config_entry = MagicMock()
    # Notera att t.ex. 'soc_sensor' SAKNAS i den sparade datan med flit
    config_entry.data = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI,
        "api_url": "http://test",
        "battery_device_id": "test_device_123"
    }

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()

    with patch(HUAWEI_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.smart_discovered_soc"}
        result = await flow.async_step_init()

        # Leta upp soc_sensor-nyckeln i det genererade formulärets schema
        schema_keys = result["data_schema"].schema.keys()
        soc_key = next((k for k in schema_keys if getattr(k, "schema", None) == "soc_sensor"), None)

        assert soc_key is not None
        assert soc_key.default() == "sensor.smart_discovered_soc", (
            "Auto-discovery-värdet sattes inte som default i OptionsFlow!"
        )

@pytest.mark.asyncio
async def test_options_flow_homevolt_uses_auto_discovered_defaults():
    """Testar att OptionsFlow använder auto-discovery för att förifylla saknade fält för Homevolt."""
    config_entry = MagicMock()
    # Notera att t.ex. 'soc_sensor' SAKNAS i den sparade datan med flit
    config_entry.data = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_HOMEVOLT,
        "api_url": "http://test",
        "battery_device_id": "test_device_123"
    }

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()

    with patch(HOMEVOLT_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.smart_discovered_homevolt_soc"}
        result = await flow.async_step_init()

        # Leta upp soc_sensor-nyckeln i det genererade formulärets schema
        schema_keys = result["data_schema"].schema.keys()
        soc_key = next((k for k in schema_keys if getattr(k, "schema", None) == "soc_sensor"), None)

        assert soc_key is not None
        assert soc_key.default() == "sensor.smart_discovered_homevolt_soc", (
            "Auto-discovery-värdet sattes inte som default i OptionsFlow för Homevolt!"
        )

@pytest.mark.asyncio
async def test_config_flow_huawei_sets_invert_true():
    """Testar att Huawei-flödet automatiskt sätter invert till True."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Starta flödet och välj Huawei
    result = await flow.async_step_huawei()
    assert result["type"] == "form"

    # Nu är `battery_sensor_invert` satt till True i bakgrunden
    assert flow.data.get(CONF_BATTERY_SENSOR_INVERT) is True

    # Gå vidare till common step
    with patch(HUAWEI_DISCOVERY_PATH, return_value={}):
        result2 = await flow.async_step_huawei(
            {"battery_device_id": "test_id"}
        )

    # Verifiera att UI-switchen för invertering är BORTTAGEN för Huawei
    common_schema_keys = result2["data_schema"].schema.keys()
    invert_toggle_present = any(
        hasattr(k, "schema") and k.schema == CONF_BATTERY_SENSOR_INVERT for k in common_schema_keys
    )
    assert not invert_toggle_present, "Invert-switchen ska vara dold för Huawei"

    # Fyll i common och skapa entry
    result3 = await flow.async_step_common({
        "api_key": "123",
        "api_url": "http://test",
        "working_mode_entity": "select.mode"
    })

    assert result3["type"] == "create_entry"
    assert result3["data"][CONF_BATTERY_TYPE] == BATTERY_TYPE_HUAWEI
    # Viktigast: verifiera att den slutgiltiga datan har invert=True
    assert result3["data"][CONF_BATTERY_SENSOR_INVERT] is True

@pytest.mark.asyncio
async def test_config_flow_homevolt_sets_inverts_false():
    """Testar att Homevolt-flödet döljer och sätter båda inverts till False."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Starta flödet och välj Homevolt
    result = await flow.async_step_homevolt()
    assert result["type"] == "form"

    # Verifiera att false sattes tyst i bakgrunden
    assert flow.data.get(CONF_BATTERY_SENSOR_INVERT) is False
    assert flow.data.get(CONF_GRID_SENSOR_INVERT) is False

    # Gå vidare till common step
    with patch(HOMEVOLT_DISCOVERY_PATH, return_value={}):
        result2 = await flow.async_step_homevolt(
            {"battery_device_id": "test_id"}
        )

    # Verifiera att UI-switcharna för invertering är BORTTAGNA för Homevolt
    common_schema_keys = result2["data_schema"].schema.keys()
    bat_invert_present = any(
        hasattr(k, "schema") and k.schema == CONF_BATTERY_SENSOR_INVERT for k in common_schema_keys
    )
    grid_invert_present = any(
        hasattr(k, "schema") and k.schema == CONF_GRID_SENSOR_INVERT for k in common_schema_keys
    )
    assert not bat_invert_present, "Batteri invert-switchen ska vara dold för Homevolt"
    assert not grid_invert_present, "Grid invert-switchen ska vara dold för Homevolt"

    # Fyll i common och skapa entry
    result3 = await flow.async_step_common({"api_key": "123", "api_url": "http://test"})

    assert result3["type"] == "create_entry"
    assert result3["data"][CONF_BATTERY_TYPE] == BATTERY_TYPE_HOMEVOLT
    assert result3["data"][CONF_BATTERY_SENSOR_INVERT] is False
    assert result3["data"][CONF_GRID_SENSOR_INVERT] is False

@pytest.mark.asyncio
async def test_config_flow_generic_respects_invert_choice():
    """Testar att Generic-flödet respekterar användarens val för invertering."""
    # --- Fall 1: Användaren väljer att invertera ---
    flow_true = BatteryOptimizerLightConfigFlow()
    flow_true.hass = MagicMock()

    # Välj Generic
    await flow_true.async_step_generic()

    # Fyll i common-steget med invert=True
    result_true = await flow_true.async_step_common({
        "api_key": "123",
        "api_url": "http://test",
        "battery_power_sensor": "sensor.battery",
        CONF_BATTERY_SENSOR_INVERT: True
    })

    assert result_true["type"] == "create_entry"
    assert result_true["data"][CONF_BATTERY_SENSOR_INVERT] is True

    # --- Fall 2: Användaren väljer INTE att invertera (default) ---
    flow_false = BatteryOptimizerLightConfigFlow()
    flow_false.hass = MagicMock()

    await flow_false.async_step_generic()

    # Fyll i common-steget utan att specificera invert (förlitar oss på default False)
    result_false = await flow_false.async_step_common({
        "api_key": "123",
        "api_url": "http://test",
        "battery_power_sensor": "sensor.battery"
    })
    assert result_false["type"] == "create_entry"
    assert result_false["data"].get(CONF_BATTERY_SENSOR_INVERT, False) is False

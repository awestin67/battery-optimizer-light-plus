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
    BATTERY_TYPE_SOLIS_MODBUS,
    BATTERY_TYPE_KOSTAL,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_GRID_SENSOR_INVERT,
)

HUAWEI_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_huawei_entities"
)
HOMEVOLT_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_homevolt_entities"
)
SOLIS_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_solis_entities"
)
KOSTAL_DISCOVERY_PATH = (
    "custom_components.battery_optimizer_light_plus.config_flow.async_auto_discover_kostal_entities"
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
async def test_config_flow_solis_modbus():
    """Testar att Solis-steget går vidare till common och sparar auto-discovery."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_solis_modbus()
    assert result["type"] == "form"
    assert result["step_id"] == "solis_modbus"

    with patch(SOLIS_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.solis_soc"}
        result2 = await flow.async_step_solis_modbus({"battery_device_id": "solis_123"})

        assert result2["type"] == "form"
        assert result2["step_id"] == "common"
        assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_SOLIS_MODBUS
        assert flow.data["soc_sensor"] == "sensor.solis_soc", "Auto-discovery data sparades inte för Solis!"

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

    config_entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_SOLIS_MODBUS, "api_url": "http://test"}
    flow.config_entry = config_entry
    with patch(SOLIS_DISCOVERY_PATH, return_value={}):
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
async def test_options_flow_solis_uses_auto_discovered_defaults():
    """Testar att OptionsFlow använder auto-discovery för att förifylla saknade fält för Solis."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_SOLIS_MODBUS,
        "api_url": "http://test",
        "battery_device_id": "test_device_123"
    }

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()

    with patch(SOLIS_DISCOVERY_PATH) as mock_discover:
        mock_discover.return_value = {"soc_sensor": "sensor.smart_discovered_solis_soc"}
        result = await flow.async_step_init()

        schema_keys = result["data_schema"].schema.keys()
        soc_key = next((k for k in schema_keys if getattr(k, "schema", None) == "soc_sensor"), None)

        assert soc_key is not None
        assert soc_key.default() == "sensor.smart_discovered_solis_soc"

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


@pytest.mark.asyncio
async def test_config_flow_huawei_strips_none_virtual_load_sensor():
    """Testar att Huawei-flödet lyckas spara utan Virtual Load Sensor (None rensas)."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    with patch(HUAWEI_DISCOVERY_PATH, return_value={}):
        await flow.async_step_huawei({"battery_device_id": "test_id"})

    # Skicka in common-formuläret utan virtual_load_sensor (dvs None)
    result = await flow.async_step_common({
        "api_key": "abc",
        "api_url": "http://test",
        "soc_sensor": "sensor.soc",
        "battery_power_sensor": "sensor.battery",
        "virtual_load_sensor": None,
    })

    assert result["type"] == "create_entry"
    assert "virtual_load_sensor" not in result["data"], (
        "virtual_load_sensor med None-värde ska inte sparas i config entry"
    )


@pytest.mark.asyncio
async def test_options_flow_strips_none_values():
    """Testar att OptionsFlow tar bort None-värden när man sparar."""
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI})
    flow.hass = MagicMock()

    result = await flow.async_step_init({
        "api_key": "new_key",
        "api_url": "http://test",
        "virtual_load_sensor": None,
        "grid_sensor": None,
    })

    assert result["type"] == "create_entry"
    call_args = flow.hass.config_entries.async_update_entry.call_args
    saved_data = call_args[1]["data"]
    assert "virtual_load_sensor" not in saved_data, (
        "virtual_load_sensor med None ska inte sparas via OptionsFlow"
    )
    assert "grid_sensor" not in saved_data, (
        "grid_sensor med None ska inte sparas via OptionsFlow"
    )

@pytest.mark.asyncio
async def test_options_flow_strips_empty_strings():
    """Testar att OptionsFlow tar bort tomma strängar när man sparar (t.ex. när användaren raderar ett fält)."""
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={
        CONF_BATTERY_TYPE: BATTERY_TYPE_HUAWEI,
        "virtual_load_sensor": "sensor.old_load",
        "grid_sensor": "sensor.old_grid"
    })
    flow.hass = MagicMock()

    result = await flow.async_step_init({
        "api_key": "new_key",
        "api_url": "http://test",
        "virtual_load_sensor": "",
        "grid_sensor": "",
    })

    assert result["type"] == "create_entry"
    call_args = flow.hass.config_entries.async_update_entry.call_args
    saved_data = call_args[1]["data"]

    assert "virtual_load_sensor" not in saved_data, "Fält med tom sträng ska tas bort helt"
    assert "grid_sensor" not in saved_data, "Fält med tom sträng ska tas bort helt"

@pytest.mark.asyncio
async def test_config_flow_enable_solar_override():
    """Testar att enable_solar_override sparas korrekt vid installation."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    await flow.async_step_generic()

    # Fall 1: Användaren aktiverar funktionen (True)
    result_true = await flow.async_step_common({
        "api_key": "123",
        "api_url": "http://test",
        "enable_solar_override": True
    })
    assert result_true["type"] == "create_entry"
    assert result_true["data"]["enable_solar_override"] is True

    # Fall 2: Användaren avaktiverar funktionen (False)
    flow2 = BatteryOptimizerLightConfigFlow()
    flow2.hass = MagicMock()
    await flow2.async_step_generic()
    result_false = await flow2.async_step_common({
        "api_key": "123",
        "api_url": "http://test",
        "enable_solar_override": False
    })
    assert result_false["type"] == "create_entry"
    assert result_false["data"]["enable_solar_override"] is False

@pytest.mark.asyncio
async def test_options_flow_enable_solar_override():
    """Testar att enable_solar_override kan uppdateras via inställningsmenyn."""
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC, "enable_solar_override": False})
    flow.hass = MagicMock()

    await flow.async_step_init({"api_key": "new_key", "api_url": "http://test", "enable_solar_override": True})

    saved_data = flow.hass.config_entries.async_update_entry.call_args[1]["data"]
    assert saved_data["enable_solar_override"] is True

@pytest.mark.asyncio
async def test_config_flow_api_url_normalization():
    """Testar att URL utan protokoll automatiskt får https:// i config flow."""
    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()
    await flow.async_step_generic()

    result = await flow.async_step_common({
        "api_key": "123",
        "api_url": "battery-optimizer-light-development.up.railway.app",
    })

    assert result["type"] == "create_entry"
    assert result["data"]["api_url"] == "https://battery-optimizer-light-development.up.railway.app"

@pytest.mark.asyncio
async def test_options_flow_api_url_normalization():
    """Testar att URL utan protokoll automatiskt får https:// i options flow."""
    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC, "api_url": "https://old.url"})
    flow.hass = MagicMock()

    await flow.async_step_init({
        "api_key": "new_key",
        "api_url": "battery-optimizer-light-development.up.railway.app",
    })

    saved_data = flow.hass.config_entries.async_update_entry.call_args[1]["data"]
    assert saved_data["api_url"] == "https://battery-optimizer-light-development.up.railway.app"

@pytest.mark.asyncio
async def test_config_flow_water_heater_switch():
    """Testar att water_heater_switch sparas vid installation."""
    from custom_components.battery_optimizer_light_plus.const import CONF_WATER_HEATER_SWITCH

    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()
    await flow.async_step_generic()

    result = await flow.async_step_common({
        "api_key": "123",
        "api_url": "https://test",
        CONF_WATER_HEATER_SWITCH: "switch.ivt_extra_varmvatten",
    })

    assert result["type"] == "create_entry"
    assert result["data"][CONF_WATER_HEATER_SWITCH] == "switch.ivt_extra_varmvatten"

@pytest.mark.asyncio
async def test_options_flow_water_heater_switch():
    """Testar att water_heater_switch kan uppdateras eller tas bort i inställningarna."""
    from custom_components.battery_optimizer_light_plus.const import CONF_WATER_HEATER_SWITCH

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = MagicMock(data={
        CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC,
        "api_url": "https://test",
        CONF_WATER_HEATER_SWITCH: "switch.old_switch"
    })
    flow.hass = MagicMock()

    # Uppdatera till ny switch
    await flow.async_step_init({
        "api_key": "new_key",
        "api_url": "https://test",
        CONF_WATER_HEATER_SWITCH: "switch.shelly_extra_vvb",
    })

    saved_data = flow.hass.config_entries.async_update_entry.call_args[1]["data"]
    assert saved_data[CONF_WATER_HEATER_SWITCH] == "switch.shelly_extra_vvb"


@pytest.mark.asyncio
async def test_config_flow_water_heater_temp_sensor():
    """Testar att water_heater_temp_sensor kan konfigureras i common-steget och options flow."""
    from custom_components.battery_optimizer_light_plus.const import (
        CONF_SOC_SENSOR,
        CONF_WATER_HEATER_TEMP_SENSOR,
    )

    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC}

    result = await flow.async_step_common({
        "api_url": "https://test.app",
        "api_key": "testkey",
        CONF_SOC_SENSOR: "sensor.battery_soc",
        CONF_WATER_HEATER_TEMP_SENSOR: "sensor.ivt_varmvattentemperatur",
    })

    assert result["type"] == "create_entry"
    assert result["data"][CONF_WATER_HEATER_TEMP_SENSOR] == "sensor.ivt_varmvattentemperatur"

    # Testa Options Flow
    options_flow = BatteryOptimizerLightOptionsFlow()
    options_flow.config_entry = MagicMock(data={
        CONF_BATTERY_TYPE: BATTERY_TYPE_GENERIC,
        "api_url": "https://test",
        CONF_WATER_HEATER_TEMP_SENSOR: "sensor.ivt_varmvattentemperatur"
    })
    options_flow.hass = MagicMock()

    await options_flow.async_step_init({
        "api_key": "new_key",
        "api_url": "https://test",
        CONF_WATER_HEATER_TEMP_SENSOR: "sensor.shelly_vvb_temp",
    })

    saved_data = options_flow.hass.config_entries.async_update_entry.call_args[1]["data"]
    assert saved_data[CONF_WATER_HEATER_TEMP_SENSOR] == "sensor.shelly_vvb_temp"


@pytest.mark.asyncio
async def test_config_flow_kostal():
    """Testar att Kostal-steget hämtar host/port, auto-discovery och går vidare till common."""
    from custom_components.battery_optimizer_light_plus.const import (
        CONF_BATTERY_DEVICE_ID,
        CONF_HOST,
        CONF_PORT,
    )

    flow = BatteryOptimizerLightConfigFlow()
    flow.hass = MagicMock()

    # Första anropet visar formuläret
    result = await flow.async_step_kostal()
    assert result["type"] == "form"
    assert result["step_id"] == "kostal"

    # Mocka device registry och config entries
    mock_device = MagicMock()
    mock_device.config_entries = {"kostal_entry_1"}
    flow.hass.config_entries.async_get_entry.return_value = MagicMock(
        data={"host": "192.168.1.150"}
    )

    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr, \
         patch(KOSTAL_DISCOVERY_PATH) as mock_discover:
        mock_dr.return_value.async_get.return_value = mock_device
        mock_discover.return_value = {
            "soc_sensor": "sensor.plenticore_battery_soc",
            "virtual_load_sensor": "sensor.plenticore_home_power",
        }

        result2 = await flow.async_step_kostal({CONF_BATTERY_DEVICE_ID: "kostal_dev_id"})

        assert result2["type"] == "form"
        assert result2["step_id"] == "common"
        assert flow.data[CONF_BATTERY_TYPE] == BATTERY_TYPE_KOSTAL
        assert flow.data[CONF_HOST] == "192.168.1.150"
        assert flow.data[CONF_PORT] == 1502
        assert flow.data["soc_sensor"] == "sensor.plenticore_battery_soc"
        assert flow.data["virtual_load_sensor"] == "sensor.plenticore_home_power"
        assert flow.data[CONF_BATTERY_SENSOR_INVERT] is False
        assert flow.data[CONF_GRID_SENSOR_INVERT] is False


def test_async_auto_discover_kostal_entities():
    """Testar att async_auto_discover_kostal_entities mappar sensorer korrekt."""
    from custom_components.battery_optimizer_light_plus.config_flow import (
        async_auto_discover_kostal_entities,
    )
    from custom_components.battery_optimizer_light_plus.const import (
        CONF_SOC_SENSOR,
        CONF_BATTERY_POWER_SENSOR,
        CONF_GRID_SENSOR,
        CONF_VIRTUAL_LOAD_SENSOR,
        CONF_SOLAR_SENSOR,
        CONF_DEVICE_STATUS_ENTITY,
    )

    hass = MagicMock()
    mock_registry = MagicMock()

    # Skapa fejkade entiteter enligt Kostals namnmönster
    entry_soc = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local:battery_soc", entity_id="sensor.battery_soc"
    )
    entry_bat_p = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local:battery_p", entity_id="sensor.battery_p"
    )
    entry_grid_p = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local_grid_p", entity_id="sensor.grid_p"
    )
    entry_home_p = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local_home_p", entity_id="sensor.home_p"
    )
    entry_dc_p = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local_dc_p", entity_id="sensor.dc_p"
    )
    entry_state = MagicMock(
        domain="sensor", unique_id="entry_id_devices:local_inverter_state", entity_id="sensor.inverter_state"
    )

    with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_registry), \
         patch("homeassistant.helpers.entity_registry.async_entries_for_device", return_value=[
             entry_soc, entry_bat_p, entry_grid_p, entry_home_p, entry_dc_p, entry_state
         ]):
        res = async_auto_discover_kostal_entities(hass, "test_device")

        assert res[CONF_SOC_SENSOR] == "sensor.battery_soc"
        assert res[CONF_BATTERY_POWER_SENSOR] == "sensor.battery_p"
        assert res[CONF_GRID_SENSOR] == "sensor.grid_p"
        assert res[CONF_VIRTUAL_LOAD_SENSOR] == "sensor.home_p"
        assert res[CONF_SOLAR_SENSOR] == "sensor.dc_p"
        assert res[CONF_DEVICE_STATUS_ENTITY] == "sensor.inverter_state"





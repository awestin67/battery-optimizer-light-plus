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

import datetime
import pytest
import aiohttp
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.battery_optimizer_light_plus import PeakGuard
from custom_components.battery_optimizer_light_plus.battery_factory import create_battery_api
from custom_components.battery_optimizer_light_plus.batteries.sonnen.sonnen import SonnenBattery
from custom_components.battery_optimizer_light_plus.batteries.sonnen.api import SonnenAPI
from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    CONF_HOST,
    CONF_PORT,
    CONF_API_TOKEN,
    CONF_SOC_SENSOR,
)

@pytest.mark.asyncio
async def test_create_sonnen_battery():
    """Test the instantiation of SonnenBattery through the factory."""
    hass = MagicMock()
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 8080,
        CONF_API_TOKEN: "test_token",
        CONF_SOC_SENSOR: "sensor.sonnen_soc",
    }

    patch_api = "custom_components.battery_optimizer_light_plus.batteries.sonnen.api.SonnenAPI"
    patch_session = "custom_components.battery_optimizer_light_plus.battery_factory.async_get_clientsession"
    with patch(patch_api) as mock_sonnen_api, \
         patch(patch_session) as mock_session:
        mock_session.return_value = "mocked_session"
        battery_api = create_battery_api(hass, config)

        assert isinstance(battery_api, SonnenBattery)
        mock_sonnen_api.assert_called_once_with(
            host="1.2.3.4",
            port=8080,
            token="test_token",
            session="mocked_session",
        )

@pytest.mark.asyncio
async def test_create_sonnen_battery_without_soc_sensor():
    """Testar att SonnenBattery kan initieras även om soc_sensor saknas (förebygger KeyError)."""
    hass = MagicMock()
    # Konfiguration HELT UTAN CONF_SOC_SENSOR
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 8080,
        CONF_API_TOKEN: "test_token",
    }

    patch_api = "custom_components.battery_optimizer_light_plus.batteries.sonnen.api.SonnenAPI"
    patch_session = "custom_components.battery_optimizer_light_plus.battery_factory.async_get_clientsession"
    with patch(patch_api), patch(patch_session):
        battery_api = create_battery_api(hass, config)
        assert isinstance(battery_api, SonnenBattery)

@pytest.fixture
def mock_sonnen_api():
    """Mockerar SonnenAPI."""
    api = MagicMock()
    api.async_get_status = AsyncMock()
    api.async_set_operating_mode = AsyncMock()
    api.async_charge = AsyncMock()
    api.async_discharge = AsyncMock()
    api.async_get_software_version = AsyncMock(return_value="1.30.0")
    api.async_set_site_limits = AsyncMock(return_value=True)
    api.async_get_site_limits = AsyncMock(return_value=None)
    return api

@pytest.fixture
def sonnen_battery(mock_sonnen_api):
    """Skapar en instans av SonnenBattery."""
    hass = MagicMock()
    hass.states.get = MagicMock()
    return SonnenBattery(hass, mock_sonnen_api, "sensor.sonnen_soc")

@pytest.mark.asyncio
async def test_get_current_soc_from_api(sonnen_battery, mock_sonnen_api):
    """Testar att SoC hämtas primärt via lokalt API."""
    sonnen_battery.coordinator.data = {"USOC": 55}

    soc = await sonnen_battery.get_current_soc()

    assert soc == 55.0
    sonnen_battery._hass.states.get.assert_not_called()

@pytest.mark.asyncio
async def test_get_current_soc_fallback_sensor(sonnen_battery, mock_sonnen_api):
    """Testar att SoC faller tillbaka på HA-sensorn om API:et kraschar."""
    sonnen_battery.coordinator.data = None  # Simulerar ett kraschat nätverk

    mock_state = MagicMock()
    mock_state.state = "60"
    sonnen_battery._hass.states.get.return_value = mock_state

    soc = await sonnen_battery.get_current_soc()

    assert soc == 60.0
    sonnen_battery._hass.states.get.assert_called_once_with("sensor.sonnen_soc")

@pytest.mark.asyncio
async def test_apply_action_charge(sonnen_battery, mock_sonnen_api):
    """Testar att CHARGE aktiverar manuellt läge (1) och skickar laddning."""
    await sonnen_battery.apply_action("CHARGE", target_kw=4.0)

    # Ska sättas till manuellt läge
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(1)
    # 4.0 kW ska bli 4000 W
    mock_sonnen_api.async_charge.assert_called_once_with(4000)

@pytest.mark.asyncio
async def test_apply_action_discharge(sonnen_battery, mock_sonnen_api):
    """Testar att DISCHARGE aktiverar manuellt läge (1) och skickar urladdning."""
    await sonnen_battery.apply_action("DISCHARGE", target_kw=1.5)

    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(1)
    mock_sonnen_api.async_discharge.assert_called_once_with(1500)

@pytest.mark.asyncio
async def test_apply_action_hold(sonnen_battery, mock_sonnen_api):
    """Testar att HOLD sätter manuellt läge (1) och nollar effekten."""
    await sonnen_battery.apply_action("HOLD")

    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(1)
    # Hold görs genom att skicka 0 W till både laddning och urladdning
    mock_sonnen_api.async_charge.assert_called_once_with(0)
    mock_sonnen_api.async_discharge.assert_called_once_with(0)

@pytest.mark.asyncio
async def test_apply_action_idle(sonnen_battery, mock_sonnen_api):
    """Testar att IDLE släpper batteriet till auto-läge (2)."""
    await sonnen_battery.apply_action("IDLE")

    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(2)
    # Inga effektkommandon ska skickas
    mock_sonnen_api.async_charge.assert_not_called()
    mock_sonnen_api.async_discharge.assert_not_called()

@pytest.mark.asyncio
async def test_get_virtual_load(sonnen_battery):
    """Testar att virtuell last beräknas korrekt (Consumption - Production)."""
    sonnen_battery.coordinator.data = {"Consumption_W": 5000, "Production_W": 2000}
    load = await sonnen_battery.get_virtual_load()
    assert load == 3000.0

    # Testar fallback om data saknas
    sonnen_battery.coordinator.data = {"Consumption_W": 5000}
    assert await sonnen_battery.get_virtual_load() is None

    # Test ValueError
    sonnen_battery.coordinator.data = {"Consumption_W": "invalid", "Production_W": 2000}
    assert await sonnen_battery.get_virtual_load() is None

@pytest.mark.asyncio
async def test_get_solar_power(sonnen_battery):
    """Testar att solproduktionen hämtas korrekt från Sonnen."""
    sonnen_battery.coordinator.data = {"Production_W": 4200}
    solar_power = await sonnen_battery.get_solar_power()
    assert solar_power == 4200.0

    sonnen_battery.coordinator.data = {}
    assert await sonnen_battery.get_solar_power() is None

    # Test ValueError
    sonnen_battery.coordinator.data = {"Production_W": "invalid_value"}
    assert await sonnen_battery.get_solar_power() is None

@pytest.mark.asyncio
async def test_get_battery_power(sonnen_battery):
    """Testar att batterieffekt hämtas korrekt."""
    sonnen_battery.coordinator.data = {"Pac_total_W": -1500}
    power = await sonnen_battery.get_battery_power()
    assert power == -1500.0

    sonnen_battery.coordinator.data = {}
    assert await sonnen_battery.get_battery_power() is None

    # Test ValueError
    sonnen_battery.coordinator.data = {"Pac_total_W": "invalid"}
    assert await sonnen_battery.get_battery_power() is None

@pytest.mark.asyncio
async def test_get_grid_power(sonnen_battery):
    """Testar att nätutbyte hämtas korrekt."""
    sonnen_battery.coordinator.data = {"GridFeedIn_W": 300}
    power = await sonnen_battery.get_grid_power()
    # Om API returnerar positivt (Export), ska metoden ge negativt.
    assert power == -300.0

    sonnen_battery.coordinator.data = {}
    assert await sonnen_battery.get_grid_power() is None

    # Test ValueError
    sonnen_battery.coordinator.data = {"GridFeedIn_W": "invalid"}
    assert await sonnen_battery.get_grid_power() is None

@pytest.mark.asyncio
async def test_get_status_text(sonnen_battery):
    """Testar att systemstatus hämtas korrekt."""
    sonnen_battery.coordinator.data = {"SystemStatus": "OnGrid"}
    status = await sonnen_battery.get_status_text()
    assert status == "OnGrid"

    sonnen_battery.coordinator.data = {}
    assert await sonnen_battery.get_status_text() is None

@pytest.mark.asyncio
async def test_is_offgrid_from_api(sonnen_battery):
    """Testar att is_offgrid använder Sonnen API:ets SystemStatus primärt."""
    sonnen_battery.coordinator.data = {"SystemStatus": "OffGrid"}
    assert await sonnen_battery.is_offgrid() is True

    sonnen_battery.coordinator.data = {"SystemStatus": "OnGrid"}
    assert await sonnen_battery.is_offgrid() is False

    # Testar okända värden
    sonnen_battery.coordinator.data = {"SystemStatus": "Backup"}
    assert await sonnen_battery.is_offgrid() is True

@pytest.mark.asyncio
async def test_is_offgrid_fallback_sensor(sonnen_battery):
    """Testar att is_offgrid faller tillbaka på HA-sensorn om API-data saknas."""
    # Data saknar SystemStatus
    sonnen_battery.coordinator.data = {}
    sonnen_battery._offgrid_sensor = "binary_sensor.my_offgrid"

    mock_state = MagicMock()
    mock_state.state = "on"
    sonnen_battery._hass.states.get.return_value = mock_state

    assert await sonnen_battery.is_offgrid() is True
    sonnen_battery._hass.states.get.assert_called_once_with("binary_sensor.my_offgrid")

    # Testa avstängd sensor
    mock_state.state = "off"
    assert await sonnen_battery.is_offgrid() is False

@pytest.mark.asyncio
async def test_sonnen_api_methods():
    """Testar att SonnenAPI sätter ihop och skickar korrekta HTTP-anrop."""
    mock_session = MagicMock()
    mock_response = AsyncMock()

    # aiohttp:s raise_for_status är synkron, så vi mockar den specifikt
    mock_response.raise_for_status = MagicMock()
    mock_response.status = 200

    # Konfigurera mock_session att returnera mock_response när den anropas med 'async with'
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.put.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aenter__.return_value = mock_response

    api = SonnenAPI("192.168.1.50", 80, "my-secret-token", mock_session)

    expected_headers = {"Auth-Token": "my-secret-token", "Content-Type": "application/json"}

    # 1. Test get_status
    mock_response.json.side_effect = [{"USOC": 50}, {"EM_USOC": 5}]
    status = await api.async_get_status()
    assert status == {"USOC": 50, "EM_USOC": 5}

    assert mock_session.get.call_count == 2
    mock_session.get.assert_any_call(
        "http://192.168.1.50:80/api/v2/status", headers=expected_headers
    )
    mock_session.get.assert_any_call(
        "http://192.168.1.50:80/api/v2/configurations", headers=expected_headers
    )

    # 2. Test set_operating_mode via /api/v2/configurations
    assert await api.async_set_operating_mode(1) is True
    mock_session.put.assert_called_once_with(
        "http://192.168.1.50:80/api/v2/configurations",
        json={"EM_OperatingMode": "1"},
        headers=expected_headers,
        timeout=aiohttp.ClientTimeout(total=5),
    )

    # 3. Test charge
    assert await api.async_charge(3000) is True
    mock_session.post.assert_any_call(
        "http://192.168.1.50:80/api/v2/setpoint/charge/3000", json={}, headers=expected_headers
    )

    # 4. Test discharge
    assert await api.async_discharge(2500) is True
    mock_session.post.assert_any_call(
        "http://192.168.1.50:80/api/v2/setpoint/discharge/2500", json={}, headers=expected_headers
    )


@pytest.mark.asyncio
async def test_sonnen_api_software_version_and_site_limits():
    """Testar att SonnenAPI implementerar DE_Software och Site Limits korrekt."""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.status = 200

    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.put.return_value.__aenter__.return_value = mock_response

    api = SonnenAPI("192.168.1.50", 80, "my-token", mock_session)
    expected_headers = {"Auth-Token": "my-token", "Content-Type": "application/json"}

    # 1. async_get_software_version med dict
    mock_response.json = AsyncMock(return_value={"DE_Software": "1.35.14"})
    sw = await api.async_get_software_version()
    assert sw == "1.35.14"
    mock_session.get.assert_called_with(
        "http://192.168.1.50:80/api/v2/configurations/DE_Software",
        headers=expected_headers,
        timeout=aiohttp.ClientTimeout(total=5),
    )

    # 2. async_get_software_version med raw string
    mock_response.json = AsyncMock(return_value="1.36.0")
    assert await api.async_get_software_version() == "1.36.0"

    # 2b. async_get_software_version fallback till /api/v2/configurations vid 404 på DE_Software
    mock_resp_404 = MagicMock(status=404)
    mock_resp_404.text = AsyncMock(return_value="Not Found")
    mock_resp_conf = MagicMock(status=200)
    mock_resp_conf.json = AsyncMock(return_value={"DE_Software": "1.37.0"})
    mock_session.get.side_effect = [
        MagicMock(__aenter__=AsyncMock(return_value=mock_resp_404), __aexit__=AsyncMock()),
        MagicMock(__aenter__=AsyncMock(return_value=mock_resp_conf), __aexit__=AsyncMock()),
    ]
    assert await api.async_get_software_version() == "1.37.0"
    mock_session.get.side_effect = None

    # 3. async_get_software_version felhantering
    mock_session.get.side_effect = Exception("Network timeout")
    assert await api.async_get_software_version() is None
    mock_session.get.side_effect = None

    # 4. async_set_site_limits success med standardduration
    mock_response.status = 200
    limits = {
        "p_gcp_max_import_limit": 4500,
        "p_gcp_max_export_limit": 0,
        "empty_field": None,
    }
    assert await api.async_set_site_limits(limits) is True
    # Verifiera att None rensats och duration sattes
    mock_session.put.assert_called_with(
        "http://192.168.1.50:80/api/v2/site/limits",
        json={"p_gcp_max_import_limit": 4500, "p_gcp_max_export_limit": 0, "duration": "PT10M"},
        headers=expected_headers,
        timeout=aiohttp.ClientTimeout(total=5),
    )

    # 5. async_set_site_limits med egen duration och status 204
    mock_response.status = 204
    assert await api.async_set_site_limits({"duration": "PT60S"}) is True

    # 6. async_set_site_limits vid felstatus
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value="Bad Request")
    assert await api.async_set_site_limits({"p_gcp_max_import_limit": 4500}) is False

    # 7. async_set_site_limits vid felstatus med EM2-krav och lyckad retry
    mock_resp_em2 = MagicMock(status=400)
    mock_resp_em2.text = AsyncMock(return_value='{"error":"Site limits can only be set in EM2"}')
    mock_resp_mode2 = MagicMock(status=200)
    mock_resp_mode2.text = AsyncMock(return_value='{"EM_OperatingMode":"2"}')
    mock_resp_ok = MagicMock(status=200)
    mock_resp_ok.text = AsyncMock(return_value='{}')
    mock_session.put.side_effect = [
        MagicMock(__aenter__=AsyncMock(return_value=mock_resp_em2), __aexit__=AsyncMock()),
        MagicMock(__aenter__=AsyncMock(return_value=mock_resp_mode2), __aexit__=AsyncMock()),
        MagicMock(__aenter__=AsyncMock(return_value=mock_resp_ok), __aexit__=AsyncMock()),
    ]
    with patch("asyncio.sleep", new_callable=AsyncMock):
        assert await api.async_set_site_limits({"p_bess_inv_max_export_limit": 0}) is True
    mock_session.put.side_effect = None

    # 7. async_set_site_limits vid exception
    mock_session.put.side_effect = Exception("Connection error")
    assert await api.async_set_site_limits({"p_gcp_max_import_limit": 4500}) is False
    mock_session.put.side_effect = None

    # 8. async_get_site_limits success
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"p_gcp_max_import_limit": 4500})
    assert await api.async_get_site_limits() == {"p_gcp_max_import_limit": 4500}

    # 9. async_get_site_limits exception
    mock_session.get.side_effect = Exception("Get limits failed")
    assert await api.async_get_site_limits() is None


@pytest.mark.asyncio
async def test_sonnen_version_detection(sonnen_battery, mock_sonnen_api):
    """Testar att firmware-version detekteras och modern EMS aktiveras vid >= 1.35.14."""
    # 1. Version 1.35.14 aktiverar modern EMS
    mock_sonnen_api.async_get_software_version.return_value = "1.35.14"
    await sonnen_battery.async_init_version()
    assert sonnen_battery.software_version == "1.35.14"
    assert sonnen_battery.is_modern_ems is True

    # 2. Version 1.36.0 aktiverar modern EMS
    mock_sonnen_api.async_get_software_version.return_value = "1.36.0"
    await sonnen_battery.async_init_version()
    assert sonnen_battery.software_version == "1.36.0"
    assert sonnen_battery.is_modern_ems is True

    # 3. Äldre version (1.30.0) använder legacy
    mock_sonnen_api.async_get_software_version.return_value = "1.30.0"
    await sonnen_battery.async_init_version()
    assert sonnen_battery.software_version == "1.30.0"
    assert sonnen_battery.is_modern_ems is False

    # 4. Ingen version (None)
    mock_sonnen_api.async_get_software_version.return_value = None
    sonnen_battery._software_version = None
    sonnen_battery._is_modern_ems = False
    await sonnen_battery.async_init_version()
    assert sonnen_battery.software_version is None
    assert sonnen_battery.is_modern_ems is False

    # 5. Ogiltig version kraschar inte
    mock_sonnen_api.async_get_software_version.return_value = "invalid-version"
    await sonnen_battery.async_init_version()
    assert sonnen_battery.software_version == "invalid-version"


@pytest.mark.asyncio
async def test_sonnen_update_data_with_site_limits(sonnen_battery, mock_sonnen_api):
    """Testar att _async_update_data hämtar site limits om modern EMS är aktiv."""
    # Modern EMS
    mock_sonnen_api.async_get_software_version.return_value = "1.35.14"
    mock_sonnen_api.async_get_status.return_value = {"USOC": 65}
    mock_sonnen_api.async_get_site_limits.return_value = {"p_gcp_max_import_limit": 4500}

    data = await sonnen_battery._async_update_data()
    assert data["USOC"] == 65
    assert data["site_limits"] == {"p_gcp_max_import_limit": 4500}
    mock_sonnen_api.async_get_site_limits.assert_called_once()

    # Legacy mode
    mock_sonnen_api.async_get_site_limits.reset_mock()
    mock_sonnen_api.async_get_software_version.return_value = "1.30.0"
    mock_sonnen_api.async_get_status.return_value = {"USOC": 65}
    sonnen_battery._software_version = None
    sonnen_battery._is_modern_ems = False
    data = await sonnen_battery._async_update_data()
    assert "site_limits" not in data
    mock_sonnen_api.async_get_site_limits.assert_not_called()


@pytest.mark.asyncio
async def test_sonnen_apply_action_modern_ems(sonnen_battery, mock_sonnen_api):
    """Testar att modern EMS körs med PUT site/limits och förblir i Mode 2."""
    sonnen_battery._software_version = "1.35.14"
    sonnen_battery._is_modern_ems = True

    limits = {
        "duration": "PT90S",
        "p_gcp_max_import_limit": 4500,
        "p_gcp_max_export_limit": 0,
        "p_bess_inv_max_export_limit": 0,
        "p_bess_inv_max_import_limit": 3300,
    }

    result = await sonnen_battery.apply_action("HOLD", sonnen_site_limits=limits)
    assert result is True

    # Ska säkerställa Self-consumption (Mode 2)
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(2)
    # Ska anropa async_set_site_limits med uppgraderad duration (PT10M)
    expected_limits = dict(limits)
    expected_limits["duration"] = "PT10M"
    mock_sonnen_api.async_set_site_limits.assert_called_once_with(expected_limits)
    # Inga manuella setpoint-kommandon
    mock_sonnen_api.async_charge.assert_not_called()
    mock_sonnen_api.async_discharge.assert_not_called()


@pytest.mark.asyncio
async def test_sonnen_apply_action_modern_ems_failure_fallback(sonnen_battery, mock_sonnen_api):
    """Testar att fel vid sättande av site limits faller tillbaka på legacy-styrning."""
    sonnen_battery._software_version = "1.35.14"
    sonnen_battery._is_modern_ems = True
    mock_sonnen_api.async_set_site_limits.return_value = False

    limits = {"p_bess_inv_max_export_limit": 0}
    await sonnen_battery.apply_action("HOLD", sonnen_site_limits=limits)

    # Både mode 2 (först) och mode 1 (vid fallback) har anropats
    assert mock_sonnen_api.async_set_operating_mode.call_count == 2
    mock_sonnen_api.async_set_operating_mode.assert_called_with(1)
    mock_sonnen_api.async_charge.assert_called_with(0)
    mock_sonnen_api.async_discharge.assert_called_with(0)


@pytest.mark.asyncio
async def test_sonnen_apply_action_modern_ems_charge_and_discharge(sonnen_battery, mock_sonnen_api):
    """Testar att CHARGE och DISCHARGE alltid körs via manuellt läge (Mode 1) för aktivt nätutbyte."""
    sonnen_battery._software_version = "1.35.14"
    sonnen_battery._is_modern_ems = True

    limits = {"p_gcp_max_import_limit": 4500, "p_bess_inv_max_import_limit": 3300}

    # CHARGE ska aktivera Mode 1 och skicka laddning (ej Mode 2 / site limits)
    await sonnen_battery.apply_action("CHARGE", target_kw=3.0, sonnen_site_limits=limits)
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(1)
    mock_sonnen_api.async_charge.assert_called_once_with(3000)
    mock_sonnen_api.async_set_site_limits.assert_not_called()

    mock_sonnen_api.reset_mock()

    # DISCHARGE ska aktivera Mode 1 och skicka urladdning (ej Mode 2 / site limits)
    await sonnen_battery.apply_action("DISCHARGE", target_kw=2.5, sonnen_site_limits=limits)
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(1)
    mock_sonnen_api.async_discharge.assert_called_once_with(2500)
    mock_sonnen_api.async_set_site_limits.assert_not_called()


@pytest.mark.asyncio
async def test_sonnen_apply_action_reuses_last_site_limits_on_hold(sonnen_battery, mock_sonnen_api):
    """Testar att apply_action("HOLD") utan limits återanvänder senast sparade limits från molnet."""
    sonnen_battery._software_version = "1.35.14"
    sonnen_battery._is_modern_ems = True

    limits = {"p_bess_inv_max_export_limit": 0}
    await sonnen_battery.apply_action("HOLD", sonnen_site_limits=limits)
    mock_sonnen_api.reset_mock()

    # PeakGuard eller lokal automation anropar HOLD utan limits
    await sonnen_battery.apply_action("HOLD")
    # Ska fortfarande använda Mode 2 och de cachade gränserna
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(2)
    mock_sonnen_api.async_set_site_limits.assert_called_once()



@pytest.mark.asyncio
async def test_coordinator_sonnen_payload_and_site_limits():
    """Testar att coordinator skickar inverter_software_version och vidarebefordrar site_limits."""
    hass = MagicMock()
    config = {
        "api_key": "test_key",
        "api_url": "https://battery-optimizer.example.com",
        "battery_type": "sonnen",
    }

    mock_battery = MagicMock()
    mock_battery.software_version = "1.35.14"
    mock_battery.get_current_soc = AsyncMock(return_value=75.0)
    mock_battery.get_min_soc = AsyncMock(return_value=None)
    mock_battery.get_virtual_load = AsyncMock(return_value=None)
    mock_battery.get_calculated_consumption = AsyncMock(return_value=None)
    mock_battery.get_battery_power = AsyncMock(return_value=None)
    mock_battery.get_grid_power = AsyncMock(return_value=None)
    mock_battery.get_house_consumption = AsyncMock(return_value=None)
    mock_battery.get_status_text = AsyncMock(return_value=None)
    mock_battery.get_solar_power = AsyncMock(return_value=None)
    mock_battery.is_offgrid = AsyncMock(return_value=False)
    mock_battery.apply_action = AsyncMock()

    patch_factory = "custom_components.battery_optimizer_light_plus.coordinator.create_battery_api"
    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_factory, return_value=mock_battery), patch(patch_session) as mock_get_session:
        coordinator = BatteryOptimizerLightCoordinator(hass, config, version="1.0.0")
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={
            "action": "HOLD",
            "target_power_kw": 0.0,
            "sonnen_site_limits": {
                "p_bess_inv_max_export_limit": 0,
                "p_gcp_max_import_limit": 4500,
            }
        })

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": []})

        await coordinator._async_update_data()

        # Verifiera att inverter_software_version skickades med
        _, kwargs = mock_session.post.call_args
        payload = kwargs["json"]
        assert payload["inverter_brand"] == "sonnen"
        assert payload["inverter_software_version"] == "1.35.14"

        # Verifiera att sonnen_site_limits vidarebefordrades till apply_action
        mock_battery.apply_action.assert_called_once_with(
            "HOLD",
            0.0,
            sonnen_site_limits={
                "p_bess_inv_max_export_limit": 0,
                "p_gcp_max_import_limit": 4500,
            },
        )


@pytest.mark.asyncio
async def test_sonnen_apply_action_clears_export_limit_on_idle(sonnen_battery, mock_sonnen_api):
    """Testar Edge Case A: apply_action("IDLE") utan limits rensar p_bess_inv_max_export_limit."""
    sonnen_battery._software_version = "1.35.14"
    sonnen_battery._is_modern_ems = True

    # 1. Molnet skickar HOLD med exportspärr och GCP importgräns
    initial_limits = {
        "p_bess_inv_max_export_limit": 0,
        "p_gcp_max_import_limit": 4500,
    }
    await sonnen_battery.apply_action("HOLD", sonnen_site_limits=initial_limits)
    mock_sonnen_api.async_set_site_limits.assert_called_with({
        "p_bess_inv_max_export_limit": 0,
        "p_gcp_max_import_limit": 4500,
        "duration": "PT10M",
    })
    mock_sonnen_api.reset_mock()

    # 2. Lokalt anrop till IDLE utan limits (t.ex. CheckWatt släpper eller PeakGuard återställer)
    await sonnen_battery.apply_action("IDLE")
    mock_sonnen_api.async_set_operating_mode.assert_called_once_with(2)
    mock_sonnen_api.async_set_site_limits.assert_called_once()
    sent_limits = mock_sonnen_api.async_set_site_limits.call_args[0][0]

    # Exportspärren ska vara borttagen så batteriet kan ladda ur till huset
    assert "p_bess_inv_max_export_limit" not in sent_limits
    # GCP-begränsningen ska finnas kvar
    assert sent_limits.get("p_gcp_max_import_limit") == 4500
    assert sent_limits.get("duration") == "PT10M"


def _create_mock_battery(is_modern_ems: bool = True):
    mock = MagicMock()
    mock.is_modern_ems = is_modern_ems
    mock.software_version = "1.35.14" if is_modern_ems else "1.34.0"
    mock.get_current_soc = AsyncMock(return_value=50.0)
    mock.get_min_soc = AsyncMock(return_value=None)
    mock.get_virtual_load = AsyncMock(return_value=None)
    mock.get_calculated_consumption = AsyncMock(return_value=None)
    mock.get_battery_power = AsyncMock(return_value=None)
    mock.get_grid_power = AsyncMock(return_value=None)
    mock.get_house_consumption = AsyncMock(return_value=None)
    mock.get_status_text = AsyncMock(return_value=None)
    mock.get_solar_power = AsyncMock(return_value=None)
    mock.is_offgrid = AsyncMock(return_value=False)
    mock.apply_action = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_peak_guard_modern_ems_disables_solar_override():
    """Testar Edge Case B: PeakGuard aktiverar inte Solar Override under HOLD när is_modern_ems är aktivt."""
    hass = MagicMock()
    config = {
        "api_key": "test_key",
        "api_url": "https://battery-optimizer.example.com",
        "battery_type": "sonnen",
        "virtual_load_sensor": "sensor.husets_netto_last_virtuell",
        "peak_limit_sensor": "sensor.optimizer_light_peak_limit",
        "soc_sensor": "sensor.soc",
        "enable_solar_override": True,
    }
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": False,
        "peakguard_status": "Off",
    }

    mock_battery = _create_mock_battery(is_modern_ems=True)

    guard = PeakGuard(hass, config, coordinator, mock_battery)

    # Sensorer indikerar stor solexport (-500W)
    limit_state = MagicMock(state="5.0")
    load_state = MagicMock(state="-500")
    soc_state = MagicMock(state="50")

    def get_state(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None

    hass.states.get.side_effect = get_state

    # Kör update 1
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    assert guard._solar_override_trigger_start is not None

    # Snabbspola 35 sekunder
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Override ska förbli False pga is_modern_ems = True
    assert guard.is_solar_override is False
    # Batteriet ska inte ha tvingats till IDLE
    mock_battery.apply_action.assert_not_called()


@pytest.mark.asyncio
async def test_peak_guard_modern_ems_hold_violation_ignores_solar_charging():
    """Testar Edge Case C: PeakGuard under HOLD larmar inte vid sol-laddning (-2000W)
    för modern EMS men vid urladdning (+500W).
    """
    hass = MagicMock()
    config = {
        "api_key": "test_key",
        "api_url": "https://battery-optimizer.example.com",
        "battery_type": "sonnen",
        "virtual_load_sensor": "sensor.husets_netto_last_virtuell",
        "peak_limit_sensor": "sensor.optimizer_light_peak_limit",
        "soc_sensor": "sensor.soc",
        "battery_power_sensor": "sensor.battery_power",
    }
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    mock_battery = _create_mock_battery(is_modern_ems=True)

    guard = PeakGuard(hass, config, coordinator, mock_battery)

    limit_state = MagicMock(state="5.0")
    load_state = MagicMock(state="2000")
    soc_state = MagicMock(state="50")
    # Solen laddar batteriet med 2000W (negativ effekt)
    bat_charging_state = MagicMock(state="-2000")

    def get_state(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        if entity_id == "sensor.battery_power":
            return bat_charging_state
        return None

    hass.states.get.side_effect = get_state

    # 1. Kör uppdatering när batteriet sol-laddas (-2000 W) under HOLD
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    # Ska INTE trigga HOLD-överskridelse eller skicka kommando
    mock_battery.apply_action.assert_not_called()
    assert guard._hold_command_sent is False

    # 2. Nu ändras batterieffekten till +500W (aktiv urladdning till huset) under HOLD
    bat_discharging_state = MagicMock(state="500")

    def get_state_discharging(entity_id):
        if entity_id == "sensor.battery_power":
            return bat_discharging_state
        return get_state(entity_id)

    hass.states.get.side_effect = get_state_discharging

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    # Urladdning under HOLD är en överträdelse, ska skicka HOLD-kommando
    mock_battery.apply_action.assert_called_once_with("HOLD")
    assert guard._hold_command_sent is True



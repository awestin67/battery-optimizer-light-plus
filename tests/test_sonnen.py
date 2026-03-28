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
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.battery_optimizer_light_plus.battery_factory import create_battery_api
from custom_components.battery_optimizer_light_plus.batteries.sonnen.sonnen import SonnenBattery
from custom_components.battery_optimizer_light_plus.batteries.sonnen.api import SonnenAPI
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

    patch_api = "custom_components.battery_optimizer_light_plus.battery_factory.SonnenAPI"
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

    patch_api = "custom_components.battery_optimizer_light_plus.battery_factory.SonnenAPI"
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

@pytest.mark.asyncio
async def test_get_battery_power(sonnen_battery):
    """Testar att batterieffekt hämtas korrekt."""
    sonnen_battery.coordinator.data = {"Pac_total_W": -1500}
    power = await sonnen_battery.get_battery_power()
    assert power == -1500.0

    sonnen_battery.coordinator.data = {}
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

@pytest.mark.asyncio
async def test_get_status_text(sonnen_battery):
    """Testar att systemstatus hämtas korrekt."""
    sonnen_battery.coordinator.data = {"SystemStatus": "OnGrid"}
    status = await sonnen_battery.get_status_text()
    assert status == "OnGrid"

    sonnen_battery.coordinator.data = {}
    assert await sonnen_battery.get_status_text() is None

@pytest.mark.asyncio
async def test_sonnen_api_methods():
    """Testar att SonnenAPI sätter ihop och skickar korrekta HTTP-anrop."""
    mock_session = MagicMock()
    mock_response = AsyncMock()

    # aiohttp:s raise_for_status är synkron, så vi mockar den specifikt
    mock_response.raise_for_status = MagicMock()

    # Konfigurera mock_session att returnera mock_response när den anropas med 'async with'
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.put.return_value.__aenter__.return_value = mock_response
    mock_session.post.return_value.__aenter__.return_value = mock_response

    api = SonnenAPI("192.168.1.50", 80, "my-secret-token", mock_session)

    expected_headers = {"Auth-Token": "my-secret-token", "Content-Type": "application/json"}

    # 1. Test get_status
    mock_response.json.return_value = {"USOC": 50}
    status = await api.async_get_status()
    assert status == {"USOC": 50}
    mock_session.get.assert_called_once_with(
        "http://192.168.1.50:80/api/v2/status", headers=expected_headers
    )

    # 2. Test set_operating_mode
    assert await api.async_set_operating_mode(1) is True
    mock_session.put.assert_called_once_with(
        "http://192.168.1.50:80/api/v2/configurations", json={"EM_OperatingMode": "1"}, headers=expected_headers
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

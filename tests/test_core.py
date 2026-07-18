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

from unittest.mock import MagicMock
import datetime

import pytest  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402
from homeassistant.core import CoreState  # noqa: E402
from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator, UpdateFailed  # noqa: E402
from custom_components.battery_optimizer_light_plus import PeakGuard  # noqa: E402
from custom_components.battery_optimizer_light_plus import ( # noqa: E402
    async_setup_entry,
    async_unload_entry,
    update_listener,
)
from custom_components.battery_optimizer_light_plus.const import DOMAIN # noqa: E402
from custom_components.battery_optimizer_light_plus.sensor import BatteryLightStatusSensor  # noqa: E402
from custom_components.battery_optimizer_light_plus.sensor import BatteryLightVirtualLoadSensor  # noqa: E402

# --- MOCK DATA ---
MOCK_CONFIG = {
    "api_url": "http://test-api",
    "api_key": "12345",
    "soc_sensor": "sensor.soc",
    "grid_sensor": "sensor.grid",
    "battery_power_sensor": "sensor.bat_power",
    "virtual_load_sensor": "sensor.husets_netto_last_virtuell",
    "enable_solar_override": True,
}

@pytest.fixture
def mock_hass_instance():
    """Skapar en fejkad Home Assistant-instans."""
    hass = MagicMock()
    hass.data = {}
    hass.states.get = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    return hass

@pytest.fixture
def mock_battery():
    """Mockerar den nya Battery Controller Factoryn."""
    mock = MagicMock()
    mock.get_current_soc = AsyncMock(return_value=None)
    mock.get_virtual_load = AsyncMock(return_value=None)
    mock.get_calculated_consumption = AsyncMock(return_value=None)
    mock.get_battery_power = AsyncMock(return_value=None)
    mock.get_grid_power = AsyncMock(return_value=None)
    mock.get_house_consumption = AsyncMock(return_value=None)
    mock.get_status_text = AsyncMock(return_value=None)
    mock.apply_action = AsyncMock()
    mock.get_min_soc = AsyncMock(return_value=None)
    mock.get_solar_power = AsyncMock(return_value=None)
    return mock

@pytest.mark.asyncio
async def test_coordinator_handles_unavailable_soc(mock_hass_instance, mock_battery):
    """
    Krav: Om SoC är otillgänglig ska koordinatorn kasta ett fel och göra retries,
    och till slut släppa till IDLE och kasta UpdateFailed, för att inte
    förstöra molnets historik med falska nollor.
    """
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery

    # Mocka get_current_soc att returnera None
    mock_battery.get_current_soc.return_value = None

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_sleep = "custom_components.battery_optimizer_light_plus.coordinator.asyncio.sleep"
    with patch(patch_session) as mock_get_session, patch(patch_sleep) as mock_sleep:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator._async_update_data()

        # Ska ha försökt vänta 2 gånger (5s)
        assert mock_sleep.call_count == 2
        # Ska ha satt batteriet i IDLE
        mock_battery.apply_action.assert_called_with("IDLE")
        # Ska inte ha postat något till molnet
        mock_session.post.assert_not_called()
        assert "SoC" in str(excinfo.value)

@pytest.mark.asyncio
async def test_peak_guard_triggers_discharge(mock_hass_instance, mock_battery):
    """Krav: Om lasten är högre än gränsen ska batteriet urladdas."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Mocka _report_peak för att verifiera argument och undvika nätverksanrop
    guard._report_peak = AsyncMock()

    # Setup av sensorvärden
    # Gräns: 5 kW
    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Last: 7 kW (2 kW över gränsen)
    load_state = MagicMock()
    load_state.state = "7000"

    # SoC: 50% (Tillräckligt för att agera)
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör logiken
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att scriptet anropades
    # Behovet är 7000 - 5000 = 2000 W
    mock_battery.apply_action.assert_called_with("DISCHARGE", 2.0)

    # Verifiera att _report_peak anropades med (current_load, limit_w)
    guard._report_peak.assert_called_with(7000.0, 5000.0)

@pytest.mark.asyncio
async def test_peak_guard_respects_safe_limit(mock_hass_instance, mock_battery):
    """Krav: Om lasten är låg ska vi återgå till molnets plan (eller Auto)."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "IDLE",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)
    guard._has_reported = True # Låtsas att vi var i ett larm-läge

    # Mocka _report_peak_clear för att verifiera argument
    guard._report_peak_clear = AsyncMock()

    # Gräns: 5 kW, Safe limit blir 4 kW
    limit_state = MagicMock()
    limit_state.state = "5.0"
    # Last: 3 kW (Väl under safe limit)
    load_state = MagicMock()
    load_state.state = "3000"
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör logiken
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Eftersom molnet sa IDLE, ska vi anropa auto_mode
    mock_battery.apply_action.assert_called_with("IDLE")

    # Verifiera att _report_peak_clear anropades med (current_load, limit_w)
    guard._report_peak_clear.assert_called_with(3000.0, 5000.0)

@pytest.mark.asyncio
async def test_peak_guard_disabled_by_backend(mock_hass_instance, mock_battery):
    """Krav: Om backend säger att peak shaving är inaktivt ska inget hända."""
    coordinator = MagicMock()
    # is_peak_shaving_active = False
    coordinator.data = {"action": "HOLD", "is_active": True, "is_peak_shaving_active": False, "peakguard_status": "Off"}

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup sensor values that WOULD trigger a peak
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "7000" # 7kW > 5kW
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Run logic
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verify NO calls were made
    mock_battery.apply_action.assert_not_called()

@pytest.mark.asyncio
async def test_solar_override_works_when_peak_shaving_disabled(mock_hass_instance, mock_battery):
    """Krav: Solar Override ska fortfarande övervakas och fungera även om Peak Shaving inaktiverats från molnet."""
    coordinator = MagicMock()
    # Backend säger att peak shaving är Off (is_active blir False)
    coordinator.data = {"action": "HOLD", "is_active": True, "is_peak_shaving_active": False, "peakguard_status": "Off"}

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup sensorer för stor solexport (-500W)
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "-500"
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update 1 - timern ska starta trots att Peak Shaving är inaktivt
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is False
    assert guard._solar_override_trigger_start is not None

    # Spola fram tiden och kör update 2
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Override måste bli True, och skicka kommandot IDLE
    assert guard.is_solar_override is True
    mock_battery.apply_action.assert_called_with("IDLE")

def test_status_sensor():
    """Testar att status-sensorn visar rätt text (Disabled/Monitoring/Triggered)."""
    coordinator = MagicMock()
    coordinator.api_key = "12345"
    coordinator.data = {"is_active": True, "is_peak_shaving_active": True, "peakguard_status": "Active"}

    # Mocka peak_guard på coordinatorn
    peak_guard = MagicMock()
    peak_guard.is_active = False
    peak_guard.in_maintenance = False
    peak_guard.maintenance_reason = None
    peak_guard.is_solar_override = False
    coordinator.peak_guard = peak_guard

    sensor = BatteryLightStatusSensor(coordinator)

    # Fall 1: Monitoring (Aktiv men inte triggad)
    assert sensor.state == "Monitoring"
    assert sensor.icon == "mdi:shield-search"

    # Fall 2: Triggered
    peak_guard.is_active = True
    assert sensor.state == "Triggered"
    assert sensor.icon == "mdi:shield-alert"

    # Fall 3: Disabled
    coordinator.data = {"is_active": True, "is_peak_shaving_active": False, "peakguard_status": "Off"}
    peak_guard.is_active = False
    assert sensor.state == "Off"
    assert sensor.icon == "mdi:shield-off"

    # Fall 3b: Paused
    coordinator.data = {"is_active": True, "is_peak_shaving_active": False, "peakguard_status": "Paused"}
    assert sensor.state == "Paused"
    assert sensor.icon == "mdi:pause-circle-outline"

    # Fall 3c: Global optimerare avstängd (is_active=False men pg_status=Active)
    coordinator.data = {"is_active": False, "is_peak_shaving_active": False, "peakguard_status": "Active"}
    assert sensor.state == "Disabled"
    assert sensor.icon == "mdi:shield-off"

    # Fall 3d: Global optimerare helt avstängd (is_active i payload är False)
    coordinator.data = {"is_active": False}
    assert sensor.state == "Disabled"
    assert sensor.icon == "mdi:shield-off"

    # Fall 4: Maintenance
    coordinator.data = {"is_active": True, "is_peak_shaving_active": True, "peakguard_status": "Active"}
    peak_guard.is_active = False
    peak_guard.in_maintenance = True
    peak_guard.maintenance_reason = "Service Mode"
    assert sensor.state == "Maintenance mode detected (Service Mode). Pausing control."
    assert sensor.icon == "mdi:tools"

    # Fall 5: Solar Override
    peak_guard.in_maintenance = False
    peak_guard.is_solar_override = True
    assert sensor.state == "Solar Override Active"
    assert sensor.icon == "mdi:solar-panel"

@pytest.mark.asyncio
async def test_peak_guard_reports_failure_on_overload(mock_hass_instance, mock_battery):
    """Krav: Om behovet överstiger max växelriktareffekt ska failure rapporteras."""
    coordinator = MagicMock()
    # Sätt max_discharge_kw till 3.3 kW (3300 W)
    coordinator.data = {
        "action": "HOLD",
        "max_discharge_kw": 3.3,
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Vi simulerar att vi redan är i ett peak-läge (har rapporterat start)
    guard._has_reported = True

    # Mocka _report_peak_failure metoden för att verifiera anrop utan att göra nätverksanrop
    guard._report_peak_failure = AsyncMock()

    # Setup sensorvärden
    # Gräns: 5 kW
    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Last: 9 kW. Behov = 9000 - 5000 = 4000 W.
    # Max inverter = 3300 W.
    # 4000 > 3300 -> Failure.
    load_state = MagicMock()
    load_state.state = "9000"

    # SoC: 50%
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör logiken
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att _report_peak_failure anropades med (current_load, limit_w)
    guard._report_peak_failure.assert_called_with(9000.0, 5000.0)

@pytest.mark.asyncio
async def test_solar_override_reports_to_cloud(mock_hass_instance, mock_battery):
    """Krav: När Solar Override aktiveras ska det rapporteras till molnet."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Mocka rapport-metoden
    guard._report_solar_override = AsyncMock()

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Last: -500 W (Export)
    load_state = MagicMock()
    load_state.state = "-500"

    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att override inte triggats direkt (väntar på 30s)
    assert guard.is_solar_override is False

    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att override aktiverades och rapport skickades
    assert guard.is_solar_override is True
    guard._report_solar_override.assert_called_with(-500.0, 5000.0)

@pytest.mark.asyncio
async def test_coordinator_sends_solar_override_flag(mock_hass_instance):
    """Krav: Coordinator ska skicka med is_solar_override flaggan till backend."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG, version="1.2.3")

    # Mocka SoC state och last
    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.soc":
            mock_state.state = "50"
        elif entity_id == "sensor.husets_netto_last_virtuell":
            mock_state.state = "4500"
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    # Mocka PeakGuard och sätt override till True
    peak_guard = MagicMock()
    peak_guard.is_solar_override = True
    peak_guard.in_maintenance = False
    coordinator.peak_guard = peak_guard

    # Mocka aiohttp session och response
    # Vi patchar där den används: custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession
    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value
        mock_post.__aenter__.return_value = mock_post
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"status": "ok"})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()

        # Verifiera anropet
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']


        assert payload["is_solar_override"] is True
        assert payload["is_in_maintenance"] is False
        assert payload["soc"] == 50.0
        assert payload["ha_version"] == "1.2.3"
        assert payload["current_consumption_kw"] == 4.5

@pytest.mark.asyncio
async def test_coordinator_sends_solar_kw(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska hämta solproduktion och skicka med current_solar_kw till backend."""
    config = MOCK_CONFIG.copy()
    config["solar_sensor"] = "sensor.solar_production"
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")

    # Låtsas att batteriets interna sökning inte hittar solcellerna (så vi testar config-fallback)
    mock_battery.get_solar_power = AsyncMock(return_value=None)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.soc":
            mock_state.state = "50"
        elif entity_id == "sensor.solar_production":
            mock_state.state = "4200" # 4200 W solproduktion
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()

        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert "current_solar_kw" in payload
        assert payload["current_solar_kw"] == 4.2

@pytest.mark.asyncio
async def test_coordinator_solar_kw_value_error(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska hantera ValueError på sol-sensorn snyggt och exkludera fältet."""
    config = MOCK_CONFIG.copy()
    config["solar_sensor"] = "sensor.solar_production"
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")

    mock_battery.get_solar_power = AsyncMock(return_value=None)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.soc":
            mock_state.state = "50"
        elif entity_id == "sensor.solar_production":
            mock_state.state = "invalid_string" # Ogiltigt värde
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert "current_solar_kw" not in payload

@pytest.mark.asyncio
async def test_coordinator_solar_kw_clamps_negative(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska sätta negativa sol-värden till 0.0 kW."""
    config = MOCK_CONFIG.copy()
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")

    # Batteriet rapporterar in ett negativt sol-värde (brus/natt)
    mock_battery.get_solar_power = AsyncMock(return_value=-15.0)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert payload.get("current_solar_kw") == 0.0

@pytest.mark.asyncio
async def test_coordinator_excludes_solar_kw_if_missing(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska exkludera current_solar_kw om solproduktion saknas (både modbus och HA-sensor)."""
    config = MOCK_CONFIG.copy()
    config["solar_sensor"] = None
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")

    # Batteriet rapporterar in None (hittar inget värde)
    mock_battery.get_solar_power = AsyncMock(return_value=None)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.soc":
            mock_state.state = "50"
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert "current_solar_kw" not in payload

@pytest.mark.asyncio
async def test_coordinator_respects_hardware_reserve(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska skala SoC för molnet och avbryta DISCHARGE lokalt om SoC <= reserv."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)

    # Ta bort metoden från mocken just här så att testet beter sig exakt som ett Sonnen-batteri
    del mock_battery.get_min_soc

    coordinator.battery_api = mock_battery
    # Sätt fysisk SoC till 14.5%
    mock_battery.get_current_soc.return_value = 14.5

    # Mocka fram en EM_USOC (Backup-reserv) på 5%
    mock_battery.coordinator = MagicMock()
    mock_battery.coordinator.data = {"EM_USOC": "5"}

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        # Backend skickar DISCHARGE
        mock_post.json = AsyncMock(return_value={"action": "DISCHARGE", "target_power_kw": 2.0})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()

        # Verifiera att molnet fick den SKALADE SoC:n
        # (14.5 - 5) / (100 - 5) * 100 = 9.5 / 95 * 100 = 10.0%
        payload = mock_session.post.call_args[1]["json"]
        assert payload["soc"] == 10.0
        assert "hardware_reserve_soc" not in payload

        # Verifiera att DISCHARGE går igenom eftersom 14.5 > 5.0
        mock_battery.apply_action.assert_called_with("DISCHARGE", 2.0)

        # --- Test 2: Nå botten (SoC = 5.0%) ---
        mock_battery.get_current_soc.return_value = 5.0
        mock_battery.apply_action.reset_mock()

        await coordinator._async_update_data()

        payload2 = mock_session.post.call_args[1]["json"]
        assert payload2["soc"] == 0.0  # Skalad SoC ska bli 0.0%

        # Verifiera att action blev IDLE istället för DISCHARGE eftersom vi nått reserven
        mock_battery.apply_action.assert_called_with("IDLE", 2.0)

@pytest.mark.asyncio
async def test_coordinator_respects_generic_min_soc(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska skala SoC för Generic om min_soc är angivet i config."""
    config = MOCK_CONFIG.copy()
    config["min_soc"] = 20.0
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)

    del mock_battery.get_min_soc # Simulera Generic (har ej get_min_soc)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 60.0 # 60% fysisk

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()

        # (60 - 20) / (100 - 20) * 100 = 40 / 80 * 100 = 50.0%
        payload = mock_session.post.call_args[1]["json"]
        assert payload["soc"] == 50.0

@pytest.mark.asyncio
async def test_peak_guard_calculates_load_with_inverted_grid(mock_hass_instance, mock_battery):
    """Krav: Om grid_sensor_invert är True ska grid-värdet negeras vid beräkning."""
    # Konfiguration med inverterad grid sensor och INGEN virtuell sensor
    config = MOCK_CONFIG.copy()
    config["grid_sensor_invert"] = True
    config["virtual_load_sensor"] = None

    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Grid: 5000 W (Positivt). Med invert=True betyder detta Export (-5000 W).
    grid_state = MagicMock()
    grid_state.state = "5000"

    # Batteri: 0 W
    bat_state = MagicMock()
    bat_state.state = "0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.grid":
            return grid_state
        if entity_id == "sensor.bat_power":
            return bat_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update utan virtuell sensor-ID
    await guard.update(None, "sensor.optimizer_light_peak_limit")

    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update(None, "sensor.optimizer_light_peak_limit")

    # Om inverteringen fungerade är lasten -5000. -5000 < -200 -> Solar Override.
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_peak_guard_calculates_load_with_inverted_battery(mock_hass_instance, mock_battery):
    """Krav: Om battery_sensor_invert är True ska batterivärdet negeras vid beräkning."""
    config = MOCK_CONFIG.copy()
    config["battery_sensor_invert"] = True
    config["virtual_load_sensor"] = None

    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Grid: 0 W
    grid_state = MagicMock()
    grid_state.state = "0"

    # Batteri: -1500 W (Vilket pga invert=True betyder 1500 W Urladdning)
    bat_state = MagicMock()
    bat_state.state = "-1500"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.grid":
            return grid_state
        if entity_id == "sensor.bat_power":
            return bat_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update(None, "sensor.optimizer_light_peak_limit")

    # Lasten beräknas till 0 + (-(-1500)) = 1500.
    # 1500 > -400, så Solar Override ska INTE aktiveras.
    assert guard.is_solar_override is False

def test_virtual_load_sensor_calculation():
    """Testar att den virtuella lastsensorn räknar rätt."""
    coordinator = MagicMock()
    coordinator.api_key = "12345"
    coordinator.hass = MagicMock()

    # Mocka config via peak_guard
    peak_guard = MagicMock()
    peak_guard.config = {
        "grid_sensor": "sensor.grid",
        "battery_power_sensor": "sensor.bat",
        "grid_sensor_invert": False,
        "virtual_load_sensor": None
    }
    coordinator.peak_guard = peak_guard

    sensor = BatteryLightVirtualLoadSensor(coordinator)

    # Mocka states
    grid_state = MagicMock()
    grid_state.state = "5000"
    bat_state = MagicMock()
    bat_state.state = "1000"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.grid":
            return grid_state
        if entity_id == "sensor.bat":
            return bat_state
        return None
    coordinator.hass.states.get.side_effect = get_state_side_effect

    # Fall 1: Normal beräkning (5000 + 1000 = 6000)
    assert sensor.state == 6000

    # Fall 2: Inverterad grid
    peak_guard.config["grid_sensor_invert"] = True
    # (-5000 + 1000 = -4000)
    assert sensor.state == -4000

@pytest.mark.asyncio
async def test_peak_guard_solar_override_hysteresis(mock_hass_instance, mock_battery):
    """Krav: Solar Override ska ha hysteres för att undvika 'flapping' vid gränsvärdet."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Mocka sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"
    soc_state = MagicMock()
    soc_state.state = "50"

    # Helper för att simulera last-ändringar
    async def set_load(load_w):
        load_state = MagicMock()
        load_state.state = str(load_w)

        def get_state_side_effect(entity_id):
            if entity_id == "sensor.optimizer_light_peak_limit":
                return limit_state
            if entity_id == "sensor.husets_netto_last_virtuell":
                return load_state
            if entity_id == "sensor.soc":
                return soc_state
            return None
        mock_hass_instance.states.get.side_effect = get_state_side_effect

        await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # 1. Trigga Override (Last < -400, t.ex. -450)
    await set_load(-450)
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await set_load(-450)
    assert guard.is_solar_override is True

    # 2. Minska exporten till -200 (Fortfarande export, men över trigg-gränsen -400)
    # Utan hysteres skulle denna stängas av här och orsaka flapping.
    await set_load(-200)
    assert guard.is_solar_override is True

    # 3. Gå över reset-gränsen (t.ex. -100) för att stänga av
    await set_load(-50)
    # På grund av den nya "fladder"-spärren ska den ligga kvar i 3 minuter
    assert guard.is_solar_override is True
    assert guard._solar_override_clear_start is not None

    guard._solar_override_clear_start -= datetime.timedelta(minutes=3, seconds=5)
    await set_load(-50)
    assert guard.is_solar_override is False

@pytest.mark.asyncio
async def test_peak_guard_solar_override_clear_delay(mock_hass_instance, mock_battery):
    """Krav: Solar Override ska ha en 3-minuters fördröjning vid avstängning för att undvika fladder."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # 1. Trigga Override (Last < -400)
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "-500"
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    assert guard.is_solar_override is True

    # 2. Simulera en storförbrukare (Last > -100)
    load_state.state = "1000"
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # 3. Direkt avstängning ska INTE ske!
    assert guard.is_solar_override is True
    assert guard._solar_override_clear_start is not None

    # 4. Spola fram tiden > 3 minuter
    guard._solar_override_clear_start -= datetime.timedelta(minutes=3, seconds=5)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # 5. Nu ska den stängas av
    assert guard.is_solar_override is False

@pytest.mark.asyncio
async def test_peak_guard_bypasses_delay_when_discharging(mock_hass_instance, mock_battery):
    """Krav: Om batteriet börjar ladda ur under Solar Override, avbryt direkt för att skydda SoC."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # 1. Trigga Override (Last < -400)
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "-500"
    soc_state = MagicMock()
    soc_state.state = "50"
    bat_state = MagicMock()
    bat_state.state = "0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        if entity_id == "sensor.bat_power":
            return bat_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is True

    # 2. Simulera att moln går i moln och batteriet börjar ladda ur (t.ex. 300W urladdning)
    load_state.state = "500"
    bat_state.state = "300"
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # 3. Direkt avstängning SKA ske, utan 3 minuters fördröjning!
    assert guard.is_solar_override is False

@pytest.mark.asyncio
async def test_peak_guard_pauses_on_custom_keyword(mock_hass_instance, mock_battery):
    """Krav: Användaren ska kunna konfigurera egna nyckelord för underhåll."""
    config = MOCK_CONFIG.copy()
    config["battery_status_sensor"] = "sensor.generic_battery_status"
    # Konfigurera ett eget nyckelord
    config["battery_status_keywords"] = "service mode, critical error"

    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Status: "Service Mode" (matchar vårt egna nyckelord)
    status_state = MagicMock()
    status_state.state = "System is in Service Mode"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.generic_battery_status":
            return status_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update(None, "sensor.optimizer_light_peak_limit")

    # Verifiera att flaggan sattes
    assert guard._in_maintenance is True

@pytest.mark.asyncio
async def test_peak_guard_pauses_on_external_control_sensor(mock_hass_instance, mock_battery):
    """Krav: Om external_control_sensor är 'on' ska PeakGuard pausa systemet direkt (t.ex. CheckWatt)."""
    config = MOCK_CONFIG.copy()
    config["external_control_sensor"] = "input_boolean.checkwatt_active"

    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    limit_state = MagicMock()
    limit_state.state = "5.0"

    # Sensorn för CheckWatt är på!
    external_state = MagicMock()
    external_state.state = "on"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "input_boolean.checkwatt_active":
            return external_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update(None, "sensor.optimizer_light_peak_limit")

    # Verifiera att PeakGuard gick in i underhållsläge och släppte batteriet till IDLE
    assert guard._in_maintenance is True
    assert guard._maintenance_reason == "External Control Active"
    mock_battery.apply_action.assert_called_with("IDLE")

@pytest.mark.asyncio
async def test_peak_guard_stops_at_zero_soc(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska sluta urladda när SoC når 0%."""
    coordinator = MagicMock()
    coordinator.data = {
        "cloud_action": "HOLD",
        "cloud_target_power_kw": 0.0,
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)
    guard._has_reported = True # Vi simulerar att PeakGuard redan är aktivt

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0" # 5 kW gräns

    load_state = MagicMock()
    load_state.state = "7000" # 7 kW last (behöver urladdning)

    # Fall 1: SoC = 1% -> Ska fortsätta urladda
    soc_state = MagicMock()
    soc_state.state = "1"

    # Batteriet står stilla just nu
    bat_state = MagicMock()
    bat_state.state = "0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        if entity_id == "sensor.bat_power":
            return bat_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update (SoC 1%)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att vi urladdar (7000 - 5000 = 2000)
    mock_battery.apply_action.assert_called_with("DISCHARGE", 2.0)

    # Återställ mock
    mock_battery.apply_action.reset_mock()

    # Fall 2: SoC = 0% -> Ska sluta tvinga urladdning
    soc_state.state = "0"

    # Simulera att batteriet fortfarande laddar ur (eftersom vi tvingade det nyss)
    bat_state.state = "2000"

    # Kör update (SoC 0%)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Nu ska den skicka HOLD (force_charge 0) eftersom vi faller ur if-satsen (soc > 0 är False)
    # och hamnar i else-satsen där molnet säger HOLD.
    mock_battery.apply_action.assert_called_with("HOLD")

@pytest.mark.asyncio
async def test_peak_guard_throttles_charge(mock_hass_instance, mock_battery):
    """Krav: Om molnet vill ladda men lasten är hög, ska laddningen strypas."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "CHARGE",
        "target_power_kw": 3.0,
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0" # 5000W

    load_state = MagicMock()
    load_state.state = "4000" # 4000W House Load

    # SoC spelar ingen roll här, men vi sätter den
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Available = 5000 - 4000 - 200 (marginal) = 800W.
    # Target = 3000W.
    # Should throttle to 800W.
    mock_battery.apply_action.assert_called_with("CHARGE", 0.8)

@pytest.mark.asyncio
async def test_peak_guard_sticky_solar_override_on_idle(mock_hass_instance, mock_battery):
    """Krav: Om Solar Override är aktiv och molnet svarar IDLE, ska override ligga kvar."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "IDLE",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Simulera att vi redan är i Solar Override
    guard._is_solar_override = True

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"
    soc_state = MagicMock()
    soc_state.state = "50"

    # Last: -200 W (Export, men inte tillräckligt för att trigga nytt (-400),
    # men tillräckligt för att ligga kvar (< -100)).
    load_state = MagicMock()
    load_state.state = "-200"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att override ligger kvar (Sticky)
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_peak_guard_forces_idle_on_solar_override_after_stale_idle(mock_hass_instance, mock_battery):
    """Krav: När Solar Override aktiveras MÅSTE den skicka IDLE, även om den tror att IDLE redan var skickat."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # 1. Simulera att PeakGuard tidigare har skickat IDLE och sedan inte uppdaterat sin state
    # (Händer när Coordinator skickar HOLD utan PeakGuards inblandning pga bat_power < 100)
    guard._last_sent_command = "IDLE"

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "-500" # Hög export
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Trigga timern och snabbspola
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    assert guard.is_solar_override is True
    mock_battery.apply_action.assert_called_with("IDLE")

@pytest.mark.asyncio
async def test_peak_guard_handles_high_export_as_solar_override(mock_hass_instance, mock_battery):
    """Krav: Vid hög export ska Solar Override aktiveras (inte blockeras)."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0" # 5000W limit

    # Last: -6000 W (Export > Limit)
    load_state = MagicMock()
    load_state.state = "-6000"

    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att PeakGuard INTE är aktiv (ingen urladdning)
    assert guard.is_active is False
    # Verifiera att Solar Override ÄR aktiv (tillåt laddning)
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_peak_guard_solar_override_disabled_in_config(mock_hass_instance, mock_battery):
    """Krav: Om enable_solar_override är False i config ska Solar Override aldrig triggas."""
    config = MOCK_CONFIG.copy()
    config["enable_solar_override"] = False

    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "-6000"
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Timern ska inte ha startat och flaggan ska vara False
    assert guard.is_solar_override is False
    assert guard._solar_override_trigger_start is None

@pytest.mark.asyncio
async def test_peak_guard_prevents_solar_override_during_buffer_fill_lag(mock_hass_instance, mock_battery):
    """
    Krav: När batteriet laddas från nätet (Buffer Fill) kan sensor-lag göra att
    vi ser en falsk export (Grid sjunker innan Batteri hinner rapportera lasten).

    Scenario:
    - Batteri laddar 3000W (Visas som -3000W).
    - Grid levererar 3000W, men laggar och visar bara 2500W Import just nu.
    - Virtuell last = 2500 + (-3000) = -500W.
    - -500W < -400W (Solar Trigger).

    Utan fixen hade detta aktiverat Solar Override.
    Med fixen ska vi se att Grid Import > 100W och blockera det.
    """
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup sensorer
    limit_state = MagicMock()
    limit_state.state = "5.0"

    soc_state = MagicMock()
    soc_state.state = "15" # Låg SoC, därför vi buffrar

    # Grid: 2500 W Import (Positivt). > 100W spärren.
    grid_state = MagicMock()
    grid_state.state = "2500"

    # Batteri: -3000 W (Laddar)
    bat_state = MagicMock()
    bat_state.state = "-3000"

    # Virtuell Last: -500 W (Falsk export pga lag)
    load_state = MagicMock()
    load_state.state = "-500"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.grid":
            return grid_state
        if entity_id == "sensor.bat_power":
            return bat_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    if guard._solar_override_trigger_start:
        guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att Solar Override INTE aktiveras, trots att lasten är -500W
    # Detta bevisar att "Import-spärren" fungerar.
    assert guard.is_solar_override is False

@pytest.mark.asyncio
async def test_peak_guard_prioritizes_ha_sensors_over_internal_api(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska prioritera manuellt konfigurerade HA-sensorer framför interna batterimetoder."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    config = MOCK_CONFIG.copy()

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    # Mocka interna batterimetoder till att indikera IMPORT (Skulle normalt blockera Solar Override)
    mock_battery.get_virtual_load.return_value = 5000.0  # Import
    mock_battery.get_grid_power.return_value = 5000.0    # Grid importerar
    mock_battery.get_battery_power.return_value = 0.0     # Batteriet är stilla
    mock_battery.get_current_soc.return_value = 50.0

    # Skapa riktiga HA-sensorer som indikerar extrem EXPORT
    good_state = MagicMock()
    good_state.state = "-4581"
    limit_state = MagicMock()
    limit_state.state = "5.0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        return good_state # Alla andra (grid, bat, load) ger export-värdet "-4581"

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Första körningen: Systemet ser -4581W export från HA-sensorer och startar timern
    # (struntar i interna API:ets "5000W")
    await guard.update(config.get("virtual_load_sensor"), "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is False

    assert guard._solar_override_trigger_start is not None, (
        "Timern startade inte! HA-sensorerna ignorerades till förmån för interna metoder."
    )

    # Snabbspola tiden förbi 30 sekunder
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)

    # Andra körningen: Nu har tiden gått, override ska aktiveras!
    await guard.update(config.get("virtual_load_sensor"), "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_coordinator_scheduling_and_cleanup(mock_hass_instance):
    """
    Krav: Koordinatorn ska schemalägga uppdateringar med async_track_time_interval
    och städa upp lyssnaren korrekt vid unload.
    """
    entry = MagicMock()
    entry.data = MOCK_CONFIG.copy()
    entry.entry_id = "test_scheduling"

    # Mocka bort factoryn så vi inte behöver bry oss om batteri-API:et
    patch_factory = "custom_components.battery_optimizer_light_plus.coordinator.create_battery_api"
    # Vi måste patcha den globala timern i __init__.py också
    patch_track_init = "custom_components.battery_optimizer_light_plus.async_track_state_change_event"
    # Och den vi vill testa i coordinator.py
    patch_track_coord = "custom_components.battery_optimizer_light_plus.coordinator.async_track_time_change"

    with patch(patch_factory), patch(patch_track_init), patch(patch_track_coord) as mock_track_change:

        # Skapa en mock för unsub-funktionen som returneras av timern
        mock_unsub = MagicMock()
        mock_track_change.return_value = mock_unsub

        # Mocka bort beroenden i setup
        mock_hass_instance.config_entries.async_forward_entry_setups = AsyncMock()
        patch_get_int = "custom_components.battery_optimizer_light_plus.async_get_integration"
        with patch(patch_get_int, new_callable=AsyncMock) as mock_get_int:
            mock_get_int.return_value = MagicMock(version="1.0.0")
            # Kör setup, detta kommer att skapa vår coordinator
            await async_setup_entry(mock_hass_instance, entry)

        # 1. Verifiera att timern sattes upp korrekt
        coordinator = mock_hass_instance.data[DOMAIN][entry.entry_id]
        assert mock_track_change.call_count == 2
        args, kwargs = mock_track_change.call_args_list[0]

        # args[0] är hass, args[1] är callback
        callback = args[1]
        assert kwargs["minute"] == list(range(0, 60, 5))
        assert kwargs["second"] == 30

        # Verifiera att wrappern anropar async_request_refresh
        coordinator.async_request_refresh = AsyncMock()
        await callback(datetime.datetime.now(datetime.timezone.utc))
        coordinator.async_request_refresh.assert_called_once()


        # 2. Verifiera att unload städar upp
        mock_hass_instance.config_entries.async_unload_platforms.return_value = True
        await async_unload_entry(mock_hass_instance, entry)

        # unsub_timer() ska ha anropats för båda timers
        assert mock_unsub.call_count == 2

@pytest.mark.asyncio
async def test_peak_guard_fallback_to_ha_sensors(mock_hass_instance):
    """Krav: Om batteriet saknar interna metoder (Huawei/Generic), ska HA-sensorer användas."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    # Skapa en klass som representerar Huawei/Generic (saknar get_virtual_load osv)
    class DummyGenericBattery:
        async def apply_action(self, action, target_kw=0):
            pass
        async def get_current_soc(self):
            return 50.0
        # get_virtual_load, get_grid_power och get_battery_power SAKNAS med flit.

    dummy_battery = DummyGenericBattery()

    # Konfiguration som tvingar PeakGuard att räkna Grid + Batteri manuellt
    config = MOCK_CONFIG.copy()
    config["virtual_load_sensor"] = None

    guard = PeakGuard(mock_hass_instance, config, coordinator, dummy_battery)

    # Setup HA-sensorer: Grid exporterar 4500W, Batteriet är stilla
    limit_state = MagicMock()
    limit_state.state = "5.0"
    grid_state = MagicMock()
    grid_state.state = "-4500" # Export enligt branschstandard
    bat_state = MagicMock()
    bat_state.state = "0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.grid":
            return grid_state
        if entity_id == "sensor.bat_power":
            return bat_state
        return None

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör update första gången
    await guard.update(None, "sensor.optimizer_light_peak_limit")
    assert guard._solar_override_trigger_start is not None, "Timern startade inte via HA-sensorer!"

    # Snabbspola och verifiera aktivering
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)
    await guard.update(None, "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_coordinator_auth_failure(mock_hass_instance, mock_battery):
    """Krav: Om API-nyckeln är fel (401) ska ett tydligt fel kastas direkt utan retries."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value
        mock_post.__aenter__.return_value = mock_post
        mock_post.status = 401
        mock_post.text = AsyncMock(return_value="Invalid API Key")

        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator._async_update_data()

        assert "Authentication failed" in str(excinfo.value)
        # Verifiera att den avbröt direkt och inte gjorde 3 försök
        assert mock_session.post.call_count == 1

@pytest.mark.asyncio
async def test_coordinator_retry_success(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska göra 3 försök. Om den lyckas på andra försöket ska den returnera datan."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_sleep = "custom_components.battery_optimizer_light_plus.coordinator.asyncio.sleep"

    with patch(patch_target) as mock_get_session, patch(patch_sleep) as mock_sleep:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Första anropet: Fel 500
        mock_fail = MagicMock()
        mock_fail.__aenter__.return_value = mock_fail
        mock_fail.status = 500
        mock_fail.text = AsyncMock(return_value="Server Error")

        # Andra anropet: OK 200
        mock_success = MagicMock()
        mock_success.__aenter__.return_value = mock_success
        mock_success.status = 200
        mock_success.json = AsyncMock(return_value={"action": "CHARGE", "target_power_kw": 5.0})

        mock_session.post.side_effect = [mock_fail, mock_success]

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        data = await coordinator._async_update_data()

        assert data["action"] == "CHARGE"
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once_with(5)

@pytest.mark.asyncio
async def test_coordinator_total_failure(mock_hass_instance, mock_battery):
    """Krav: Efter 3 misslyckade försök ska UpdateFailed kastas."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_sleep = "custom_components.battery_optimizer_light_plus.coordinator.asyncio.sleep"

    with patch(patch_target) as mock_get_session, patch(patch_sleep) as mock_sleep:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_fail = MagicMock()
        mock_fail.__aenter__.return_value = mock_fail
        mock_fail.status = 500
        mock_fail.text = AsyncMock(return_value="Server Error")

        mock_session.post.return_value = mock_fail

        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator._async_update_data()

        assert mock_session.post.call_count == 3
        assert mock_sleep.call_count == 2
        assert "Update error after 3 attempts" in str(excinfo.value)
        mock_battery.apply_action.assert_called_with("IDLE")

@pytest.mark.asyncio
async def test_lifecycle_and_services(mock_hass_instance):
    """Testar setup, migrering, registrering av tjänster, unload och reload."""
    entry = MagicMock()
    entry.data = MOCK_CONFIG.copy()
    entry.entry_id = "test_id"

    patch_int = "custom_components.battery_optimizer_light_plus.async_get_integration"
    patch_coord = "custom_components.battery_optimizer_light_plus.BatteryOptimizerLightCoordinator"
    patch_guard = "custom_components.battery_optimizer_light_plus.PeakGuard"
    patch_track = "custom_components.battery_optimizer_light_plus.async_track_state_change_event"

    with patch(patch_int, new_callable=AsyncMock) as mock_get_int, patch(patch_coord) as mock_coord_class, \
         patch(patch_guard) as mock_guard_class, patch(patch_track) as mock_track:

        mock_int = MagicMock()
        mock_int.version = "1.0.0"
        mock_get_int.return_value = mock_int

        mock_coord = mock_coord_class.return_value
        mock_coord.async_config_entry_first_refresh = AsyncMock()
        mock_coord.battery_api = MagicMock()
        mock_coord.battery_api.coordinator = MagicMock()
        mock_coord.battery_api.apply_action = AsyncMock()
        mock_guard = mock_guard_class.return_value
        mock_guard.update = AsyncMock()

        # Test setup
        assert await async_setup_entry(mock_hass_instance, entry) is True

        # Verifiera att background tracker sattes upp och kör dess on_load_change
        mock_track.assert_called_once()
        on_load_change = mock_track.call_args[0][2]
        mock_hass_instance.state = CoreState.running # Låtsas att HA är 'running'
        await on_load_change(None)
        mock_guard.update.assert_called()

        # Verifiera tjänster (services)
        assert mock_hass_instance.services.async_register.call_count == 2
        services = {call[0][1]: call[0][2] for call in mock_hass_instance.services.async_register.call_args_list}

        await services["run_peak_guard"](MagicMock(data={"virtual_load_entity": "v", "limit_entity": "l"}))
        mock_guard.update.assert_called_with("v", "l")

        # Test unload
        mock_hass_instance.config_entries.async_unload_platforms.return_value = True
        assert await async_unload_entry(mock_hass_instance, entry) is True

        # Test update listener
        await update_listener(mock_hass_instance, entry)
        mock_hass_instance.config_entries.async_reload.assert_called_once_with("test_id")

@pytest.mark.asyncio
async def test_setup_sonnen_listener(mock_hass_instance):
    """Testar att Sonnen får sin lokala polling uppsatt och kopplad till PeakGuard."""
    entry = MagicMock()
    entry.data = MOCK_CONFIG.copy()
    entry.data["battery_type"] = "sonnen"
    entry.entry_id = "test_sonnen"

    patch_int = "custom_components.battery_optimizer_light_plus.async_get_integration"
    patch_coord = "custom_components.battery_optimizer_light_plus.BatteryOptimizerLightCoordinator"
    with patch(patch_int, new_callable=AsyncMock) as mock_get_int, patch(patch_coord) as mock_coord_class:
        mock_get_int.return_value = MagicMock()
        mock_coord = mock_coord_class.return_value
        mock_coord.async_config_entry_first_refresh = AsyncMock()
        mock_coord.battery_api.coordinator = MagicMock()
        mock_coord.battery_api.coordinator.async_config_entry_first_refresh = AsyncMock()

        await async_setup_entry(mock_hass_instance, entry)

        # Verifiera att listener lades till och anropa den
        mock_coord.battery_api.coordinator.async_add_listener.assert_called_once()
        callback_func = mock_coord.battery_api.coordinator.async_add_listener.call_args[0][0]
        callback_func()
        mock_hass_instance.async_create_task.assert_called_once()

@pytest.mark.asyncio
async def test_peakguard_reporting_methods(mock_hass_instance, mock_battery):
    """Testar de interna HTTP-anropen för _report_* metoderna."""
    coordinator = MagicMock()
    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    patch_target = "custom_components.battery_optimizer_light_plus.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.post.return_value.__aenter__.return_value = mock_response

        await guard._report_peak(5000, 4000)
        await guard._report_peak_clear(3000, 4000)
        await guard._report_peak_failure(7000, 4000)
        await guard._report_solar_override(-500, 4000)
        await guard._report_solar_override_clear(-100, 4000)

        assert mock_session.post.call_count == 5

@pytest.mark.asyncio
async def test_peak_guard_update_exception(mock_hass_instance, mock_battery):
    """Testar den breda except-satsen i PeakGuard.update för att säkerställa att den inte kraschar."""
    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, MagicMock(), mock_battery)
    mock_hass_instance.states.get.side_effect = Exception("Simulerad krasch")
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")


@pytest.mark.asyncio
async def test_huawei_battery_apply_action_hold():
    """Krav: Huawei HOLD ska sätta max urladdning till 0 och stoppa forcible charge."""
    from custom_components.battery_optimizer_light_plus.batteries.huawei.huawei import HuaweiBattery

    mock_hass = MagicMock()
    mock_hass.services.async_call = AsyncMock()

    battery = HuaweiBattery(
        hass=mock_hass,
        device_id="huawei_inv_1",
        soc_entity="sensor.soc",
    )

    with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_get, \
             patch("homeassistant.helpers.entity_registry.async_entries_for_device") as mock_entries, \
             patch.object(battery, "_get_related_devices", return_value={"huawei_inv_1"}):
        mock_registry = MagicMock()
        mock_er_get.return_value = mock_registry

        mock_entry = MagicMock()
        mock_entry.domain = "number"
        mock_entry.translation_key = "maximum_discharging_power"
        mock_entry.entity_id = "number.battery_max_discharge"
        mock_entries.return_value = [mock_entry]

        mock_state = MagicMock()
        mock_state.state = "5000"
        mock_hass.states.get.return_value = mock_state

        await battery.apply_action("HOLD")

        # Verifiera att rätt anrop gjordes för att "pausa" batteriet
        mock_hass.services.async_call.assert_any_call(
            "number",
            "set_value",
            {"entity_id": "number.battery_max_discharge", "value": 0},
            blocking=True,
        )
        mock_hass.services.async_call.assert_any_call(
            "huawei_solar",
            "stop_forcible_charge",
            {"device_id": "huawei_inv_1"},
            blocking=True,
        )

@pytest.mark.asyncio
async def test_huawei_battery_apply_action_idle():
    """Krav: Huawei IDLE ska släppa spärren med stop_forcible_charge."""
    from custom_components.battery_optimizer_light_plus.batteries.huawei.huawei import HuaweiBattery

    mock_hass = MagicMock()
    mock_hass.services.async_call = AsyncMock()

    battery = HuaweiBattery(
        hass=mock_hass,
        device_id="huawei_inv_1",
        soc_entity="sensor.soc",
    )

    with patch.object(battery, "_get_related_devices", return_value={"huawei_inv_1"}):
        await battery.apply_action("IDLE")

    mock_hass.services.async_call.assert_called_once_with(
        "huawei_solar", "stop_forcible_charge", {"device_id": "huawei_inv_1"}, blocking=True
    )

@pytest.mark.asyncio
async def test_end_to_end_power_conversion(mock_hass_instance):
    """Krav: Säkerställ att molnets target_power_kw översätts korrekt till Watt för Huawei och Homevolt."""
    from custom_components.battery_optimizer_light_plus.batteries.huawei.huawei import HuaweiBattery
    from custom_components.battery_optimizer_light_plus.batteries.homevolt.homevolt import HomevoltBattery

    # --- 1. Testa Huawei ---
    huawei = HuaweiBattery(mock_hass_instance, "huawei_1", "sensor.soc")
    mock_hass_instance.services.async_call.reset_mock()

    with patch.object(huawei, "_get_related_devices", return_value={"huawei_1"}):
        await huawei.apply_action("CHARGE", target_kw=3.5)

    huawei_call = mock_hass_instance.services.async_call.call_args_list[0]
    assert huawei_call[0][0] == "huawei_solar"
    assert huawei_call[0][1] == "forcible_charge"
    assert huawei_call[0][2]["power"] == 3500, "3.5 kW ska översättas till 3500 W för Huawei"

    # --- 2. Testa Homevolt ---
    homevolt = HomevoltBattery(
        mock_hass_instance, "homevolt_1", "sensor.soc", None, "sensor.bat", None, None
    )
    mock_hass_instance.services.async_call.reset_mock()

    await homevolt.apply_action("DISCHARGE", target_kw=2.2)

    homevolt_call = mock_hass_instance.services.async_call.call_args_list[0]
    assert homevolt_call[0][0] == "homevolt_local"
    assert homevolt_call[0][1] == "add_schedule"
    assert homevolt_call[0][2]["setpoint"] == 2200, "2.2 kW ska översättas till 2200 W för Homevolt"
    assert homevolt_call[0][2]["mode"] == "2", "DISCHARGE ska sätta mode '2' för Homevolt"

@pytest.mark.asyncio
async def test_coordinator_graph_data_fetch(mock_hass_instance, mock_battery):
    """Testar att koordinatorn hämtar grafdata och lägger den i coordinator.data."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mocka post-anropet (/signal)
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        # Mocka get-anropet (/ha_graph_data)
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={
            "history": [{"timestamp": "2026-04-13T10:00:00Z", "savings_sek": 5.0, "current_solar_kw": 2.5}],
            "forecast": [{"timestamp": "2026-04-13T12:00:00Z", "soc": 40.0}]
        })

        data = await coordinator._async_update_data()

        # Verifiera att datan hamnade rätt
        assert "graph_data" in data
        assert len(data["graph_data"]["history"]) == 1
        assert data["graph_data"]["history"][0]["savings_sek"] == 5.0
        # Verifiera normalisering av current_solar_kw till solar_kw
        assert "current_solar_kw" not in data["graph_data"]["history"][0]
        assert data["graph_data"]["history"][0]["solar_kw"] == 2.5

def test_graph_data_sensor():
    """Testar att graf-sensorn returnerar attributen som förväntat."""
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightGraphDataSensor
    coordinator = MagicMock()
    coordinator.config = {"api_key": "test_key"}
    coordinator.data = {
        "last_update_time": "2026-04-18T07:12:00+00:00",
        "graph_data": {
            "history": [{"timestamp": "1", "val": 1}],
            "forecast": [{"timestamp": "2", "val": 2}]
        }
    }

    sensor = BatteryLightGraphDataSensor(coordinator)
    assert sensor.state == "OK"
    assert sensor.extra_state_attributes["last_update_time"] == "2026-04-18T07:12:00+00:00"

    # Test utan data
    coordinator.data = None
    assert sensor.state == "Waiting for data"
    assert sensor.extra_state_attributes == {}

@patch("custom_components.battery_optimizer_light_plus.sensor.dt_util")
def test_daily_savings_sensor(mock_dt_util):
    """Testar att dagliga besparingar summeras korrekt utifrån historiken."""
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightDailySavingsSensor
    coordinator = MagicMock()
    coordinator.api_key = "test_key"

    today = datetime.datetime(2026, 4, 13, 12, 0, 0, tzinfo=datetime.timezone.utc)
    yesterday = today - datetime.timedelta(days=1)

    mock_dt_util.now.return_value = today

    def mock_parse(ts):
        if not ts:
            return None
        try:
            return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except Exception:
            return None

    mock_dt_util.parse_datetime.side_effect = mock_parse
    mock_dt_util.as_local.side_effect = lambda dt: dt

    coordinator.data = {
        "graph_data": {
            "history": [
                {"timestamp": yesterday.isoformat(), "savings_sek": 5.0},
                {"timestamp": today.isoformat(), "savings_sek": 10.5},
                {"timestamp": (today + datetime.timedelta(hours=1)).isoformat(), "savings_sek": 15.0},
                {"timestamp": None, "savings_sek": 100.0},
            ]
        }
    }

    sensor = BatteryLightDailySavingsSensor(coordinator)
    # Endast dagens poster (10.5 + 15.0) ska räknas
    assert sensor.state == 25.5

    coordinator.data = None
    assert sensor.state == 0.0

@pytest.mark.asyncio
async def test_coordinator_fetches_ai_summary_after_0600(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska hämta AI-sammanfattningen kl 06:00 lokal tid."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    # Sätt befintlig data så att den inte hämtar på grund av "första uppstart"
    coordinator.data = {"action": "IDLE", "ai_summary": "Gammal text"}
    coordinator._last_ai_fetch_day = datetime.date(2026, 4, 14)  # Igår

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_now = "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now"

    with patch(patch_session) as mock_get_session, patch(patch_now) as mock_now:
        # Fejka klockan till 06:15 idag
        fake_now = datetime.datetime(2026, 4, 15, 6, 15, 0, tzinfo=datetime.timezone.utc)
        mock_now.return_value = fake_now

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mocka POST-anropet (/signal)
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        # Mocka GET-anropen för grafer
        mock_graph_resp = MagicMock()
        mock_graph_resp.__aenter__.return_value = mock_graph_resp
        mock_graph_resp.status = 200
        mock_graph_resp.json = AsyncMock(return_value={"history": [], "forecast": []})

        # Mocka GET-anropet för AI-sammanfattningen
        mock_ai_resp = MagicMock()
        mock_ai_resp.__aenter__.return_value = mock_ai_resp
        mock_ai_resp.status = 200
        mock_ai_resp.json = AsyncMock(return_value={"ai_summary": "Ny AI-text från 06:15"})

        # Styr vilket svar som ges beroende på vilken URL som anropas
        def get_side_effect(url, *args, **kwargs):
            if "ha_graph_data" in url:
                return mock_graph_resp
            elif "ha_ai_summary" in url:
                return mock_ai_resp
            return mock_graph_resp

        mock_session.get.side_effect = get_side_effect

        data = await coordinator._async_update_data()

        # Verifiera att datan uppdaterades
        assert data["ai_summary"] == "Ny AI-text från 06:15"
        assert coordinator._last_ai_fetch_day == fake_now.date()

        # Verifiera att GET anropades exakt två gånger (en för graph_data, en för ai_summary)
        calls = mock_session.get.call_args_list
        assert len(calls) == 2
        assert "ha_graph_data" in calls[0][0][0]
        assert "ha_ai_summary" in calls[1][0][0]

@pytest.mark.asyncio
async def test_coordinator_retries_ai_summary_within_window(mock_hass_instance, mock_battery):
    """Krav: Om AI-texten dröjer ska vi fortsätta försöka tills vi får den (öppet fönster)."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    # Vi har standardtexten, och datumet är fortfarande igår
    coordinator.data = {"action": "IDLE", "ai_summary": "Ingen AI-sammanfattning tillgänglig ännu."}
    coordinator._last_ai_fetch_day = datetime.date(2026, 4, 14)

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_now = "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now"

    with patch(patch_session) as mock_get_session, patch(patch_now) as mock_now:
        # Nu är klockan 06:45 (Inom retry-fönstret)
        fake_now = datetime.datetime(2026, 4, 15, 6, 45, 0, tzinfo=datetime.timezone.utc)
        mock_now.return_value = fake_now

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        mock_graph_resp = MagicMock()
        mock_graph_resp.__aenter__.return_value = mock_graph_resp
        mock_graph_resp.status = 200
        mock_graph_resp.json = AsyncMock(return_value={"history": [], "forecast": []})

        # Nu lyckas AI:n leverera texten
        mock_ai_resp = MagicMock()
        mock_ai_resp.__aenter__.return_value = mock_ai_resp
        mock_ai_resp.status = 200
        mock_ai_resp.json = AsyncMock(return_value={"ai_summary": "Nu kom texten fram!"})

        def get_side_effect(url, *args, **kwargs):
            if "ha_graph_data" in url:
                return mock_graph_resp
            elif "ha_ai_summary" in url:
                return mock_ai_resp
            return mock_graph_resp

        mock_session.get.side_effect = get_side_effect

        data = await coordinator._async_update_data()

        assert data["ai_summary"] == "Nu kom texten fram!"
        assert coordinator._last_ai_fetch_day == fake_now.date()

@pytest.mark.asyncio
async def test_coordinator_ai_summary_waits_for_new_text(mock_hass_instance, mock_battery):
    """Krav: Om API-anropet returnerar samma text som igår, ska vi fortsätta försöka (inom fönstret)."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    # Vi har en gammal text från igår
    old_text = "Sammanfattning för igår: Allt var bra."
    coordinator.data = {"action": "IDLE", "ai_summary": old_text}
    yesterday = datetime.date(2026, 4, 14)
    coordinator._last_ai_fetch_day = yesterday

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_now = "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now"

    with patch(patch_session) as mock_get_session, patch(patch_now) as mock_now:
        # Klockan är 06:16
        fake_now = datetime.datetime(2026, 4, 15, 6, 16, 0, tzinfo=datetime.timezone.utc)
        mock_now.return_value = fake_now

        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        mock_graph_resp = MagicMock()
        mock_graph_resp.__aenter__.return_value = mock_graph_resp
        mock_graph_resp.status = 200
        mock_graph_resp.json = AsyncMock(return_value={"history": [], "forecast": []})

        # Backend skickar samma text som vi redan hade (t.ex. har inte hunnit generera ny)
        mock_ai_resp = MagicMock()
        mock_ai_resp.__aenter__.return_value = mock_ai_resp
        mock_ai_resp.status = 200
        mock_ai_resp.json = AsyncMock(return_value={"ai_summary": old_text})

        def get_side_effect(url, *args, **kwargs):
            if "ha_graph_data" in url:
                return mock_graph_resp
            elif "ha_ai_summary" in url:
                return mock_ai_resp
            return mock_graph_resp

        mock_session.get.side_effect = get_side_effect

        data = await coordinator._async_update_data()

        # Texten är den samma, så vi sparar INTE datumet som "klar för idag"
        assert data["ai_summary"] == old_text
        assert getattr(coordinator, "_last_ai_fetch_day", None) == yesterday

        # I nästa cykel (fortfarande inom samma fönster) gör backend klart texten
        new_text = "Sammanfattning för idag: Nya händelser."
        mock_ai_resp.json = AsyncMock(return_value={"ai_summary": new_text})

        coordinator.data = data
        data2 = await coordinator._async_update_data()

        # Nu ska datumet ha uppdaterats eftersom texten skilde sig från gårdagens
        assert data2["ai_summary"] == new_text
        assert coordinator._last_ai_fetch_day == fake_now.date()


@pytest.mark.asyncio
@pytest.mark.parametrize("ev_state_value, expected_result", [
    ("on", True),
    ("ON", True),
    ("true", True),
    ("1", True),
    ("charging", True),
    ("på", True),
    ("PÅ", True),
    ("charge", True),
    ("sant", True),
    ("SANT", True),
    ("1500", True),  # Numeric value > 0
    ("0", False),
    ("off", False),
    ("false", False),
    ("unavailable", False),
    ("unknown", False),
    ("idle", False),
])
async def test_coordinator_ev_charging_states(mock_hass_instance, mock_battery, ev_state_value, expected_result):
    """Testar att olika tillstånd för EV-laddning hanteras korrekt."""
    config = MOCK_CONFIG.copy()
    config["ev_charging_sensor"] = "sensor.ev_charger"
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.2.3")
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.ev_charger":
            mock_state.state = ev_state_value
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})
        await coordinator._async_update_data()

        payload = mock_session.post.call_args[1]["json"]
        assert payload["is_ev_charging"] is expected_result

@pytest.mark.asyncio
async def test_peak_guard_updates_coordinator_data_for_generic(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska skriva över coordinatorns action och target_power så att
    Generic-användares sensorer uppdateras."""
    coordinator = MagicMock()
    coordinator.data = {
        "cloud_action": "HOLD",
        "cloud_target_power_kw": 0.0,
        "action": "HOLD",
        "target_power_kw": 0.0,
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }
    coordinator.async_update_listeners = MagicMock()

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "7000" # 2kW över gränsen
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None
    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att datan har ändrats lokalt och eventet har avfyrats
    assert coordinator.data["action"] == "DISCHARGE"
    assert coordinator.data["target_power_kw"] == 2.0
    coordinator.async_update_listeners.assert_called()

@pytest.mark.asyncio
async def test_peak_guard_handles_unavailable_sensors(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska inte krascha eller agera felaktigt om sensorer är 'unavailable' eller 'unknown'."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Simulera att anslutningen till växelriktaren/mätaren är nere
    limit_state = MagicMock()
    limit_state.state = "unavailable"

    load_state = MagicMock()
    load_state.state = "unknown"

    soc_state = MagicMock()
    soc_state.state = "unavailable"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Kör logiken
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att inga oönskade/farliga styrsignaler skickades under nätverksfelet
    mock_battery.apply_action.assert_not_called()

@pytest.mark.asyncio
async def test_coordinator_passive_mode(mock_hass_instance, mock_battery):
    """Krav: Om client_mode är PASSIVE ska HA inte styra batteriet via molnbeslut."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "CHARGE", "target_power_kw": 2.0, "client_mode": "PASSIVE"})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()

        mock_battery.apply_action.assert_not_called()
        assert getattr(coordinator, "_is_passive_mode", False) is True

@pytest.mark.asyncio
async def test_coordinator_passive_mode_fallback(mock_hass_instance, mock_battery):
    """Krav: Om integrationen är i PASSIVE mode och tappar nätverket ska den inte tvinga fram IDLE."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    coordinator._is_passive_mode = True  # Senast kända status var passiv
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_sleep = "custom_components.battery_optimizer_light_plus.coordinator.asyncio.sleep"

    with patch(patch_target) as mock_get_session, patch(patch_sleep):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_fail = MagicMock()
        mock_fail.__aenter__.return_value = mock_fail
        mock_fail.status = 500
        mock_fail.text = AsyncMock(return_value="Server Error")

        mock_session.post.return_value = mock_fail

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        # Det lokala batteriet får inte röras!
        mock_battery.apply_action.assert_not_called()

@pytest.mark.asyncio
async def test_peak_guard_aborts_in_passive_mode(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska inte trigga eller skicka Modbus-anrop när client_mode = PASSIVE."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
        "client_mode": "PASSIVE"
    }

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Setup av sensorvärden som normalt skulle trigga PeakGuard
    limit_state = MagicMock()
    limit_state.state = "5.0"
    load_state = MagicMock()
    load_state.state = "7000"
    soc_state = MagicMock()
    soc_state.state = "50"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        if entity_id == "sensor.husets_netto_last_virtuell":
            return load_state
        if entity_id == "sensor.soc":
            return soc_state
        return None

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Kontrollera att PeakGuard avbröt tidigt och inte anropade apply_action
    mock_battery.apply_action.assert_not_called()
    assert guard.is_active is False

@pytest.mark.asyncio
async def test_peak_guard_clears_state_when_switching_to_passive_mode(mock_hass_instance, mock_battery):
    """Krav: Om integrationen växlar till PASSIVE mode ska PeakGuard återställa sina lokala flaggor."""
    coordinator = MagicMock()
    coordinator.data = {
        "action": "HOLD",
        "is_active": True,
        "is_peak_shaving_active": True,
        "peakguard_status": "Active",
        "client_mode": "PASSIVE"
    }
    coordinator.async_update_listeners = MagicMock()

    guard = PeakGuard(mock_hass_instance, MOCK_CONFIG, coordinator, mock_battery)

    # Sätt PeakGuard i ett "smutsigt" läge där den tidigare var aktiv med olika åtgärder
    guard._has_reported = True
    guard._is_solar_override = True
    guard._in_maintenance = True
    guard._maintenance_reason = "Test Override"

    # Kör update (vi skickar in mockade sensorer även om PeakGuard kommer avbryta tidigt)
    await guard.update("sensor.husets_netto_last_virtuell", "sensor.optimizer_light_peak_limit")

    # Verifiera att flaggorna omedelbart återställdes för att inte störa HA-dashboards
    assert guard.is_active is False
    assert guard.is_solar_override is False
    assert guard.in_maintenance is False
    assert guard.maintenance_reason is None

    # Verifiera att lyssnarna uppdaterades (så att de grafiska sensorerna ritas om i Home Assistant)
    assert coordinator.async_update_listeners.call_count >= 1

@pytest.mark.asyncio
async def test_coordinator_transitions_between_active_and_passive(mock_hass_instance, mock_battery):
    """Krav: Koordinatorn ska kunna växla mellan ACTIVE och PASSIVE dynamiskt vid varje uppdatering."""
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        # Steg 1: Anrop 1 ger ACTIVE (Standard)
        mock_post.json = AsyncMock(
            return_value={"action": "CHARGE", "target_power_kw": 2.0, "client_mode": "ACTIVE"}
        )
        await coordinator._async_update_data()
        assert getattr(coordinator, "_is_passive_mode", False) is False
        mock_battery.apply_action.assert_called_with("CHARGE", 2.0)

        # Steg 2: Anrop 2 ger PASSIVE (Edge tog över)
        mock_battery.apply_action.reset_mock()
        mock_post.json = AsyncMock(
            return_value={"action": "DISCHARGE", "target_power_kw": 3.0, "client_mode": "PASSIVE"}
        )
        await coordinator._async_update_data()
        assert getattr(coordinator, "_is_passive_mode", False) is True
        mock_battery.apply_action.assert_not_called()  # Ska INTE utföras lokalt!

        # Steg 3: Anrop 3 ger ACTIVE igen (Edge-klienten togs bort)
        mock_post.json = AsyncMock(
            return_value={"action": "HOLD", "target_power_kw": 0.0, "client_mode": "ACTIVE"}
        )
        await coordinator._async_update_data()
        assert getattr(coordinator, "_is_passive_mode", False) is False
        mock_battery.apply_action.assert_called_with("HOLD", 0.0)

@pytest.mark.asyncio
async def test_base_battery_is_offgrid():
    """Testar att BatteryApi:s grundläggande is_offgrid-metod fungerar med en HA-sensor."""
    from custom_components.battery_optimizer_light_plus.batteries.generic import GenericBattery

    hass = MagicMock()
    battery = GenericBattery(hass, "sensor.soc")

    # 1. Om offgrid_sensor saknas helt
    assert await battery.is_offgrid() is False

    # 2. Med konfigurerad sensor som returnerar 'on'
    battery._offgrid_sensor = "binary_sensor.offgrid"
    mock_state = MagicMock()
    mock_state.state = "on"
    hass.states.get.return_value = mock_state

    assert await battery.is_offgrid() is True
    hass.states.get.assert_called_with("binary_sensor.offgrid")

    # 3. Med konfigurerad sensor som returnerar 'off'
    mock_state.state = "off"
    assert await battery.is_offgrid() is False

    # 4. Med sensor som är 'unavailable'
    mock_state.state = "unavailable"
    assert await battery.is_offgrid() is False

@pytest.mark.asyncio
async def test_coordinator_uses_virtual_load_sensor(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska använda virtual_load_sensor som prio 2 för husets förbrukning."""
    config = MOCK_CONFIG.copy()
    config["virtual_load_sensor"] = "sensor.my_custom_house_load"

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")

    # Batteriet rapporterar in None för förbrukning
    if hasattr(mock_battery, "get_calculated_consumption"):
        del mock_battery.get_calculated_consumption
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    def mock_get_state(entity_id):
        mock_state = MagicMock()
        if entity_id == "sensor.soc":
            mock_state.state = "50"
        elif entity_id == "sensor.my_custom_house_load":
            mock_state.state = "6200" # 6200 W
        return mock_state
    mock_hass_instance.states.get.side_effect = mock_get_state

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})


        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert payload["current_consumption_kw"] == 6.2

@pytest.mark.asyncio
async def test_coordinator_payload_includes_inverter_brand(mock_hass_instance, mock_battery):
    """Krav: Coordinator ska skicka med inverter_brand i payloaden till molnet."""
    config = MOCK_CONFIG.copy()
    config["battery_type"] = "generic"

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config, version="1.0.0")
    coordinator.battery_api = mock_battery
    mock_battery.get_current_soc.return_value = 50.0

    patch_target = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_target) as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_post = mock_session.post.return_value.__aenter__.return_value
        mock_post.status = 200
        mock_post.json = AsyncMock(return_value={"action": "IDLE"})

        mock_get = mock_session.get.return_value.__aenter__.return_value
        mock_get.status = 200
        mock_get.json = AsyncMock(return_value={"history": [], "forecast": []})

        await coordinator._async_update_data()
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']

        assert payload["inverter_brand"] == "generic"

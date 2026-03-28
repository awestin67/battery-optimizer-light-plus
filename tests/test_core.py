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
}

@pytest.fixture
def mock_hass_instance():
    """Skapar en fejkad Home Assistant-instans."""
    hass = MagicMock()
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
    mock.get_battery_power = AsyncMock(return_value=None)
    mock.get_grid_power = AsyncMock(return_value=None)
    mock.get_status_text = AsyncMock(return_value=None)
    mock.apply_action = AsyncMock()
    return mock

@pytest.mark.asyncio
async def test_coordinator_handles_unavailable_soc(mock_hass_instance):
    """
    Krav: Om SoC är otillgänglig (t.ex. vid uppstart) ska koordinatorn
    returnera gammal data och inte krascha.
    """
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, MOCK_CONFIG)
    coordinator.data = {"action": "OLD_DATA"}  # Set some old data

    # Simulate that the sensor is 'unavailable', causing get_current_soc() to return None
    mock_state = MagicMock()
    mock_state.state = "unavailable"
    mock_hass_instance.states.get.return_value = mock_state

    # Mock the session to verify it's not called
    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        result = await coordinator._async_update_data()
        assert result == {"action": "OLD_DATA"}
        mock_get_session.return_value.post.assert_not_called()

@pytest.mark.asyncio
async def test_peak_guard_triggers_discharge(mock_hass_instance, mock_battery):
    """Krav: Om lasten är högre än gränsen ska batteriet urladdas."""
    coordinator = MagicMock()
    coordinator.data = {"action": "HOLD"} # Molnet säger HOLD, men PeakGuard ska ta över

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
    coordinator.data = {"action": "IDLE"} # Molnet säger IDLE

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
    coordinator.data = {"action": "HOLD", "is_peak_shaving_active": False, "peakguard_status": "Off"}

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
    coordinator.data = {"action": "HOLD", "is_peak_shaving_active": False, "peakguard_status": "Off"}

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
    coordinator.data = {"is_peak_shaving_active": True}

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
    coordinator.data = {"is_peak_shaving_active": False, "peakguard_status": "Off"}
    peak_guard.is_active = False
    assert sensor.state == "Off"
    assert sensor.icon == "mdi:shield-off"

    # Fall 3b: Paused
    coordinator.data = {"is_peak_shaving_active": False, "peakguard_status": "Paused"}
    assert sensor.state == "Paused"
    assert sensor.icon == "mdi:pause-circle-outline"

    # Fall 4: Maintenance
    coordinator.data = {"is_peak_shaving_active": True, "peakguard_status": "Active"}
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
    coordinator.data = {"action": "HOLD", "max_discharge_kw": 3.3}

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
    coordinator.data = {"action": "HOLD"} # Molnet säger HOLD

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

    # Mocka SoC state
    mock_state = MagicMock()
    mock_state.state = "50"
    mock_hass_instance.states.get.return_value = mock_state

    # Mocka PeakGuard och sätt override till True
    peak_guard = MagicMock()
    peak_guard.is_solar_override = True
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

        await coordinator._async_update_data()

        # Verifiera anropet
        _, kwargs = mock_session.post.call_args
        payload = kwargs['json']


        assert payload["is_solar_override"] is True
        assert payload["soc"] == 50.0
        assert payload["ha_version"] == "1.2.3"

@pytest.mark.asyncio
async def test_peak_guard_calculates_load_with_inverted_grid(mock_hass_instance, mock_battery):
    """Krav: Om grid_sensor_invert är True ska grid-värdet negeras vid beräkning."""
    # Konfiguration med inverterad grid sensor och INGEN virtuell sensor
    config = MOCK_CONFIG.copy()
    config["grid_sensor_invert"] = True
    config["virtual_load_sensor"] = None

    coordinator = MagicMock()
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
async def test_peak_guard_stops_at_zero_soc(mock_hass_instance, mock_battery):
    """Krav: PeakGuard ska sluta urladda när SoC når 0%."""
    coordinator = MagicMock()
    coordinator.data = {"action": "HOLD"} # Molnet säger HOLD

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
    coordinator.data = {"action": "CHARGE", "target_power_kw": 3.0} # 3000W

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
    coordinator.data = {"action": "IDLE"} # Molnet svarar IDLE (Auto)

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"}

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
    coordinator.data = {"action": "HOLD"} # Molnet säger HOLD (Buffer Fill active)

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
async def test_peak_guard_solar_override_with_internal_battery_api(mock_hass_instance, mock_battery):
    """Krav: Solar Override ska triggas baserat på interna batterimetoder och ignorera spöksensorer."""
    coordinator = MagicMock()
    coordinator.data = {"action": "HOLD"}

    # Konfigurationen INNEHÅLLER gamla spöksensorer, men vi förväntar oss att koden struntar i dem
    config = MOCK_CONFIG.copy()

    guard = PeakGuard(mock_hass_instance, config, coordinator, mock_battery)

    # Mocka interna batterimetoder för att simulera den enorma solexporten (t.ex. Sonnen)
    mock_battery.get_virtual_load.return_value = -4581.0  # Stor export
    mock_battery.get_grid_power.return_value = -4581.0    # Grid exporterar (negativt)
    mock_battery.get_battery_power.return_value = 0.0     # Batteriet är stilla
    mock_battery.get_current_soc.return_value = 50.0

    # Skapa falska "spöksensorer" som annars hade blockerat Solar Override
    bad_state = MagicMock()
    bad_state.state = "5000" # 5000W Import (Skulle blockera override om PeakGuard lyssnade på denna)
    limit_state = MagicMock()
    limit_state.state = "5.0"

    def get_state_side_effect(entity_id):
        if entity_id == "sensor.optimizer_light_peak_limit":
            return limit_state
        return bad_state # Alla andra (grid, bat, load) ger det falska import-värdet "5000"

    mock_hass_instance.states.get.side_effect = get_state_side_effect

    # Första körningen: Systemet ser -4581W export från API:et, och startar 30s-timern
    await guard.update(config.get("virtual_load_sensor"), "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is False

    assert guard._solar_override_trigger_start is not None, (
        "Timern startade inte! Spöksensorerna blockerar fortfarande logiken."
    )

    # Snabbspola tiden förbi 30 sekunder
    guard._solar_override_trigger_start -= datetime.timedelta(seconds=35)

    # Andra körningen: Nu har tiden gått, override ska aktiveras!
    await guard.update(config.get("virtual_load_sensor"), "sensor.optimizer_light_peak_limit")
    assert guard.is_solar_override is True

@pytest.mark.asyncio
async def test_peak_guard_fallback_to_ha_sensors(mock_hass_instance):
    """Krav: Om batteriet saknar interna metoder (Huawei/Generic), ska HA-sensorer användas."""
    coordinator = MagicMock()
    coordinator.data = {"action": "HOLD"}

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
        assert "Connection error after 3 attempts" in str(excinfo.value)

@pytest.mark.asyncio
async def test_lifecycle_and_services(mock_hass_instance):
    """Testar setup, migrering, registrering av tjänster, unload och reload."""
    entry = MagicMock()
    entry.data = MOCK_CONFIG.copy()
    # Sätt in gammal dev-URL för att trigga migreringslogiken
    entry.data["api_url"] = "https://battery-prod.awestinconsulting.se/signal"
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

        # Verifiera att migreringen av URL sparades i config_entries
        mock_hass_instance.config_entries.async_update_entry.assert_called_once()

        # Verifiera att background tracker sattes upp och kör dess on_load_change
        mock_track.assert_called_once()
        on_load_change = mock_track.call_args[0][2]
        mock_hass_instance.state = CoreState.running # Låtsas att HA är 'running'
        await on_load_change(None)
        mock_guard.update.assert_called()

        # Verifiera tjänster (services)
        assert mock_hass_instance.services.async_register.call_count == 5
        services = {call[0][1]: call[0][2] for call in mock_hass_instance.services.async_register.call_args_list}

        await services["force_charge"](MagicMock(data={"power": 1000}))
        mock_coord.battery_api.apply_action.assert_called_with("CHARGE", 1.0)

        await services["force_discharge"](MagicMock(data={"power": 1500}))
        mock_coord.battery_api.apply_action.assert_called_with("DISCHARGE", 1.5)

        await services["hold"](MagicMock(data={}))
        mock_coord.battery_api.apply_action.assert_called_with("HOLD")

        await services["auto"](MagicMock(data={}))
        mock_coord.battery_api.apply_action.assert_called_with("IDLE")

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

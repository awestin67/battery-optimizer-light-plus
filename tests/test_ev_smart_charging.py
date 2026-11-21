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
from custom_components.battery_optimizer_light_plus.const import (
    CONF_EV_C1_NAME,
    CONF_EV_C1_TARGET_KWH,
)
from custom_components.battery_optimizer_light_plus.config_flow import BatteryOptimizerLightOptionsFlow

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_hass_instance():
    hass = MagicMock()
    hass.data = {}
    hass.states.get = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    return hass


async def test_options_flow_init():
    """Test the options flow for EV Smart Charging."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.options = {}
    config_entry.data = {}

    flow = BatteryOptimizerLightOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = hass

    # Kör init
    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    # Verifiera att schemat har våra nya EV-fält
    schema_keys = result["data_schema"].schema.keys()
    assert any(CONF_EV_C1_NAME in str(k) for k in schema_keys)
    assert any(CONF_EV_C1_TARGET_KWH in str(k) for k in schema_keys)

async def test_plan_ev_charging_service_call(mock_hass_instance):
    """Test the plan_ev_charging service directly."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "20.0",
            "input_datetime.depart": "07:00:00",
            "input_number.max_kw": "11.0"
        }.get(entity_id, "unknown")
    )

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"schedules": {"Testbil": [{"start": "2026-07-19T02:00:00"}]}})
        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")

        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        assert kwargs["json"]["cars"][0]["id"] == "Testbil"
        assert kwargs["json"]["cars"][0]["departure_time"] == "07:00"
        assert coordinator.ev_schedules["Testbil"] == [{"start": "2026-07-19T02:00:00"}]

async def test_async_clear_ev_charging(mock_hass_instance):
    """Test att async_clear_ev_charging skickar DELETE-anrop."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
    }

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.ev_schedules = {"Testbil": [{"start": "now"}]}
    coordinator.async_set_updated_data = MagicMock()
    coordinator.data = {}

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.delete.return_value.__aenter__.return_value = mock_response
        mock_get_session.return_value = mock_session

        await coordinator.async_clear_ev_charging("car1")

        mock_session.delete.assert_called_once()
        args, kwargs = mock_session.delete.call_args
        assert "Testbil" in args[0]
        assert "Testbil" not in coordinator.ev_schedules


async def test_plan_ev_charging_with_datetime_helper_format(mock_hass_instance):
    """Test att input_datetime med både datum och tid parsas till HH:MM."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "35.0",
            "input_datetime.depart": "2026-11-07 06:30:00",
            "input_number.max_kw": "11.0"
        }.get(entity_id, "unknown")
    )

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"schedules": {"Testbil": [{"start": "2026-11-07T01:00:00"}]}})
        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")

        mock_session.post.assert_called_once()
        _, kwargs = mock_session.post.call_args
        assert kwargs["json"]["cars"][0]["departure_time"] == "06:30"


async def _setup_ev_entry(mock_hass_instance, cable_state):
    """Hjälpare: kör async_setup_entry med EV-hjälpare och fångar lyssnare + debounce-timers."""
    from custom_components.battery_optimizer_light_plus import async_setup_entry

    entry = MagicMock()
    entry.entry_id = "ev_entry"
    entry.data = {
        "api_url": "http://test-api",
        "api_key": "12345",
        "ev_c1_cable_connected": "binary_sensor.cable",
        "ev_c1_target_kwh": "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }
    entry.options = {}

    cable = MagicMock()
    cable.state = cable_state
    mock_hass_instance.states.get.side_effect = lambda e: cable if e == "binary_sensor.cable" else None

    pkg = "custom_components.battery_optimizer_light_plus"
    tracked = []
    timers = []

    def fake_track(hass, entities, cb):
        tracked.append((list(entities), cb))
        return MagicMock()

    def fake_later(hass, delay, cb):
        unsub = MagicMock()
        timers.append((delay, cb, unsub))
        return unsub

    with patch(f"{pkg}.async_get_integration", new_callable=AsyncMock) as gi, \
            patch(f"{pkg}.BatteryOptimizerLightCoordinator") as coord_cls, \
            patch(f"{pkg}.async_track_state_change_event", side_effect=fake_track):
        gi.return_value = MagicMock()
        coord = coord_cls.return_value
        coord.async_config_entry_first_refresh = AsyncMock()
        coord.async_plan_ev_charging = AsyncMock()
        coord.data = {}
        assert await async_setup_entry(mock_hass_instance, entry) is True

    # Stäng eventuella coroutines som skickats till mockad async_create_task under setup
    for call in mock_hass_instance.async_create_task.call_args_list:
        arg = call[0][0]
        if hasattr(arg, "close"):
            arg.close()

    return coord, tracked, timers, fake_later


def _helper_event(entity_id, old, new):
    event = MagicMock()
    old_s = MagicMock(state=old) if old is not None else None
    event.data = {"entity_id": entity_id, "old_state": old_s, "new_state": MagicMock(state=new)}
    return event


async def test_ev_helper_change_is_debounced(mock_hass_instance):
    """Flera snabba helper-ändringar ska ge exakt en omplanering efter debounce."""
    pkg = "custom_components.battery_optimizer_light_plus"
    coord, tracked, timers, fake_later = await _setup_ev_entry(mock_hass_instance, "on")
    coord.async_plan_ev_charging.reset_mock()
    helper_cb = next(cb for ents, cb in tracked if "input_number.target" in ents)

    with patch(f"{pkg}.async_call_later", side_effect=fake_later):
        await helper_cb(_helper_event("input_number.target", "30", "31"))
        await helper_cb(_helper_event("input_number.target", "31", "32"))
        await helper_cb(_helper_event("input_number.target", "32", "33"))

    coord.async_plan_ev_charging.assert_not_called()
    assert len(timers) == 3
    # Tidigare timers ska ha avbrutits
    timers[0][2].assert_called_once()
    timers[1][2].assert_called_once()
    timers[2][2].assert_not_called()

    await timers[-1][1](None)
    coord.async_plan_ev_charging.assert_called_once_with("car1")


async def test_ev_helper_change_ignored_when_cable_disconnected_or_initial_state(mock_hass_instance):
    """Ingen omplanering om kabeln är urkopplad eller om det är första tillståndet (old_state=None)."""
    pkg = "custom_components.battery_optimizer_light_plus"
    coord, tracked, timers, fake_later = await _setup_ev_entry(mock_hass_instance, "off")
    helper_cb = next(cb for ents, cb in tracked if "input_number.target" in ents)
    with patch(f"{pkg}.async_call_later", side_effect=fake_later):
        await helper_cb(_helper_event("input_number.target", "30", "31"))
    assert timers == []

    coord, tracked, timers, fake_later = await _setup_ev_entry(mock_hass_instance, "on")
    helper_cb = next(cb for ents, cb in tracked if "input_number.target" in ents)
    with patch(f"{pkg}.async_call_later", side_effect=fake_later):
        await helper_cb(_helper_event("input_number.target", None, "31"))
    assert timers == []


async def test_ev_plan_created_at_setup_when_cable_connected(mock_hass_instance):
    """Om kabeln redan är inkopplad vid uppstart ska en startplan skapas för bilen."""
    coord, _, _, _ = await _setup_ev_entry(mock_hass_instance, "on")
    assert mock_hass_instance.async_create_task.called
    coord.async_plan_ev_charging.assert_called_once_with("car1")


async def test_ev_preliminary_plan_and_afternoon_replan(mock_hass_instance):
    """Preliminär plan före kl 13:15 ska spåras och automatiskt planeras om efter kl 13:15."""
    from datetime import datetime
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.async_request_refresh = AsyncMock()

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "25.0",
            "input_datetime.depart": "07:00:00",
            "input_number.max_kw": "11.0",
        }.get(entity_id, "unknown")
    )

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "schedules": {"Testbil": [{"start": "2026-11-07T22:00:00"}]},
                "is_preliminary": True,
            }
        )
        mock_session.post.return_value.__aenter__.return_value = mock_response
        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")
        assert "car1" in coordinator.ev_preliminary_cars

        # Fånga _update_interval från setup_timer
        captured_cb = None

        def fake_track_time(hass, action, **kwargs):
            nonlocal captured_cb
            captured_cb = action
            return MagicMock()

        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.async_track_time_change",
            side_effect=fake_track_time,
        ):
            coordinator.setup_timer()

        assert captured_cb is not None

        # 1. Före kl 13:15 (t.ex. 12:15) ska ingen ny EV-planering triggas
        mock_session.post.reset_mock()
        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now",
            return_value=datetime(2026, 11, 7, 12, 15, 0),
        ):
            await captured_cb(None)
        mock_session.post.assert_not_called()
        assert "car1" in coordinator.ev_preliminary_cars

        # 2. Vid kl 13:15 (men fel minut, t.ex. 13:20) ska ingen ny EV-planering triggas
        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now",
            return_value=datetime(2026, 11, 7, 13, 20, 0),
        ):
            await captured_cb(None)
        mock_session.post.assert_not_called()

        # 3. Vid kl 13:15 (kvartsminut 15) ska omplanering triggas och rensa is_preliminary när priserna finns
        mock_response.json = AsyncMock(
            return_value={
                "schedules": {"Testbil": [{"start": "2026-11-08T02:00:00"}]},
                "is_preliminary": False,
            }
        )
        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.dt_util.now",
            return_value=datetime(2026, 11, 7, 13, 15, 0),
        ):
            await captured_cb(None)
        mock_session.post.assert_called_once()
        assert "car1" not in coordinator.ev_preliminary_cars


async def test_ev_preliminary_flag_cleared_on_disconnect(mock_hass_instance):
    """Att koppla ur kabeln (async_clear_ev_charging) ska även rensa ev_preliminary_cars."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.ev_schedules = {"Testbil": [{"start": "now"}]}
    coordinator.ev_preliminary_cars = {"car1"}
    coordinator.data = None

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.delete.return_value.__aenter__.return_value = mock_response
        mock_get_session.return_value = mock_session

        await coordinator.async_clear_ev_charging("car1")
        assert "car1" not in coordinator.ev_preliminary_cars
        assert "Testbil" not in coordinator.ev_schedules


async def test_ev_schedule_sensor_always_available_and_preliminary_attribute():
    """BatteryLightEVScheduleSensor ska alltid vara available=True och exponera is_preliminary."""
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    coordinator = MagicMock()
    coordinator.api_key = "test_key"
    coordinator.last_update_success = False
    coordinator.data = None
    coordinator.ev_schedules = {}
    coordinator.ev_preliminary_cars = set()

    sensor = BatteryLightEVScheduleSensor(coordinator)
    assert sensor.available is True
    assert sensor.state == "Inga scheman"
    assert sensor.extra_state_attributes == {"schedules": {}, "is_preliminary": False}

    # När preliminärt schema finns
    coordinator.ev_schedules = {"Testbil": [{"start": "2026-11-07T22:00:00"}]}
    coordinator.ev_preliminary_cars = {"car1"}
    assert sensor.available is True
    assert sensor.state == "1 bilar planerade"
    assert sensor.extra_state_attributes["is_preliminary"] is True

    # När definitivt schema ersatt det preliminära
    coordinator.ev_preliminary_cars.clear()
    assert sensor.extra_state_attributes["is_preliminary"] is False


async def test_plan_and_clear_ev_charging_refreshes_only_graph_data(mock_hass_instance):
    """EV-planering och rensning ska uppdatera /ha_graph_data men INTE anropa async_request_refresh (/signal)."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "Testbil",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }

    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.data = {"action": "IDLE", "graph_data": {}}
    coordinator.async_request_refresh = AsyncMock()

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "20.0",
            "input_datetime.depart": "07:00:00",
            "input_number.max_kw": "11.0",
        }.get(entity_id, "unknown")
    )

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()

        mock_post_resp = AsyncMock()
        mock_post_resp.status = 200
        mock_post_resp.json = AsyncMock(return_value={"schedules": {"Testbil": [{"start": "2026-11-07T02:00:00"}]}})
        mock_session.post.return_value.__aenter__.return_value = mock_post_resp

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(
            return_value={"history": [{"timestamp": "2026-11-07T00:00:00Z", "current_solar_kw": 1.5}]}
        )
        mock_session.get.return_value.__aenter__.return_value = mock_get_resp

        mock_del_resp = AsyncMock()
        mock_del_resp.status = 200
        mock_session.delete.return_value.__aenter__.return_value = mock_del_resp

        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")

        coordinator.async_request_refresh.assert_not_called()
        mock_session.get.assert_called_once()
        assert coordinator.data["graph_data"]["history"][0]["solar_kw"] == 1.5
        assert "last_update_time" in coordinator.data

        mock_session.get.reset_mock()
        await coordinator.async_clear_ev_charging("car1")

        coordinator.async_request_refresh.assert_not_called()
        mock_session.get.assert_called_once()


async def test_coordinator_429_rate_limit_preserves_existing_data_without_retries(mock_hass_instance):
    """Vid HTTP 429 ska befintlig coordinator.data behållas direkt utan 3 retries eller IDLE-fallback."""
    from custom_components.battery_optimizer_light_plus.coordinator import (
        BatteryOptimizerLightCoordinator,
        UpdateFailed,
    )

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        "soc_sensor": "sensor.soc",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    mock_battery = MagicMock()
    mock_battery.software_version = None
    mock_battery.is_modern_ems = False
    mock_battery.get_current_soc = AsyncMock(return_value=60.0)
    mock_battery.get_min_soc = AsyncMock(return_value=0.0)
    mock_battery.get_grid_power = AsyncMock(return_value=500.0)
    mock_battery.get_battery_power = AsyncMock(return_value=0.0)
    mock_battery.get_solar_power = AsyncMock(return_value=0.0)
    mock_battery.get_virtual_load = AsyncMock(return_value=500.0)
    mock_battery.get_calculated_consumption = AsyncMock(return_value=500.0)
    mock_battery.get_house_consumption = AsyncMock(return_value=500.0)
    mock_battery.get_status_text = AsyncMock(return_value=None)
    mock_battery.apply_action = AsyncMock()
    coordinator.battery_api = mock_battery

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    patch_sleep = "custom_components.battery_optimizer_light_plus.coordinator.asyncio.sleep"
    with patch(patch_session) as mock_get_session, patch(patch_sleep, new_callable=AsyncMock) as mock_sleep:
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 429
        mock_resp.text = AsyncMock(return_value='{"error":"Rate limit exceeded: 5 per 1 minute"}')
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_get_session.return_value = mock_session

        # Fall 1: coordinator.data finns redan -> ska returnera befintlig data direkt utan retry
        existing_data = {"action": "CHARGE", "target_power_kw": 3.5}
        coordinator.data = existing_data
        res = await coordinator._async_update_data()
        assert res is existing_data
        assert mock_session.post.call_count == 1
        mock_sleep.assert_not_called()
        mock_battery.apply_action.assert_not_called()

        # Fall 2: coordinator.data är None (första uppstart) -> ska kasta UpdateFailed direkt utan 3 retries
        mock_session.post.reset_mock()
        coordinator.data = None
        with pytest.raises(UpdateFailed) as excinfo:
            await coordinator._async_update_data()
        assert "Server 429:" in str(excinfo.value)
        assert mock_session.post.call_count == 1
        mock_sleep.assert_not_called()

        # Fall 3: 200 OK med ev_smart_plans -> ska synka till coordinator.ev_schedules
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "action": "IDLE",
                "target_power_kw": 0.0,
                "ev_smart_plans": {"Testbil": [{"start": "2026-11-08T01:00:00", "charge_kw": 11.0}]},
            }
        )
        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"history": []})
        mock_session.get.return_value.__aenter__.return_value = mock_get_resp

        res_ok = await coordinator._async_update_data()
        assert res_ok["action"] == "IDLE"
        assert coordinator.ev_schedules == {"Testbil": [{"start": "2026-11-08T01:00:00", "charge_kw": 11.0}]}


async def test_ev_cable_connected_supports_text_sensors_and_avoids_duplicate_triggers(mock_hass_instance):
    """Kabelanslutning ska stödja både binary_sensor ('on'/'off') och text-sensorer
    (t.ex. 'EV Connected' -> 'Charging' -> 'EV Disconnected') utan dubbla replans."""
    coord, tracked, _, _ = await _setup_ev_entry(mock_hass_instance, "EV Disconnected")
    coord.async_plan_ev_charging.reset_mock()
    coord.async_clear_ev_charging = AsyncMock()

    cable_cb = next(cb for ents, cb in tracked if "binary_sensor.cable" in ents)

    # 1. 'EV Disconnected' -> 'Waiting for EV' (Kabel ansluten) -> ska trigga planering
    await cable_cb(_helper_event("binary_sensor.cable", "EV Disconnected", "Waiting for EV"))
    coord.async_plan_ev_charging.assert_called_once_with("car1")
    coord.async_clear_ev_charging.assert_not_called()

    # 2. 'Waiting for EV' -> 'Charging' (Fortfarande ansluten) -> ska INTE trigga ny plan eller rensa
    coord.async_plan_ev_charging.reset_mock()
    await cable_cb(_helper_event("binary_sensor.cable", "Waiting for EV", "Charging"))
    coord.async_plan_ev_charging.assert_not_called()
    coord.async_clear_ev_charging.assert_not_called()

    # 3. 'Charging' -> 'unavailable' (Tillfälligt molnavbrott) -> ska INTE rensa planen
    coord.ev_schedules = {"Bil 1": [{"start": "2026-11-08T01:00:00"}]}
    await cable_cb(_helper_event("binary_sensor.cable", "Charging", "unavailable"))
    coord.async_clear_ev_charging.assert_not_called()

    # 3b. 'unavailable' -> 'Charging' (Molnsensorn återhämtar sig när schema redan finns) -> ska INTE replanna
    coord.async_plan_ev_charging.reset_mock()
    await cable_cb(_helper_event("binary_sensor.cable", "unavailable", "Charging"))
    coord.async_plan_ev_charging.assert_not_called()

    # 4. 'Charging' -> 'EV Disconnected' (Urkopplad) -> ska rensa planen
    await cable_cb(_helper_event("binary_sensor.cable", "Charging", "EV Disconnected"))
    coord.async_clear_ev_charging.assert_called_once_with("car1")

    # 5. 'unavailable' -> 'EV Disconnected' när inget schema finns -> ska INTE skicka onödig DELETE
    coord.ev_schedules = {}
    coord.async_clear_ev_charging.reset_mock()
    await cable_cb(_helper_event("binary_sensor.cable", "unavailable", "EV Disconnected"))
    coord.async_clear_ev_charging.assert_not_called()

    # 6. Numeriskt värde '1' på kabelsensorn ska INTE feltolkas som kabel ansluten
    coord.async_plan_ev_charging.reset_mock()
    await cable_cb(_helper_event("binary_sensor.cable", "0", "1"))
    coord.async_plan_ev_charging.assert_not_called()


async def test_ev_replan_preliminary_to_sharp_replaces_sensor_schedule(mock_hass_instance, caplog):
    """Fall 1: Preliminärt schema A ersätts helt med skarpt schema B vid omplanering 13:15."""
    import logging
    from datetime import datetime, timezone
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "BMW",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.async_request_refresh = AsyncMock()
    sensor = BatteryLightEVScheduleSensor(coordinator)

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "20.0",
            "input_datetime.depart": "07:30:00",
            "input_number.max_kw": "5.4",
        }.get(entity_id, "unknown")
    )

    plan_a = [
        {"start": "2026-11-21T12:45:00", "end": "2026-11-21T13:15:00", "charge_kw": 5.4},
        {"start": "2026-11-22T04:30:00", "end": "2026-11-22T05:30:00", "charge_kw": 5.4},
    ]
    plan_b = [
        {"start": "2026-11-22T04:00:00", "end": "2026-11-22T07:15:00", "charge_kw": 5.4},
    ]

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": plan_a}, "is_preliminary": True})
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")
        attrs_before = sensor.extra_state_attributes
        assert attrs_before["schedules"] == {"BMW": plan_a}
        assert attrs_before["is_preliminary"] is True
        assert "car1" in coordinator.ev_preliminary_cars

        captured_cb = None

        def fake_track_time(hass, action, **kwargs):
            nonlocal captured_cb
            captured_cb = action
            return MagicMock()

        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.async_track_time_change",
            side_effect=fake_track_time,
        ):
            coordinator.setup_timer()

        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": plan_b}, "is_preliminary": False})
        with caplog.at_level(logging.DEBUG), patch(
            "custom_components.battery_optimizer_light_plus.coordinator.dt_util.as_local",
            side_effect=lambda dt: dt,
        ):
            await captured_cb(datetime(2026, 11, 21, 13, 15, 30, tzinfo=timezone.utc))

        attrs_after = sensor.extra_state_attributes
        assert attrs_after["schedules"] == {"BMW": plan_b}
        assert attrs_after["is_preliminary"] is False
        assert "car1" not in coordinator.ev_preliminary_cars
        # Tidigare snapshot ska inte ha muterats in-place
        assert attrs_before["schedules"] == {"BMW": plan_a}
        assert "EV replan BMW: preliminary=True->False, steps 2->1, window 12:45–05:30 -> 04:00–07:15" in caplog.text


async def test_signal_after_replan_never_overwrites_ev_schedule(mock_hass_instance):
    """Fall 2: /signal med gammal ev_smart_plans får inte skriva över nytt schema eller återuppliva ett rensat."""
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        "soc_sensor": "sensor.soc",
        CONF_EV_C1_NAME: "BMW",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    mock_battery = MagicMock()
    mock_battery.software_version = None
    mock_battery.get_current_soc = AsyncMock(return_value=60.0)
    mock_battery.get_min_soc = AsyncMock(return_value=0.0)
    mock_battery.get_calculated_consumption = AsyncMock(return_value=500.0)
    mock_battery.get_solar_power = AsyncMock(return_value=0.0)
    mock_battery.apply_action = AsyncMock()
    coordinator.battery_api = mock_battery
    sensor = BatteryLightEVScheduleSensor(coordinator)

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": "20.0",
            "input_datetime.depart": "07:30:00",
            "input_number.max_kw": "5.4",
        }.get(entity_id, "unknown")
    )

    plan_a = [{"start": "2026-11-21T12:45:00", "end": "2026-11-21T13:15:00", "charge_kw": 5.4}]
    plan_b = [{"start": "2026-11-22T04:00:00", "end": "2026-11-22T07:15:00", "charge_kw": 5.4}]

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_post_resp = AsyncMock()
        mock_post_resp.status = 200
        mock_post_resp.json = AsyncMock(return_value={"schedules": {"BMW": plan_b}, "is_preliminary": False})
        mock_session.post.return_value.__aenter__.return_value = mock_post_resp

        mock_get_resp = AsyncMock()
        mock_get_resp.status = 200
        mock_get_resp.json = AsyncMock(return_value={"history": []})
        mock_session.get.return_value.__aenter__.return_value = mock_get_resp

        mock_del_resp = AsyncMock()
        mock_del_resp.status = 200
        mock_session.delete.return_value.__aenter__.return_value = mock_del_resp
        mock_get_session.return_value = mock_session

        # 1. Omplanering sätter skarpt schema B
        await coordinator.async_plan_ev_charging("car1")
        assert sensor.extra_state_attributes["schedules"] == {"BMW": plan_b}

        # 2. Efterföljande /signal har gammal ev_smart_plans (A) -> sensorn ska behålla B
        mock_post_resp.json = AsyncMock(
            return_value={"action": "IDLE", "target_power_kw": 0.0, "ev_smart_plans": {"BMW": plan_a}}
        )
        await coordinator._async_update_data()
        assert sensor.extra_state_attributes["schedules"] == {"BMW": plan_b}

        # 3. Kabeln kopplas ur -> schemat rensas och /signal får inte återuppliva A
        await coordinator.async_clear_ev_charging("car1")
        assert sensor.extra_state_attributes["schedules"] == {}
        await coordinator._async_update_data()
        assert sensor.extra_state_attributes["schedules"] == {}


async def test_ev_replan_empty_response_does_not_mark_preliminary_as_sharp(mock_hass_instance, caplog):
    """Fall 3: Tomt schedules-svar med is_preliminary=false ska inte markera gammalt schema som skarpt."""
    import logging
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "BMW",
        CONF_EV_C1_TARGET_KWH: "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    sensor = BatteryLightEVScheduleSensor(coordinator)

    target_val = {"v": "20.0"}
    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.target": target_val["v"],
            "input_datetime.depart": "07:30:00",
            "input_number.max_kw": "5.4",
        }.get(entity_id, "unknown")
    )

    plan_a = [{"start": "2026-11-21T12:45:00", "end": "2026-11-21T13:15:00", "charge_kw": 5.4}]

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": plan_a}, "is_preliminary": True})
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_get_session.return_value = mock_session

        await coordinator.async_plan_ev_charging("car1")
        assert sensor.extra_state_attributes["is_preliminary"] is True

        # Tomt svar trots target_kwh > 0: behåll preliminär status för fortsatt omplanering och logga varning
        mock_resp.json = AsyncMock(return_value={"schedules": {}, "is_preliminary": False})
        with caplog.at_level(logging.WARNING):
            await coordinator.async_plan_ev_charging("car1")

        assert sensor.extra_state_attributes["is_preliminary"] is True
        assert "car1" in coordinator.ev_preliminary_cars
        assert "saknades eller var tom" in caplog.text

        # När target_kwh <= 0 (bilen är full) ska schemat rensas och is_preliminary bli False
        target_val["v"] = "0.0"
        await coordinator.async_plan_ev_charging("car1")
        assert sensor.extra_state_attributes["schedules"] == {}
        assert sensor.extra_state_attributes["is_preliminary"] is False
        assert "car1" not in coordinator.ev_preliminary_cars


async def test_ev_replan_two_cars_only_replaces_preliminary_car(mock_hass_instance):
    """Fall 4: Två bilar där bara en är preliminär -> omplanering ersätter bara den bilens schema."""
    from datetime import datetime, timezone
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    config = {
        "api_url": "http://test-api",
        "api_key": "123",
        CONF_EV_C1_NAME: "BMW",
        CONF_EV_C1_TARGET_KWH: "input_number.c1_target",
        "ev_c1_depart_time": "input_datetime.c1_depart",
        "ev_c1_max_kw": "input_number.c1_max_kw",
        "ev_c2_name": "Skoda",
        "ev_c2_target_kwh": "input_number.c2_target",
        "ev_c2_depart_time": "input_datetime.c2_depart",
        "ev_c2_max_kw": "input_number.c2_max_kw",
    }
    coordinator = BatteryOptimizerLightCoordinator(mock_hass_instance, config)
    coordinator.async_request_refresh = AsyncMock()
    sensor = BatteryLightEVScheduleSensor(coordinator)

    mock_hass_instance.states.get.side_effect = lambda entity_id: MagicMock(
        state={
            "input_number.c1_target": "20.0",
            "input_datetime.c1_depart": "07:30:00",
            "input_number.c1_max_kw": "5.4",
            "input_number.c2_target": "15.0",
            "input_datetime.c2_depart": "18:00:00",
            "input_number.c2_max_kw": "11.0",
        }.get(entity_id, "unknown")
    )

    bmw_prelim = [{"start": "2026-11-21T12:45:00", "end": "2026-11-21T13:15:00", "charge_kw": 5.4}]
    bmw_sharp = [{"start": "2026-11-22T04:00:00", "end": "2026-11-22T07:15:00", "charge_kw": 5.4}]
    skoda_sharp = [{"start": "2026-11-21T14:00:00", "end": "2026-11-21T15:30:00", "charge_kw": 11.0}]

    patch_session = "custom_components.battery_optimizer_light_plus.coordinator.async_get_clientsession"
    with patch(patch_session) as mock_get_session:
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_get_session.return_value = mock_session

        # Bil 1 får preliminärt schema, Bil 2 får skarpt schema
        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": bmw_prelim}, "is_preliminary": True})
        await coordinator.async_plan_ev_charging("car1")

        mock_resp.json = AsyncMock(return_value={"schedules": {"Skoda": skoda_sharp}, "is_preliminary": False})
        await coordinator.async_plan_ev_charging("car2")

        assert coordinator.ev_preliminary_cars == {"car1"}

        captured_cb = None

        def fake_track_time(hass, action, **kwargs):
            nonlocal captured_cb
            captured_cb = action
            return MagicMock()

        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.async_track_time_change",
            side_effect=fake_track_time,
        ):
            coordinator.setup_timer()

        mock_session.post.reset_mock()
        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": bmw_sharp}, "is_preliminary": False})
        with patch(
            "custom_components.battery_optimizer_light_plus.coordinator.dt_util.as_local",
            side_effect=lambda dt: dt,
        ):
            await captured_cb(datetime(2026, 11, 21, 13, 15, 30, tzinfo=timezone.utc))

        mock_session.post.assert_called_once()
        _, kwargs = mock_session.post.call_args
        assert [c["id"] for c in kwargs["json"]["cars"]] == ["BMW"]
        assert sensor.extra_state_attributes["schedules"] == {"BMW": bmw_sharp, "Skoda": skoda_sharp}
        assert sensor.extra_state_attributes["is_preliminary"] is False


async def test_ev_reload_with_cable_connected_fetches_new_plan_and_updates_sensor(mock_hass_instance):
    """Fall 5: Omstart/reload med inkopplad kabel begär ny plan och sensorn visar den."""
    from custom_components.battery_optimizer_light_plus import async_setup_entry
    from custom_components.battery_optimizer_light_plus.coordinator import BatteryOptimizerLightCoordinator
    from custom_components.battery_optimizer_light_plus.sensor import BatteryLightEVScheduleSensor

    entry = MagicMock()
    entry.entry_id = "ev_reload_entry"
    entry.data = {
        "api_url": "http://test-api",
        "api_key": "12345",
        CONF_EV_C1_NAME: "BMW",
        "ev_c1_cable_connected": "binary_sensor.cable",
        "ev_c1_target_kwh": "input_number.target",
        "ev_c1_depart_time": "input_datetime.depart",
        "ev_c1_max_kw": "input_number.max_kw",
    }
    entry.options = {}

    state_map = {
        "binary_sensor.cable": "on",
        "input_number.target": "20.0",
        "input_datetime.depart": "07:30:00",
        "input_number.max_kw": "5.4",
    }
    mock_hass_instance.states.get.side_effect = lambda e: (
        MagicMock(state=state_map[e]) if e in state_map else None
    )

    scheduled_coros = []
    mock_hass_instance.async_create_task.side_effect = lambda coro: scheduled_coros.append(coro)

    real_coord = BatteryOptimizerLightCoordinator(mock_hass_instance, dict(entry.data))
    real_coord.async_config_entry_first_refresh = AsyncMock()
    real_coord.setup_timer = MagicMock()
    real_coord.data = {}
    sensor = BatteryLightEVScheduleSensor(real_coord)

    new_plan = [{"start": "2026-11-22T04:00:00", "end": "2026-11-22T07:15:00", "charge_kw": 5.4}]
    pkg = "custom_components.battery_optimizer_light_plus"
    with patch(f"{pkg}.async_get_integration", new_callable=AsyncMock) as gi, \
            patch(f"{pkg}.BatteryOptimizerLightCoordinator", return_value=real_coord), \
            patch(f"{pkg}.async_track_state_change_event", return_value=MagicMock()), \
            patch(f"{pkg}.coordinator.async_get_clientsession") as mock_get_session:
        gi.return_value = MagicMock()
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"schedules": {"BMW": new_plan}, "is_preliminary": False})
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_get_session.return_value = mock_session

        assert await async_setup_entry(mock_hass_instance, entry) is True
        assert len(scheduled_coros) == 1
        await scheduled_coros[0]

    assert sensor.extra_state_attributes == {"schedules": {"BMW": new_plan}, "is_preliminary": False}





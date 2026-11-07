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

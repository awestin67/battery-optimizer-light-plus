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
        assert coordinator.ev_schedules["Testbil"] == []

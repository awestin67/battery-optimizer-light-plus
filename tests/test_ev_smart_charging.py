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
from custom_components.battery_optimizer_light_plus.const import (
    CONF_EV_C1_NAME,
    CONF_EV_C1_TARGET_KWH,
)
from custom_components.battery_optimizer_light_plus.config_flow import BatteryOptimizerLightOptionsFlow

pytestmark = pytest.mark.asyncio

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

async def test_plan_ev_charging_service_call():
    """Test the plan_ev_charging service directly."""
    # TODO: Skapa integrationen och anropa tjänsten "plan_ev_charging"
    # Mocka post-anropet till /api/ev/plan och verifiera att payload innehåller rätt data
    pass

async def test_ev_cable_connected_trigger():
    """Test that ev_cable_connected triggers the plan_ev_charging service."""
    # TODO: Sätt state på CONF_EV_C1_CABLE_CONNECTED till "on" och verifiera
    # att _on_ev_connected anropar async_plan_ev_charging("car1")
    pass

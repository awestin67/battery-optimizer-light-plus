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
from unittest.mock import MagicMock, AsyncMock
from custom_components.battery_optimizer_light_plus.switch import async_setup_entry, SonnenManualModeSwitch
from custom_components.battery_optimizer_light_plus.const import DOMAIN, CONF_BATTERY_TYPE, BATTERY_TYPE_SONNEN

@pytest.mark.asyncio
async def test_switch_setup_entry():
    """Testar att switch-plattformen skapas för Sonnen."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.data = {CONF_BATTERY_TYPE: BATTERY_TYPE_SONNEN}

    coordinator = MagicMock()
    hass.data = {DOMAIN: {"test_id": coordinator}}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], SonnenManualModeSwitch)

def test_switch_device_info():
    """Testar att enhetsinformationen knyts korrekt till huvudintegrationen."""
    main_coordinator = MagicMock()
    main_coordinator.api_key = "12345"
    sonnen_coord = MagicMock()
    switch = SonnenManualModeSwitch(main_coordinator, sonnen_coord)

    assert switch.device_info["identifiers"] == {(DOMAIN, "12345")}
    assert switch.device_info["name"] == "Battery Optimizer Light Plus"

@pytest.mark.asyncio
async def test_switch_setup_entry_not_sonnen():
    """Testar att ingen switch skapas om batteriet inte är Sonnen."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.data = {CONF_BATTERY_TYPE: "huawei"}

    coordinator = MagicMock()
    hass.data = {DOMAIN: {"test_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

def test_switch_properties():
    """Testar att switchen visar rätt läge baserat på API-data."""
    main_coordinator = MagicMock()
    main_coordinator.api_key = "12345"
    sonnen_coord = MagicMock()

    switch = SonnenManualModeSwitch(main_coordinator, sonnen_coord)

    sonnen_coord.data = {"OperatingMode": "1"}
    assert switch.is_on is True

    sonnen_coord.data = {"OperatingMode": "2"}
    assert switch.is_on is False

    sonnen_coord.data = {}
    assert switch.is_on is False
    sonnen_coord.data = None
    assert switch.is_on is False

@pytest.mark.asyncio
async def test_switch_turn_on_off():
    """Testar att knapptryckningar skickar rätt API-anrop."""
    main_coordinator = MagicMock()
    main_coordinator.battery_api._api.async_set_operating_mode = AsyncMock()
    sonnen_coord = MagicMock()
    sonnen_coord.async_request_refresh = AsyncMock()
    switch = SonnenManualModeSwitch(main_coordinator, sonnen_coord)

    await switch.async_turn_on()
    main_coordinator.battery_api._api.async_set_operating_mode.assert_called_with(1)

    await switch.async_turn_off()
    main_coordinator.battery_api._api.async_set_operating_mode.assert_called_with(2)
    assert sonnen_coord.async_request_refresh.call_count == 2

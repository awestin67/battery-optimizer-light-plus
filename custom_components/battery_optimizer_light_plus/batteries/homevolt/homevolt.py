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

import logging
from datetime import timedelta
import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class HomevoltBattery(BatteryApi):
    """Adapter for a Homevolt battery via the homevolt_local integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        soc_entity: str,
        grid_entity: str | None,
        battery_power_entity: str,
        load_entity: str | None,
        status_entity: str | None,
    ):
        self._hass = hass
        self._device_id = device_id
        self._soc_entity = soc_entity
        self._grid_entity = grid_entity
        self._battery_power_entity = battery_power_entity
        self._load_entity = load_entity
        self._status_entity = status_entity

    async def get_current_soc(self) -> float | None:
        """Get the current state of charge."""
        state = self._hass.states.get(self._soc_entity)
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            try:
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    async def get_battery_power(self) -> float | None:
        """Get the current battery power in Watts."""
        state = self._hass.states.get(self._battery_power_entity)
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            try:
                # Assuming Homevolt: positive=discharging, negative=charging
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    async def get_grid_power(self) -> float | None:
        """Get the current grid power in Watts."""
        if not self._grid_entity:
            return None
        state = self._hass.states.get(self._grid_entity)
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            try:
                # Assuming Homevolt: positive=import, negative=export
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    async def get_virtual_load(self) -> float | None:
        """Get the current house load in Watts."""
        if not self._load_entity:
            return None
        state = self._hass.states.get(self._load_entity)
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            try:
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    async def get_status_text(self) -> str | None:
        """Get the current battery status text."""
        if not self._status_entity:
            return None
        state = self._hass.states.get(self._status_entity)
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            return state.state
        return None

    async def apply_action(self, action: str, target_kw: float = 0):
        """Apply a given action to the battery."""
        _LOGGER.debug(f"Applying action to Homevolt: {action} with {target_kw} kW")

        action_upper = action.upper()
        target_w = int(target_kw * 1000)

        if action_upper in ["CHARGE", "DISCHARGE"]:
            mode = action_upper.lower()
            setpoint = abs(target_w)
        elif action_upper == "HOLD":
            mode = "manual"
            setpoint = 0
        elif action_upper == "IDLE":
            mode = "auto"
            setpoint = 0
        else:
            _LOGGER.warning(f"Unknown action for Homevolt: {action}")
            return

        now = dt_util.now()
        end_time = now + timedelta(minutes=10)

        service_data = {
            "device_id": self._device_id,
            "mode": mode,
            "setpoint": setpoint,
            "from_time": now.isoformat(),
            "to_time": end_time.isoformat(),
        }

        _LOGGER.info(f"Calling homevolt_local.add_schedule with: {service_data}")
        try:
            await self._hass.services.async_call(
                "homevolt_local", "add_schedule", service_data, blocking=True
            )
        except Exception as e:
            _LOGGER.error(f"Failed to call homevolt_local.add_schedule service: {e}")

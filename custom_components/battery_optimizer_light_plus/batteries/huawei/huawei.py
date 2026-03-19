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
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class HuaweiBattery(BatteryApi):
    """A class to interact with the Huawei battery."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        working_mode_entity: str,
        soc_entity: str,
        device_status_entity: str | None = None
    ):
        """Initialize the HuaweiBattery object."""
        self._hass = hass
        self._device_id = device_id
        self._working_mode_entity = working_mode_entity
        self._soc_entity = soc_entity
        self._device_status_entity = device_status_entity

    async def get_current_soc(self) -> float | None:
        """Get the battery's state of charge (SoC)."""
        soc_state = self._hass.states.get(self._soc_entity)
        if soc_state and soc_state.state not in ("unknown", "unavailable"):
            try:
                return float(soc_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid SoC value: {soc_state.state}")
                return None
        return None

    async def get_status_text(self) -> str | None:
        """Hämtar enhetsstatus för automatisk konfiguration i PeakGuard."""
        if self._device_status_entity:
            state = self._hass.states.get(self._device_status_entity)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return str(state.state)
        return None

    async def async_set_charge(self, power: int):
        """Set the battery to charge with a specific power."""
        await self._hass.services.async_call(
            "huawei_solar", "forcible_charge",
            {"device_id": self._device_id, "power": power, "duration": 60}
        )

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)

        if action == "CHARGE":
            await self.async_set_charge(power_w)
        elif action == "DISCHARGE":
            await self.async_set_discharge(power_w)
        elif action == "HOLD":
            await self.async_hold()
        elif action == "IDLE":
            await self.async_set_idle()

    async def async_set_discharge(self, power: int):
        """Set the battery to discharge with a specific power."""
        await self._hass.services.async_call(
            "huawei_solar", "forcible_discharge",
            {"device_id": self._device_id, "power": power, "duration": 60}
        )

    async def async_set_idle(self):
        """Set the battery to idle (auto/self-consumption)."""
        await self._hass.services.async_call(
            "huawei_solar", "stop_forcible_charge", {"device_id": self._device_id}
        )
        await self._hass.services.async_call(
            "select", "select_option", {"entity_id": self._working_mode_entity, "option": "maximise_self_consumption"}
        )

    async def async_hold(self):
        """Set the battery to hold (manual mode, 0W)."""
        await self._hass.services.async_call(
            "huawei_solar", "stop_forcible_charge", {"device_id": self._device_id}
        )
        await self._hass.services.async_call(
            "select", "select_option", {"entity_id": self._working_mode_entity, "option": "fixed_charge_discharge"}
        )

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
from homeassistant.exceptions import ServiceNotFound
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class HuaweiBattery(BatteryApi):
    """A class to interact with the Huawei battery."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        soc_entity: str,
        device_status_entity: str | None = None
    ):
        """Initialize the HuaweiBattery object."""
        self._hass = hass
        self._device_id = device_id
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

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        action_upper = action.upper()

        try:
            if action_upper == "CHARGE":
                await self._hass.services.async_call(
                    "huawei_solar",
                    "forcible_charge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
                    blocking=True,
                )
            elif action_upper == "DISCHARGE":
                await self._hass.services.async_call(
                    "huawei_solar",
                    "forcible_discharge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
                    blocking=True,
                )
            elif action_upper == "HOLD":
                # Simulerar ett HOLD genom att tvinga en extremt låg laddning (1 W).
                # cv.positive_int avvisar 0 W, så 1 W håller batteriet låst utan att dra ström.
                # Duration sätts till maxtillåtna 1440 min (24h) tills vi aktivt stoppar den.
                await self._hass.services.async_call(
                    "huawei_solar",
                    "forcible_charge",
                    {"device_id": self._device_id, "power": 1, "duration": 1440},
                    blocking=True
                )
            elif action_upper == "IDLE":
                await self._hass.services.async_call(
                    "huawei_solar", "stop_forcible_charge", {"device_id": self._device_id}, blocking=True
                )
            else:
                _LOGGER.warning(f"Unknown action for Huawei: {action}")
        except ServiceNotFound as e:
            _LOGGER.warning(
                "Huawei service not found: %s. The 'huawei_solar' integration might be starting up. "
                "Please check your setup.", e
            )
        except Exception as e:
            _LOGGER.error("An unexpected error occurred while applying Huawei action '%s': %s",
            action,
            e,
            exc_info=True,
            )

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


"""Sonnen Battery abstraction."""
import logging
import asyncio
from .api import SonnenAPI

from ..base import BatteryApi
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class SonnenBattery(BatteryApi):
    """Klass för att interagera med ett Sonnen-batteri."""

    def __init__(self, hass: HomeAssistant, api: SonnenAPI, soc_entity: str):
        """Initierar SonnenBattery."""
        self._hass = hass
        self._api = api
        self._soc_entity = soc_entity

    async def get_current_soc(self) -> float | None:
        """Hämtar aktuell laddningsgrad (SoC) i procent."""
        try:
            status_data = await self._api.async_get_status()
            if status_data and "USOC" in status_data:
                return int(status_data["USOC"])
        except Exception as e:
            _LOGGER.warning("Could not fetch SoC from Sonnen API, falling back to sensor: %s", e)
            soc_state = self._hass.states.get(self._soc_entity)
            if soc_state and soc_state.state not in ("unknown", "unavailable"):
                try:
                    return float(soc_state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Invalid SoC value: {soc_state.state}")
                    return None
        return None

    async def async_set_charge(self, power: int):
        """Sätter batteriet i laddningsläge med angiven effekt i watt."""
        _LOGGER.debug("Sätter laddning till %s W", power)
        return await self._api.async_charge(power)

    async def async_set_discharge(self, power: int):
        """Sätter batteriet i urladdningsläge med angiven effekt i watt."""
        _LOGGER.debug("Sätter urladdning till %s W", power)
        return await self._api.async_discharge(power)

    async def async_set_idle(self):
        """Sätter batteriet i viloläge (varken laddar eller laddar ur)."""
        _LOGGER.debug("Sätter batteriet i viloläge")
        # För att sätta i viloläge, skickar vi laddnings- och urladdningskommandon med 0 W
        charge_ok = await self.async_set_charge(0)
        discharge_ok = await self.async_set_discharge(0)
        return charge_ok and discharge_ok

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)

        if action == "CHARGE":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            await self.async_set_charge(power_w)
        elif action == "DISCHARGE":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            await self.async_set_discharge(power_w)
        elif action == "HOLD":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            await self.async_set_idle()
        elif action == "IDLE":
            await self._api.async_set_operating_mode(2)

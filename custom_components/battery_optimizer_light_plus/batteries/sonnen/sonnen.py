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
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import SonnenAPI

from ..base import BatteryApi
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class SonnenBattery(BatteryApi):
    """Klass för att interagera med ett Sonnen-batteri."""

    def __init__(self, hass: HomeAssistant, api: SonnenAPI, soc_entity: str | None = None):
        """Initierar SonnenBattery."""
        self._hass = hass
        self._api = api
        self._soc_entity = soc_entity
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="Sonnen Local API",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self):
        """Hämtar data från Sonnen lokalt."""
        try:
            return await self._api.async_get_status()
        except Exception as e:
            raise UpdateFailed(f"Kunde inte hämta Sonnen data: {e}") from e

    async def get_current_soc(self) -> float | None:
        """Hämtar aktuell laddningsgrad (SoC) i procent."""
        data = self.coordinator.data
        if data and "USOC" in data:
            return float(data["USOC"])

        if self._soc_entity:
            soc_state = self._hass.states.get(self._soc_entity)
            if soc_state and soc_state.state not in ("unknown", "unavailable", None):
                try:
                    return float(soc_state.state)
                except ValueError:
                    pass
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
    async def get_virtual_load(self) -> float | None:
        data = self.coordinator.data
        if data and "Consumption_W" in data and "Production_W" in data:
            return float(data["Consumption_W"]) - float(data["Production_W"])
        return None

    async def get_battery_power(self) -> float | None:
        data = self.coordinator.data
        if data and "Pac_total_W" in data:
            return float(data["Pac_total_W"])
        return None

    async def get_grid_power(self) -> float | None:
        data = self.coordinator.data
        if data and "GridFeedIn_W" in data:
            return float(data["GridFeedIn_W"])
        return None

    async def get_status_text(self) -> str | None:
        data = self.coordinator.data
        if data and "SystemStatus" in data:
            return str(data["SystemStatus"])
        return None

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

try:
    from awesomeversion import AwesomeVersion
except ImportError:
    class AwesomeVersion:  # type: ignore[no-redef]
        """Fallback-implementation om awesomeversion saknas."""

        def __init__(self, version: str):
            self.version = str(version).strip()

        def __ge__(self, other):
            if isinstance(other, AwesomeVersion):
                other_ver = other.version
            else:
                other_ver = str(other).strip()

            def _parse_tuple(v: str):
                parts = []
                for p in v.split("."):
                    num = ""
                    for ch in p:
                        if ch.isdigit():
                            num += ch
                        else:
                            break
                    parts.append(int(num) if num else 0)
                return tuple(parts)

            return _parse_tuple(self.version) >= _parse_tuple(other_ver)

_LOGGER = logging.getLogger(__name__)

class SonnenBattery(BatteryApi):
    """Klass för att interagera med ett Sonnen-batteri."""

    def __init__(self, hass: HomeAssistant, api: SonnenAPI, soc_entity: str | None = None):
        """Initierar SonnenBattery."""
        self._hass = hass
        self._api = api
        self._soc_entity = soc_entity
        self._software_version: str | None = None
        self._is_modern_ems: bool = False
        self._last_site_limits: dict | None = None
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="Sonnen Local API",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=10),
        )

    @property
    def software_version(self) -> str | None:
        """Firmware-version för Sonnen."""
        return self._software_version

    @property
    def is_modern_ems(self) -> bool:
        """Indikerar om batteriet stödjer moderna EMS Site Limits (>= 1.35.14)."""
        return self._is_modern_ems

    def _process_software_version(self, sw: str | None) -> bool:
        """Tolkar mjukvaruversion och sätter is_modern_ems."""
        if not sw:
            return False
        self._software_version = str(sw).strip()
        try:
            self._is_modern_ems = AwesomeVersion(self._software_version) >= AwesomeVersion("1.35.14")
            _LOGGER.info(
                "Sonnen firmware version detected: %s (Modern EMS: %s)",
                self._software_version,
                self._is_modern_ems,
            )
            return True
        except Exception as err:
            _LOGGER.warning("Kunde inte parsa Sonnen version '%s': %s", sw, err)
            return False

    async def async_init_version(self):
        """Detekterar Sonnen firmware och aktiverar EMS om >= 1.35.14."""
        sw = await self._api.async_get_software_version()
        if sw:
            self._process_software_version(sw)
        else:
            _LOGGER.warning(
                "Sonnen firmware-version kunde inte läsas av från batteriets API vid start. "
                "Provar igen vid nästa statusläsning."
            )

    async def _async_update_data(self):
        """Hämtar data från Sonnen lokalt."""
        if self._software_version is None:
            await self.async_init_version()

        try:
            raw_status = await self._api.async_get_status()
            status_data = dict(raw_status) if isinstance(raw_status, dict) else {}
            if self._software_version is None and "DE_Software" in status_data:
                self._process_software_version(status_data["DE_Software"])

            if self._is_modern_ems:
                try:
                    site_limits = await self._api.async_get_site_limits()
                    if site_limits:
                        status_data["site_limits"] = site_limits
                except Exception as limits_err:
                    _LOGGER.debug("Kunde inte hämta aktiva site limits från Sonnen: %s", limits_err)
            return status_data
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

    async def apply_action(
        self, action: str, target_kw: float = 0.0, sonnen_site_limits: dict | None = None, **kwargs
    ):
        """Verkställer ett beslut från molnet eller lokalt."""
        if sonnen_site_limits is not None:
            self._last_site_limits = dict(sonnen_site_limits)
            if action == "HOLD":
                sonnen_site_limits["p_bess_inv_max_export_limit"] = 0
                self._last_site_limits["p_bess_inv_max_export_limit"] = 0
            elif action == "IDLE":
                sonnen_site_limits.pop("p_bess_inv_max_export_limit", None)
                self._last_site_limits.pop("p_bess_inv_max_export_limit", None)
        elif self._last_site_limits is not None and action in ("HOLD", "IDLE"):
            sonnen_site_limits = dict(self._last_site_limits)
            if action == "HOLD":
                sonnen_site_limits["p_bess_inv_max_export_limit"] = 0
                self._last_site_limits["p_bess_inv_max_export_limit"] = 0
            elif action == "IDLE":
                sonnen_site_limits.pop("p_bess_inv_max_export_limit", None)
                self._last_site_limits.pop("p_bess_inv_max_export_limit", None)

        # Använd modern EMS för HOLD och IDLE när gränser finns
        if self._is_modern_ems and sonnen_site_limits is not None and action in ("HOLD", "IDLE"):
            _LOGGER.debug("Verkställer beslut via Sonnen Site Limits (%s): %s", action, sonnen_site_limits)

            # Säkerställ att batteriet ligger kvar i Self-consumption (Mode 2)
            await self._api.async_set_operating_mode(2)

            limits_payload = dict(sonnen_site_limits)
            if limits_payload.get("duration") in ("PT90S", None):
                limits_payload["duration"] = "PT10M"

            # Skicka gränserna direkt till PUT /api/v2/site/limits
            success = await self._api.async_set_site_limits(limits_payload)
            if success:
                return True
            _LOGGER.warning("Misslyckades att sätta Site Limits, provar fallback...")

        # För aktiv CHARGE och DISCHARGE (samt fallback för HOLD/IDLE) krävs manuellt driftläge (Mode 1)
        power_w = int(target_kw * 1000)

        if action == "CHARGE":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            return await self.async_set_charge(power_w)
        elif action == "DISCHARGE":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            return await self.async_set_discharge(power_w)
        elif action == "HOLD":
            await self._api.async_set_operating_mode(1)
            await asyncio.sleep(0.5)
            return await self.async_set_idle()
        elif action == "IDLE":
            return await self._api.async_set_operating_mode(2)
    async def get_virtual_load(self) -> float | None:
        data = self.coordinator.data
        if data and "Consumption_W" in data and "Production_W" in data:
            try:
                return float(data["Consumption_W"]) - float(data["Production_W"])
            except (ValueError, TypeError):
                pass
        return None

    async def get_solar_power(self) -> float | None:
        """Hämtar solproduktion i Watt."""
        data = self.coordinator.data
        if data and "Production_W" in data:
            try:
                return float(data["Production_W"])
            except (ValueError, TypeError):
                pass
        return None

    async def get_battery_power(self) -> float | None:
        data = self.coordinator.data
        if data and "Pac_total_W" in data:
            try:
                return float(data["Pac_total_W"])
            except (ValueError, TypeError):
                pass
        return None

    async def get_grid_power(self) -> float | None:
        data = self.coordinator.data
        if data and "GridFeedIn_W" in data:
            # Sonnen: Positiv = Export. PeakGuard förväntar sig Negativ = Export.
            try:
                return -float(data["GridFeedIn_W"])
            except (ValueError, TypeError):
                pass
        return None

    async def get_status_text(self) -> str | None:
        data = self.coordinator.data
        if data and "SystemStatus" in data:
            return str(data["SystemStatus"])
        return None

    async def is_offgrid(self) -> bool:
        """Kollar offgrid-status för Sonnen."""
        data = self.coordinator.data
        if data and "SystemStatus" in data:
            system_status = data.get("SystemStatus")
            if system_status and str(system_status).strip().lower() != "ongrid":
                return True

        # Fallback to generic offgrid sensor logic
        return await super().is_offgrid()

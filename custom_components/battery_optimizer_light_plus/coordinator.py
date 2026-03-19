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
import asyncio
from datetime import timedelta
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .battery_factory import create_battery_api

_LOGGER = logging.getLogger(__name__)

class BatteryOptimizerLightCoordinator(DataUpdateCoordinator):
    """Hanterar kommunikationen för Light-versionen."""

    def __init__(self, hass, config, version="0.0.0"):
        super().__init__(
            hass,
            _LOGGER,
            name="Battery Optimizer Light Plus",
            update_interval=timedelta(minutes=5),
        )
        self.api_url = f"{config['api_url'].rstrip('/')}/signal"
        self.api_key = config['api_key']
        self.version = version
        self.battery_api = create_battery_api(hass, config)

        # --- DEV OVERRIDE (Avkommentera vid lokal utveckling) ---
        # self.api_url = "https://battery-light-development.up.railway.app/signal"

        # Säkerhetsvarning om vi kör mot dev
        if "development" in self.api_url:
            _LOGGER.warning("⚠️ VARNING: Integrationen körs mot DEVELOPMENT-backend: %s", self.api_url)

        self.consumption_forecast_entity = config.get("consumption_forecast_sensor")

    async def _async_update_data(self):
        """Körs var 5:e minut."""
        # 1. Hämta SOC
        soc = await self.battery_api.get_current_soc()

        if soc is None:
            raise UpdateFailed("Could not retrieve SoC from battery.")

        is_solar_override = False
        if hasattr(self, "peak_guard") and self.peak_guard:
            is_solar_override = self.peak_guard.is_solar_override

        # 3. Hämta förbrukningsprognos (Valfritt)
        consumption_forecast = None
        if self.consumption_forecast_entity:
            forecast_state = self.hass.states.get(self.consumption_forecast_entity)
            if forecast_state and forecast_state.state not in ["unknown", "unavailable"]:
                try:
                    consumption_forecast = float(forecast_state.state)
                except ValueError:
                    pass  # Ignorera om värdet inte är ett tal

        # 2. Payload (Endast det backend behöver)
        payload = {
            "api_key": self.api_key,
            "soc": soc,
            "is_solar_override": is_solar_override,
            "consumption_forecast_kwh": consumption_forecast,
            "ha_version": self.version
        }

        _LOGGER.debug(f"Light-Request: {payload}")

        # Retry-mekanism (3 försök)
        session = async_get_clientsession(self.hass)
        for attempt in range(3):
            try:
                async with session.post(
                    self.api_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 401:
                        text = await response.text()
                        raise UpdateFailed(f"Authentication failed: {text}")

                    if response.status != 200:
                        text = await response.text()
                        raise UpdateFailed(f"Server {response.status}: {text}")

                    data = await response.json()

                    action = data.get("action", "IDLE")
                    target_kw = data.get("target_power_kw", 0.0)

                    # Låt batterihanteraren verkställa beslutet, om inte PeakGuard har tagit över lokalt
                    if not is_solar_override and not (hasattr(self, "peak_guard") and self.peak_guard.is_active):
                        await self.battery_api.apply_action(action, target_kw)

                    return data

            except Exception as err:
                if isinstance(err, UpdateFailed) and "Authentication failed" in str(err):
                    raise

                # Get a more descriptive error message
                error_detail = str(err)
                if not error_detail:
                    # Fallback for exceptions with empty string representation
                    error_detail = repr(err) # Use repr for more technical detail if str is empty

                if attempt < 2:
                    _LOGGER.warning(
                        "Connection attempt %d failed with %s: %s. Retrying in 5s...",
                        attempt + 1,
                        type(err).__name__,
                        error_detail,
                    )
                    await asyncio.sleep(5)
                else:
                    _LOGGER.exception("Light-Error after 3 attempts")
                    raise UpdateFailed(
                        f"Connection error after 3 attempts: {type(err).__name__}: {error_detail}"
                    ) from err

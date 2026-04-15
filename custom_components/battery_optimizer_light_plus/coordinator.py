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
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
import homeassistant.util.dt as dt_util
from .battery_factory import create_battery_api

_LOGGER = logging.getLogger(__name__)

class BatteryOptimizerLightCoordinator(DataUpdateCoordinator):
    """Hanterar kommunikationen för Light-versionen."""

    def __init__(self, hass, config, version="0.0.0"):
        super().__init__(
            hass,
            _LOGGER,
            name="Battery Optimizer Light Plus",
        )
        self.api_url = f"{config['api_url'].rstrip('/')}/signal"
        self.api_key = config['api_key']
        self.version = version
        self.config = config
        self.battery_api = create_battery_api(hass, config)

        # --- DEV OVERRIDE (Avkommentera vid lokal utveckling) ---
        # self.api_url = "https://battery-light-development.up.railway.app/signal"

        # Säkerhetsvarning om vi kör mot dev
        if "development" in self.api_url:
            _LOGGER.warning("⚠️ VARNING: Integrationen körs mot DEVELOPMENT-backend: %s", self.api_url)

        self.consumption_forecast_entity = config.get("consumption_forecast_sensor")
        self.unsub_timer = None
        self.current_load_w = None

    def setup_timer(self):
        """Startar schemaläggaren.

        Anropas efter lyckad första uppdatering för att undvika minnesläckor vid setup-fel.
        """
        async def _update_interval(now):
            await self.async_request_refresh()

        self.unsub_timer = async_track_time_change(
            self.hass,
            _update_interval,
            minute=list(range(0, 60, 5)),
            second=30
        )

    async def _async_update_data(self):
        """Körs var 5:e minut."""
        # 1. Hämta SOC
        soc = await self.battery_api.get_current_soc()

        if soc is None:
            # Om vi inte kan läsa SoC vid uppstart, sätter vi den till 0.0 temporärt
            # så att vi ändå kan hämta ett beslut från molnet och släppa manuellt läge.
            _LOGGER.warning("Could not retrieve SoC from battery. Using 0.0 temporarily to fetch cloud action.")
            soc = 0.0

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

        # 4. Hämta aktuell förbrukning / Huslast (kW)
        current_consumption_kw = 0.0
        current_load_w = None

        # --- PRIO 1: Beräkning av formeln (Högsta prio via intern batterilogik) ---
        # Huawei räknar t.ex. ut Grid + Inverter Active Power här för att inkludera solproduktion
        if hasattr(self.battery_api, "get_calculated_consumption"):
            current_load_w = await self.battery_api.get_calculated_consumption()

        # Inbyggd genväg för Sonnen (Sonnen Husförbrukning / Consumption_W)
        if current_load_w is None and hasattr(self.battery_api, "coordinator"):
            data = getattr(self.battery_api.coordinator, "data", None)
            if data and "Consumption_W" in data:
                try:
                    current_load_w = float(data["Consumption_W"])
                except (ValueError, TypeError):
                    pass

        # --- PRIO 2: Användarens konfigurerade virtuella last-sensor ---
        if current_load_w is None:
            virtual_load_id = self.config.get("virtual_load_sensor")
            if virtual_load_id:
                state = self.hass.states.get(virtual_load_id)
                if state and state.state not in ["unknown", "unavailable"]:
                    try:
                        current_load_w = float(state.state)
                    except ValueError:
                        pass

        # --- PRIO 3: Beräkning via generiska HA-sensorer (Grid + Batteri) ---
        # Används om ingen annan metod finns. Observera att detta missar solproduktion.
        if current_load_w is None:
            grid_id = self.config.get("grid_sensor")
            bat_id = self.config.get("battery_power_sensor")

            if grid_id or bat_id:
                g_val = None
                b_val = None

                if grid_id:
                    grid_state = self.hass.states.get(grid_id)
                    if grid_state and grid_state.state not in ["unknown", "unavailable"]:
                        try:
                            g_val = float(grid_state.state)
                            if self.config.get("grid_sensor_invert", False):
                                g_val = -g_val
                        except ValueError:
                            pass

                if bat_id:
                    bat_state = self.hass.states.get(bat_id)
                    if bat_state and bat_state.state not in ["unknown", "unavailable"]:
                        try:
                            b_val = float(bat_state.state)
                            if self.config.get("battery_sensor_invert", False):
                                b_val = -b_val
                        except ValueError:
                            pass

                if g_val is not None or b_val is not None:
                    current_load_w = (g_val or 0.0) + (b_val or 0.0)

        # --- PRIO 4: Fallback till API-specifika sensorer (t.ex. Huawei EMMA/SDongle) ---
        if current_load_w is None and hasattr(self.battery_api, "get_house_consumption"):
            current_load_w = await self.battery_api.get_house_consumption()

        if current_load_w is not None:
            # Ett hus kan inte ha negativ förbrukning. Negativa värden beror oftast på
            # mätfel eller fördröjningar mellan sensorernas uppdateringar.
            if current_load_w < 0:
                current_load_w = 0.0
            current_consumption_kw = round(current_load_w / 1000.0, 3)
        else:
            _LOGGER.debug("Husförbrukning kunde inte beräknas (sensorer under uppstart?). Skickar 0.0 kW till molnet.")

        self.current_load_w = current_load_w

        # 5. Payload (Endast det backend behöver)
        payload = {
            "api_key": self.api_key,
            "soc": soc,
            "is_solar_override": is_solar_override,
            "consumption_forecast_kwh": consumption_forecast,
            "ha_version": self.version,
            "current_consumption_kw": current_consumption_kw
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

                    # --- Hämta graf-data ---
                    try:
                        history_hours = int(self.config.get("graph_history_hours", 24))
                        base_api_url = self.config.get("api_url", "").rstrip("/")
                        graph_url = f"{base_api_url}/ha_graph_data?history_hours={history_hours}"

                        async with session.get(
                            graph_url, headers={"X-API-Key": self.api_key}, timeout=aiohttp.ClientTimeout(total=30)
                        ) as graph_response:
                            if graph_response.status == 200:
                                data["graph_data"] = await graph_response.json()
                            else:
                                _LOGGER.debug("Kunde inte hämta grafdata. Status: %s", graph_response.status)
                    except Exception as e:
                        _LOGGER.debug("Fel vid hämtning av grafdata: %s", e)

                    action = data.get("action", "IDLE")

                    try:
                        target_kw = float(data.get("target_power_kw", 0.0))
                        # Om backend skickar värdet i Watt istället för kW (t.ex. 1800)
                        if target_kw > 100:
                            target_kw = target_kw / 1000.0
                    except (ValueError, TypeError):
                        target_kw = 0.0

                    # Låt batterihanteraren verkställa beslutet, om inte PeakGuard har tagit över lokalt
                    if not is_solar_override and not (hasattr(self, "peak_guard") and self.peak_guard.is_active):
                        await self.battery_api.apply_action(action, target_kw)

                    # --- Hämta AI Sammanfattning (Endast vid uppstart och 04:15) ---
                    now = dt_util.now()
                    should_fetch_ai = False

                    if not self.data or "ai_summary" not in self.data:
                        should_fetch_ai = True
                    # Vi pollar var 5:e minut, så vi kollar om vi befinner oss runt 04:15
                    elif now.hour == 4 and 15 <= now.minute < 20:
                        last_fetch = getattr(self, "_last_ai_fetch_day", None)
                        if last_fetch != now.date():
                            should_fetch_ai = True

                    default_ai_text = "Ingen AI-sammanfattning tillgänglig ännu."
                    fallback_ai_text = self.data.get("ai_summary", default_ai_text) if self.data else default_ai_text

                    if should_fetch_ai:
                        try:
                            base_api_url = self.config.get("api_url", "").rstrip("/")
                            ai_url = f"{base_api_url}/ha_ai_summary"
                            async with session.get(
                                ai_url,
                                headers={"x-api-key": self.api_key},
                                timeout=10
                            ) as ai_resp:
                                if ai_resp.status == 200:
                                    ai_data = await ai_resp.json()
                                    data["ai_summary"] = ai_data.get("ai_summary", default_ai_text)
                                    self._last_ai_fetch_day = now.date()
                                else:
                                    data["ai_summary"] = fallback_ai_text
                        except Exception as e:
                            _LOGGER.debug(f"Kunde inte hämta AI-sammanfattning: {e}")
                            data["ai_summary"] = fallback_ai_text
                    else:
                        data["ai_summary"] = fallback_ai_text

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
                    # Släpp batteriet till Auto-läge om vi tappar kontakten helt
                    try:
                        await self.battery_api.apply_action("IDLE")
                    except Exception as fallback_err:
                        _LOGGER.error(f"Failed to set battery to IDLE on connection error: {fallback_err}")
                    raise UpdateFailed(
                        f"Connection error after 3 attempts: {type(err).__name__}: {error_detail}"
                    ) from err

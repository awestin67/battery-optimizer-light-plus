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

        self.unsub_timer = None
        self.current_load_w = None
        self._is_passive_mode = False

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

        async def _ev_interval(now):
            await self.check_ev_schedules()

        self.unsub_ev_timer = async_track_time_change(
            self.hass,
            _ev_interval,
            second=0
        )

    async def _async_update_data(self):
        """Körs var 5:e minut."""
        session = async_get_clientsession(self.hass)

        for attempt in range(3):
            try:
                # 1. Hämta SOC
                soc = await self.battery_api.get_current_soc()

                try:
                    hardware_min_soc = float(self.config.get("min_soc", 0.0))
                except (ValueError, TypeError):
                    hardware_min_soc = 0.0

                # Hämta reservkapacitet om batteriet stöder det (tex Sonnen EM_USOC)
                if hasattr(self.battery_api, "get_min_soc"):
                    min_val = await self.battery_api.get_min_soc()
                    if min_val is not None:
                        hardware_min_soc = min_val

                if (
                    hardware_min_soc == 0.0
                    and hasattr(self.battery_api, "coordinator")
                    and getattr(self.battery_api.coordinator, "data", None)
                ):
                    em_usoc = self.battery_api.coordinator.data.get("EM_USOC")
                    if em_usoc is not None:
                        try:
                            hardware_min_soc = float(em_usoc)
                        except (ValueError, TypeError):
                            pass

                if soc is None:
                    raise ValueError("Batteriets SoC kunde inte läsas av. Sensorn kanske startar upp?")

                # Skala SoC så att molnet ser det tillgängliga fönstret (t.ex. 5-100%) som 0-100%.
                # Detta döljer hårdvarureserven helt för molnet.
                reported_soc = 0.0
                if hardware_min_soc < 100.0:
                    reported_soc = max(0.0, (soc - hardware_min_soc) / (100.0 - hardware_min_soc) * 100.0)
                reported_soc = round(reported_soc, 1)

                # --- SENSOR GLITCH FILTER ---
                # Förhindrar orimliga spikar (t.ex. när Sonnen går ner i sleep mode på 0% och rapporterar 100%)
                if hasattr(self, "_last_valid_soc") and self._last_valid_soc is not None:
                    if reported_soc - self._last_valid_soc > 30.0:
                        _LOGGER.warning(
                            f"Ignorerar orimligt SoC-hopp från {self._last_valid_soc}% till {reported_soc}%. "
                            "Förmodligen ett sensor-glitch från batteriet."
                        )
                        reported_soc = self._last_valid_soc
                self._last_valid_soc = reported_soc

                is_solar_override = False
                is_in_maintenance = False
                if hasattr(self, "peak_guard") and self.peak_guard:
                    is_solar_override = self.peak_guard.is_solar_override
                    is_in_maintenance = self.peak_guard.in_maintenance

                # --- EV CHARGING SENSOR ---
                is_ev_charging = False

                from .const import CONF_EV_C1_IS_CHARGING, CONF_EV_C2_IS_CHARGING
                ev_sensors = [
                    self.config.get("ev_charging_sensor"),
                    self.config.get(CONF_EV_C1_IS_CHARGING),
                    self.config.get(CONF_EV_C2_IS_CHARGING)
                ]

                for entity_id in ev_sensors:
                    if entity_id:
                        ev_state = self.hass.states.get(entity_id)
                        if ev_state and ev_state.state not in ["unknown", "unavailable"]:
                            val = ev_state.state.lower()
                            # Hantera Binary Sensor, specifik status eller numeriskt effektvärde (>0W)
                            if val in ["on", "true", "charging", "1", "på", "charge", "sant"]:
                                is_ev_charging = True
                            else:
                                try:
                                    if float(val) > 0:
                                        is_ev_charging = True
                                except ValueError:
                                    pass

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
                    _LOGGER.debug(
                        "Husförbrukning kunde inte beräknas (sensorer under uppstart?). "
                        "Skickar 0.0 kW till molnet."
                    )

                # --- SOLPRODUKTION ---
                current_solar_kw = None
                current_solar_w = None

                if hasattr(self.battery_api, "get_solar_power"):
                    current_solar_w = await self.battery_api.get_solar_power()

                if current_solar_w is None:
                    solar_id = self.config.get("solar_sensor")
                    if solar_id:
                        solar_state = self.hass.states.get(solar_id)
                        if solar_state and solar_state.state not in ["unknown", "unavailable"]:
                            try:
                                val = float(solar_state.state)
                                if solar_state.attributes.get("unit_of_measurement") == "kW":
                                    val *= 1000.0
                                current_solar_w = val
                            except ValueError:
                                pass

                if current_solar_w is not None:
                    if current_solar_w < 0:
                        current_solar_w = 0.0
                    current_solar_kw = round(current_solar_w / 1000.0, 3)

                self.current_load_w = current_load_w

                # --- OFFGRID STATUS ---
                is_offgrid = False

                # 1. Check if battery API implements is_offgrid natively
                if hasattr(self.battery_api, "is_offgrid"):
                    if asyncio.iscoroutinefunction(self.battery_api.is_offgrid):
                        is_offgrid = await self.battery_api.is_offgrid()
                    else:
                        is_offgrid = self.battery_api.is_offgrid()

                # 5. Payload (Endast det backend behöver)
                payload = {
                    "api_key": self.api_key,
                    "soc": reported_soc,
                    "is_solar_override": is_solar_override,
                    "is_in_maintenance": is_in_maintenance,
                    "is_ev_charging": is_ev_charging,
                    "is_offgrid": is_offgrid,
                    "ha_version": self.version,
                    "current_consumption_kw": current_consumption_kw,
                    "inverter_brand": self.config.get("battery_type", "unknown")
                }

                if current_solar_kw is not None:
                    payload["current_solar_kw"] = current_solar_kw

                _LOGGER.debug(f"Light-Request: {payload}")

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
                    fallback_graph_data = self.data.get("graph_data", {}) if self.data else {}
                    try:
                        history_hours = int(self.config.get("graph_history_hours", 24))
                        base_api_url = self.config.get("api_url", "").rstrip("/")
                        graph_url = f"{base_api_url}/ha_graph_data?history_hours={history_hours}"

                        async with session.get(
                            graph_url, headers={"X-API-Key": self.api_key}, timeout=aiohttp.ClientTimeout(total=30)
                        ) as graph_response:
                            if graph_response.status == 200:
                                graph_data = await graph_response.json()
                                # Normalisera current_solar_kw till solar_kw i historiken
                                for entry in graph_data.get("history", []):
                                    if "current_solar_kw" in entry:
                                        entry["solar_kw"] = entry.pop("current_solar_kw")
                                data["graph_data"] = graph_data
                            else:
                                _LOGGER.debug("Kunde inte hämta grafdata. Status: %s", graph_response.status)
                                data["graph_data"] = fallback_graph_data
                    except Exception as e:
                        _LOGGER.debug("Fel vid hämtning av grafdata: %s", e)
                        data["graph_data"] = fallback_graph_data

                    action = data.get("action", "IDLE")

                    client_mode = data.get("client_mode", "ACTIVE")
                    self._is_passive_mode = (client_mode == "PASSIVE")

                    try:
                        target_kw = float(data.get("target_power_kw", 0.0))
                        # Om backend skickar värdet i Watt istället för kW (t.ex. 1800)
                        if target_kw > 100:
                            target_kw = target_kw / 1000.0
                    except (ValueError, TypeError):
                        target_kw = 0.0

                    # --- NYTT: Spara molnets ursprungliga intention ---
                    data["cloud_action"] = action
                    data["cloud_target_power_kw"] = target_kw

                    # Låt batterihanteraren verkställa beslutet, om inte PeakGuard har tagit över lokalt
                    if self._is_passive_mode:
                        _LOGGER.debug("Passive mode active. Not applying actions to battery from cloud.")
                    elif (
                        not is_in_maintenance
                        and not is_solar_override
                        and not (hasattr(self, "peak_guard") and self.peak_guard.is_active)
                    ):
                        # Spärra manuell urladdning om vi har nått hårdvarureserven (t.ex. Sonnen Backup)
                        if action == "DISCHARGE" and soc <= hardware_min_soc:
                            _LOGGER.info(
                                f"Batteriets SoC ({soc}%) har nått hårdvarureserven "
                                f"({hardware_min_soc}%). Avbryter urladdning."
                            )
                            action = "IDLE"

                        try:
                            await self.battery_api.apply_action(action, target_kw)
                        except Exception as local_err:
                            _LOGGER.error(
                                f"Lokalt fel vid styrning av batteriet (påverkar ej molnet): {local_err}",
                                exc_info=True,
                            )

                    # --- Hämta AI Sammanfattning (Endast vid uppstart och 04:15) ---
                    now = dt_util.now()
                    should_fetch_ai = False

                    default_ai_text = "Ingen AI-sammanfattning tillgänglig ännu."
                    fallback_ai_text = self.data.get("ai_summary", default_ai_text) if self.data else default_ai_text

                    # 1. Hämta alltid vid första uppstart
                    if not self.data or "ai_summary" not in self.data:
                        should_fetch_ai = True
                    # 2. Hämta under dagen om vi inte redan fått en ny text idag (börjar kolla kl 06:00 lokal tid)
                    elif now.hour >= 5:
                        last_fetch = getattr(self, "_last_ai_fetch_day", None)
                        if last_fetch != now.date():
                            should_fetch_ai = True

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
                                    fetched_summary = ai_data.get("ai_summary", default_ai_text)
                                    data["ai_summary"] = fetched_summary

                                    # Markera endast som hämtad för idag om texten faktiskt har
                                    # ändrats från vår tidigare cachade version (och inte är default).
                                    # Vi sätter dessutom bara flaggan om klockan passerat 06:00 för att inte
                                    # luras av nattliga omstarter (där vi råkar hämta gårdagens text efter midnatt).
                                    if fetched_summary != default_ai_text and fetched_summary != fallback_ai_text:
                                        if now.hour >= 6:
                                            self._last_ai_fetch_day = now.date()
                                else:
                                    data["ai_summary"] = fallback_ai_text
                        except Exception as e:
                            _LOGGER.debug(f"Kunde inte hämta AI-sammanfattning: {e}")
                            data["ai_summary"] = fallback_ai_text
                    else:
                        data["ai_summary"] = fallback_ai_text

                    data["last_update_time"] = now.isoformat()
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
                        "Update attempt %d failed with %s: %s. Retrying in 5s...",
                        attempt + 1,
                        type(err).__name__,
                        error_detail,
                    )
                    await asyncio.sleep(5)
                else:
                    _LOGGER.exception("Light-Error after 3 attempts")
                    # Släpp batteriet till Auto-läge om vi tappar kontakten helt
                    try:
                        if getattr(self, "_is_passive_mode", False):
                            _LOGGER.debug("Passive mode active. Skipping fallback to IDLE on connection error.")
                        else:
                            await self.battery_api.apply_action("IDLE")
                    except Exception as fallback_err:
                        _LOGGER.error(f"Failed to set battery to IDLE on connection error: {fallback_err}")
                    raise UpdateFailed(
                        f"Update error after 3 attempts: {type(err).__name__}: {error_detail}"
                    ) from err

    async def async_plan_ev_charging(self, car_id="all"):
        """Anropar API för att få laddschema baserat på konfigurerade HA-helpers."""
        from .const import (
            CONF_EV_C1_NAME,
            CONF_EV_C1_TARGET_KWH,
            CONF_EV_C1_DEPART_TIME,
            CONF_EV_C1_MAX_KW,
            CONF_EV_C2_NAME,
            CONF_EV_C2_TARGET_KWH,
            CONF_EV_C2_DEPART_TIME,
            CONF_EV_C2_MAX_KW,
        )

        cars_payload = []

        def build_car_payload(cid, name_key, target_key, depart_key, max_kw_key):
            target = self.hass.states.get(self.config.get(target_key, ""))
            depart = self.hass.states.get(self.config.get(depart_key, ""))
            max_kw = self.hass.states.get(self.config.get(max_kw_key, ""))

            if target and depart and max_kw and target.state not in ("unknown", "unavailable"):
                try:
                    cname = self.config.get(name_key, f"Bil {cid}")
                    return {
                        "id": cname,
                        "target_kwh": float(target.state),
                        "departure_time": depart.state,
                        "max_charge_kw": float(max_kw.state)
                    }
                except ValueError:
                    pass
            return None

        if car_id in ("car1", "all"):
            c1 = build_car_payload(
                "1", CONF_EV_C1_NAME, CONF_EV_C1_TARGET_KWH, CONF_EV_C1_DEPART_TIME, CONF_EV_C1_MAX_KW
            )
            if c1:
                cars_payload.append(c1)

        if car_id in ("car2", "all"):
            c2 = build_car_payload(
                "2", CONF_EV_C2_NAME, CONF_EV_C2_TARGET_KWH, CONF_EV_C2_DEPART_TIME, CONF_EV_C2_MAX_KW
            )
            if c2:
                cars_payload.append(c2)

        if not cars_payload:
            _LOGGER.warning(
                "Kunde inte bygga EV-payload, kontrollera att dina Helpers är korrekt "
                "ifyllda och konfigurerade."
            )
            return

        payload = {
            "api_key": self.api_key,
            "cars": cars_payload
        }

        url = self.config["api_url"].rstrip('/') + "/api/ev/plan"
        _LOGGER.debug(f"Hämtar EV-laddplan från {url}: {payload}")

        session = async_get_clientsession(self.hass)
        try:
            async with session.post(url, json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    schedules = data.get("schedules", {})
                    _LOGGER.info(f"Mottog ny EV-laddplan: {schedules}")
                    if not hasattr(self, "ev_schedules"):
                        self.ev_schedules = {}
                    self.ev_schedules.update(schedules)
                else:
                    _LOGGER.error(f"Fel vid hämtning av EV-laddplan: {resp.status} {await resp.text()}")
        except Exception as e:
            _LOGGER.error(f"Kunde inte anropa EV-API: {e}")

    async def check_ev_schedules(self):
        """Körs varje minut för att starta/stoppa laddboxar enligt schema."""
        if not hasattr(self, "ev_schedules") or not self.ev_schedules:
            return

        from .const import CONF_EV_C1_NAME, CONF_EV_C1_SWITCH, CONF_EV_C2_NAME, CONF_EV_C2_SWITCH

        now = dt_util.now()

        def process_car(name_key, switch_key, default_name):
            car_name = self.config.get(name_key, default_name)
            switch_id = self.config.get(switch_key)
            if not switch_id:
                return

            car_schedule = self.ev_schedules.get(car_name)
            if not car_schedule:
                return

            should_be_on = False
            for step in car_schedule:
                try:
                    start_dt = dt_util.parse_datetime(step["start_time"])
                    end_dt = dt_util.parse_datetime(step["end_time"])
                    if start_dt and end_dt and start_dt <= now < end_dt:
                        should_be_on = True
                        break
                except Exception as e:
                    _LOGGER.debug(f"Kunde inte parsa datum i ev schema: {e}")

            switch_state = self.hass.states.get(switch_id)
            if not switch_state:
                return

            if should_be_on and switch_state.state != "on":
                _LOGGER.info(f"Startar laddbox {switch_id} enligt EV-schema för {car_name}")
                self.hass.async_create_task(
                    self.hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=False)
                )
            elif not should_be_on and switch_state.state == "on":
                _LOGGER.info(f"Stoppar laddbox {switch_id} enligt EV-schema för {car_name}")
                self.hass.async_create_task(
                    self.hass.services.async_call("switch", "turn_off", {"entity_id": switch_id}, blocking=False)
                )

        process_car(CONF_EV_C1_NAME, CONF_EV_C1_SWITCH, "Bil 1")
        process_car(CONF_EV_C2_NAME, CONF_EV_C2_SWITCH, "Bil 2")

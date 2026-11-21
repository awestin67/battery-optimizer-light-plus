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
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.util.dt as dt_util
from .battery_factory import create_battery_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _match_schedule_key(schedules_dict: dict, target_name: str):
    """Matchar bilnamn exakt först, sedan skiftlägesokänsligt."""
    if target_name in schedules_dict:
        return target_name
    norm = str(target_name).strip().lower()
    for key in schedules_dict:
        if str(key).strip().lower() == norm:
            return key
    return None

class BatteryOptimizerLightCoordinator(DataUpdateCoordinator):
    """Hanterar kommunikationen för Light-versionen."""

    def __init__(self, hass, config, version="0.0.0"):
        super().__init__(
            hass,
            _LOGGER,
            name="Battery Optimizer Light Plus",
        )
        raw_url = str(config.get("api_url", "")).strip().rstrip("/")
        if raw_url and not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raw_url = f"https://{raw_url}"
        self.base_api_url = raw_url
        self.api_url = f"{raw_url}/signal"
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
        self._ev_lock = asyncio.Lock()
        self.ev_schedules = {}
        self.ev_preliminary_cars = set()
        self._ev_schedules_seeded = False

    @property
    def device_info(self) -> DeviceInfo:
        """Gemensam enhetsinformation för integrationens entiteter."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api_key)},
            name="Battery Optimizer Light Plus",
            manufacturer="Awestin Consulting",
            model="Cloud Optimizer",
            configuration_url="https://battery-prod.awestinconsulting.se",
        )

    def setup_timer(self):
        """Startar schemaläggaren.

        Anropas efter lyckad första uppdatering för att undvika minnesläckor vid setup-fel.
        """
        async def _update_interval(now):
            tick_local = dt_util.as_local(now) if now is not None else dt_util.now()
            await self.async_request_refresh()
            prelim_cars = getattr(self, "ev_preliminary_cars", None)
            if prelim_cars:
                if (tick_local.hour > 13 or (tick_local.hour == 13 and tick_local.minute >= 15)) and (
                    tick_local.minute in (0, 15, 30, 45)
                ):
                    for c_key in list(prelim_cars):
                        _LOGGER.info(
                            "Uppdaterar preliminärt EV-schema för %s nu när morgondagens priser bör finnas...",
                            c_key,
                        )
                        await self.async_plan_ev_charging(c_key)

        self.unsub_timer = async_track_time_change(
            self.hass,
            _update_interval,
            minute=list(range(0, 60, 5)),
            second=30
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

                is_in_maintenance = False
                if (
                    hasattr(self, "peak_guard")
                    and self.peak_guard
                    and not getattr(self, "_is_passive_mode", False)
                ):
                    is_in_maintenance = self.peak_guard.in_maintenance

                # --- EV CHARGING SENSOR ---
                is_ev_charging = False
                ev_power_kw_total = 0.0
                has_ev_power_sensor = False

                from .const import CONF_EV_C1_IS_CHARGING, CONF_EV_C2_IS_CHARGING
                ev_sensors = list(
                    dict.fromkeys(
                        s
                        for s in (
                            self.config.get("ev_charging_sensor"),
                            self.config.get(CONF_EV_C1_IS_CHARGING),
                            self.config.get(CONF_EV_C2_IS_CHARGING),
                        )
                        if s
                    )
                )

                for entity_id in ev_sensors:
                    ev_state = self.hass.states.get(entity_id)
                    if ev_state and ev_state.state not in ["unknown", "unavailable"]:
                        val = ev_state.state.lower()
                        # Hantera Binary Sensor, specifik status eller numeriskt effektvärde (>0W)
                        if val in ["on", "true", "charging", "boosting", "1", "på", "charge", "sant"]:
                            is_ev_charging = True
                        else:
                            try:
                                if float(val) > 0:
                                    is_ev_charging = True
                            except ValueError:
                                pass
                        try:
                            attrs = getattr(ev_state, "attributes", None)
                            unit = attrs.get("unit_of_measurement") if isinstance(attrs, dict) else None
                            if isinstance(unit, str) and unit.strip().lower() in ("w", "watt", "kw", "kilowatt"):
                                p_val = max(0.0, float(ev_state.state))
                                if unit.strip().lower() in ("w", "watt"):
                                    p_val /= 1000.0
                                ev_power_kw_total += p_val
                                has_ev_power_sensor = True
                        except (ValueError, TypeError):
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
                                val = float(state.state)
                                unit = state.attributes.get("unit_of_measurement")
                                if unit and unit.lower() in ["kw", "kilowatt"]:
                                    val *= 1000.0
                                current_load_w = val
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
                                    unit = grid_state.attributes.get("unit_of_measurement")
                                    if unit and unit.lower() in ["kw", "kilowatt"]:
                                        g_val *= 1000.0
                                    if self.config.get("grid_sensor_invert", False):
                                        g_val = -g_val
                                except ValueError:
                                    pass

                        if bat_id:
                            bat_state = self.hass.states.get(bat_id)
                            if bat_state and bat_state.state not in ["unknown", "unavailable"]:
                                try:
                                    b_val = float(bat_state.state)
                                    unit = bat_state.attributes.get("unit_of_measurement")
                                    if unit and unit.lower() in ["kw", "kilowatt"]:
                                        b_val *= 1000.0
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
                                unit = solar_state.attributes.get("unit_of_measurement")
                                if unit and unit.lower() in ["kw", "kilowatt"]:
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

                # --- VARMVATTEN TEMPERATUR ---
                water_heater_temp_id = self.config.get("water_heater_temp_sensor")
                water_heater_temp = None
                if water_heater_temp_id:
                    vh_temp_state = self.hass.states.get(water_heater_temp_id)
                    if vh_temp_state and vh_temp_state.state not in ["unknown", "unavailable"]:
                        try:
                            water_heater_temp = round(float(vh_temp_state.state), 1)
                        except (ValueError, TypeError):
                            pass

                # 5. Payload (Endast det backend behöver)
                payload = {
                    "soc": reported_soc,
                    "is_in_maintenance": is_in_maintenance,
                    "is_ev_charging": is_ev_charging,
                    "is_offgrid": is_offgrid,
                    "ha_version": self.version,
                    "current_consumption_kw": current_consumption_kw,
                    "inverter_brand": self.config.get("battery_type", "unknown")
                }

                sw_ver = getattr(self.battery_api, "software_version", None)
                if callable(sw_ver) or type(sw_ver).__name__ in ("MagicMock", "Mock", "AsyncMock"):
                    sw_ver = None
                if sw_ver is not None and str(sw_ver).strip():
                    payload["inverter_software_version"] = str(sw_ver).strip()

                supports_export_limit = getattr(self.battery_api, "supports_bess_export_limit", None)
                if isinstance(supports_export_limit, bool):
                    payload["supports_bess_export_limit"] = supports_export_limit

                if has_ev_power_sensor:
                    payload["ev_power_kw"] = round(ev_power_kw_total, 3)

                if current_solar_kw is not None:
                    payload["current_solar_kw"] = current_solar_kw

                if water_heater_temp is not None:
                    payload["water_heater_temp"] = water_heater_temp

                _LOGGER.debug(f"Light-Request: {payload}")

                headers = {"X-API-Key": self.api_key}

                async with session.post(
                    self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 401:
                        text = await response.text()
                        raise UpdateFailed(f"Authentication failed: {text}")

                    if response.status == 429:
                        text = await response.text()
                        if self.data:
                            _LOGGER.warning(
                                "Rate limit (429) mot molnet – behåller senaste kända data till nästa uppdatering."
                            )
                            return self.data
                        raise UpdateFailed(f"Server 429: {text}")

                    if response.status != 200:
                        text = await response.text()
                        raise UpdateFailed(f"Server {response.status}: {text}")

                    data = await response.json()

                    ev_smart_plans = data.get("ev_smart_plans")
                    if isinstance(ev_smart_plans, dict):
                        if not getattr(self, "_ev_schedules_seeded", False) and not getattr(self, "ev_schedules", None):
                            self.ev_schedules = {
                                k: [dict(step) if isinstance(step, dict) else step for step in v]
                                if isinstance(v, list)
                                else v
                                for k, v in ev_smart_plans.items()
                            }
                            self._ev_schedules_seeded = True
                        elif getattr(self, "ev_preliminary_cars", None):
                            from .const import CONF_EV_C1_NAME, CONF_EV_C2_NAME

                            car_name_map = {
                                "car1": self.config.get(CONF_EV_C1_NAME, "Bil 1"),
                                "car2": self.config.get(CONF_EV_C2_NAME, "Bil 2"),
                            }
                            updated_schedules = dict(getattr(self, "ev_schedules", None) or {})
                            promoted = False
                            for c_key in list(self.ev_preliminary_cars):
                                cname = car_name_map.get(c_key)
                                if not cname:
                                    continue
                                matched_key = _match_schedule_key(ev_smart_plans, cname)
                                steps = ev_smart_plans.get(matched_key) if matched_key is not None else None
                                if (
                                    isinstance(steps, list)
                                    and len(steps) > 0
                                    and all(
                                        isinstance(step, dict) and step.get("is_preliminary") is False
                                        for step in steps
                                    )
                                ):
                                    updated_schedules[cname] = [dict(step) for step in steps]
                                    self.ev_preliminary_cars.discard(c_key)
                                    promoted = True
                                    _LOGGER.info(
                                        "Uppdaterade preliminärt EV-schema för %s med skarpt schema från /signal.",
                                        cname,
                                    )
                            if promoted:
                                self.ev_schedules = updated_schedules

                    # --- Hämta graf-data ---
                    fallback_graph_data = self.data.get("graph_data", {}) if self.data else {}
                    try:
                        history_hours = int(self.config.get("graph_history_hours", 24))
                        base_api_url = getattr(self, "base_api_url", self.config.get("api_url", "").rstrip("/"))
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
                    if hasattr(self.battery_api, "set_passive_mode"):
                        self.battery_api.set_passive_mode(self._is_passive_mode)

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
                    site_limits = data.get("site_limits") or data.get("sonnen_site_limits")
                    has_ev_export_limit = (
                        action == "IDLE"
                        and isinstance(site_limits, dict)
                        and site_limits.get("p_bess_inv_max_export_limit") is not None
                        and getattr(self.battery_api, "supports_bess_export_limit", False) is True
                    )
                    ev_hold_override = (
                        hasattr(self, "peak_guard")
                        and getattr(self.peak_guard, "ev_charging_paused", False) is True
                        and action not in ("HOLD", "CHARGE")
                        and str(data.get("peakguard_status") or "").strip() != "Pausad (Sol > Elbil)"
                        and not has_ev_export_limit
                    )
                    if self._is_passive_mode:
                        _LOGGER.debug("Passive mode active. Not applying actions to battery from cloud.")
                    elif (
                        not is_in_maintenance
                        and not (hasattr(self, "peak_guard") and self.peak_guard.is_active)
                        and not ev_hold_override
                    ):
                        # Spärra manuell urladdning om vi har nått hårdvarureserven (t.ex. Sonnen Backup)
                        if action == "DISCHARGE" and soc <= hardware_min_soc:
                            _LOGGER.info(
                                f"Batteriets SoC ({soc}%) har nått hårdvarureserven "
                                f"({hardware_min_soc}%). Avbryter urladdning."
                            )
                            action = "IDLE"

                        if action != "HOLD" and hasattr(self, "peak_guard") and self.peak_guard:
                            self.peak_guard._hold_command_sent = False

                        try:
                            site_limits = data.get("site_limits") or data.get("sonnen_site_limits")
                            try:
                                if site_limits is not None:
                                    await self.battery_api.apply_action(
                                        action,
                                        target_kw,
                                        site_limits=site_limits,
                                        sonnen_site_limits=site_limits,
                                    )
                                else:
                                    await self.battery_api.apply_action(action, target_kw)
                            except TypeError:
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
                            base_api_url = getattr(self, "base_api_url", self.config.get("api_url", "").rstrip("/"))
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
                if isinstance(err, UpdateFailed) and (
                    "Authentication failed" in str(err) or "Server 429:" in str(err)
                ):
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
        """Wrapper för att förhindra race conditions vid multipla laddkablar."""
        async with self._ev_lock:
            await self._async_plan_ev_charging_locked(car_id)

    async def _async_plan_ev_charging_locked(self, car_id="all"):
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
                    raw_dep = str(depart.state).strip()
                    if " " in raw_dep or "T" in raw_dep:
                        sep = "T" if "T" in raw_dep else " "
                        raw_dep = raw_dep.split(sep)[-1]
                    return {
                        "id": cname,
                        "target_kwh": float(target.state),
                        "departure_time": raw_dep[:5], # Cloud expects HH:MM
                        "max_charge_kw": float(max_kw.state)
                    }
                except ValueError:
                    pass
            return None

        requested_cars = []
        if car_id in ("car1", "all"):
            c1 = build_car_payload(
                "1", CONF_EV_C1_NAME, CONF_EV_C1_TARGET_KWH, CONF_EV_C1_DEPART_TIME, CONF_EV_C1_MAX_KW
            )
            if c1:
                cars_payload.append(c1)
                requested_cars.append(("car1", c1["id"], c1["target_kwh"]))

        if car_id in ("car2", "all"):
            c2 = build_car_payload(
                "2", CONF_EV_C2_NAME, CONF_EV_C2_TARGET_KWH, CONF_EV_C2_DEPART_TIME, CONF_EV_C2_MAX_KW
            )
            if c2:
                cars_payload.append(c2)
                requested_cars.append(("car2", c2["id"], c2["target_kwh"]))

        if not cars_payload:
            _LOGGER.warning(
                "Kunde inte bygga EV-payload, kontrollera att dina Helpers är korrekt "
                "ifyllda och konfigurerade."
            )
            return

        payload = {
            "cars": cars_payload
        }

        base_url = getattr(self, "base_api_url", self.config.get("api_url", "").rstrip("/"))
        url = f"{base_url}/api/ev/plan"
        _LOGGER.debug(f"Hämtar EV-laddplan från {url}: {payload}")

        def _format_ev_window(steps) -> str:
            if not isinstance(steps, list) or not steps:
                return "tomt"
            first = steps[0] if isinstance(steps[0], dict) else {}
            last = steps[-1] if isinstance(steps[-1], dict) else {}
            start_str = str(first.get("start") or "")
            end_str = str(last.get("end") or last.get("start") or "")
            start_hhmm = start_str[11:16] if len(start_str) >= 16 else start_str
            end_hhmm = end_str[11:16] if len(end_str) >= 16 else end_str
            if start_hhmm and end_hhmm:
                return f"{start_hhmm}–{end_hhmm}"
            return start_hhmm or end_hhmm or "okänt"

        headers = {"X-API-Key": self.api_key}
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(url, json=payload, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    schedules = data.get("schedules")
                    if not isinstance(schedules, dict):
                        schedules = {}
                    is_prelim = bool(data.get("is_preliminary", False))
                    if not hasattr(self, "ev_preliminary_cars"):
                        self.ev_preliminary_cars = set()
                    old_schedules = dict(getattr(self, "ev_schedules", None) or {})
                    new_schedules = dict(old_schedules)
                    self._ev_schedules_seeded = True

                    matched_response_keys = set()
                    for c_key, cname, target_kwh in requested_cars:
                        was_prelim = c_key in self.ev_preliminary_cars
                        old_steps = old_schedules.get(cname) or []
                        matched_key = _match_schedule_key(schedules, cname)
                        if matched_key is not None:
                            matched_response_keys.add(matched_key)
                        car_steps = schedules.get(matched_key) if matched_key is not None else None

                        if isinstance(car_steps, list) and len(car_steps) > 0:
                            new_schedules[cname] = [
                                dict(step) if isinstance(step, dict) else step
                                for step in car_steps
                            ]
                            if is_prelim:
                                self.ev_preliminary_cars.add(c_key)
                            else:
                                self.ev_preliminary_cars.discard(c_key)
                            now_prelim = c_key in self.ev_preliminary_cars
                            _LOGGER.debug(
                                "EV replan %s: preliminary=%s->%s, steps %d->%d, window %s -> %s",
                                cname,
                                was_prelim,
                                now_prelim,
                                len(old_steps),
                                len(car_steps),
                                _format_ev_window(old_steps),
                                _format_ev_window(car_steps),
                            )
                        elif target_kwh <= 0:
                            new_schedules.pop(cname, None)
                            self.ev_preliminary_cars.discard(c_key)
                            _LOGGER.debug(
                                "EV replan %s: target_kwh=%.1f -> rensar schema (preliminary=%s->False)",
                                cname,
                                target_kwh,
                                was_prelim,
                            )
                        else:
                            if is_prelim or was_prelim:
                                self.ev_preliminary_cars.add(c_key)
                            _LOGGER.warning(
                                "EV-laddplan för %s saknades eller var tom i svaret "
                                "(is_preliminary=%s, target_kwh=%.1f). Behåller preliminär status=%s.",
                                cname,
                                is_prelim,
                                target_kwh,
                                c_key in self.ev_preliminary_cars,
                            )

                    requested_names = {cname.strip().lower() for _, cname, _ in requested_cars}
                    for other_name, other_steps in schedules.items():
                        if (
                            other_name not in matched_response_keys
                            and str(other_name).strip().lower() not in requested_names
                            and isinstance(other_steps, list)
                            and other_steps
                        ):
                            new_schedules[other_name] = [
                                dict(step) if isinstance(step, dict) else step
                                for step in other_steps
                            ]

                    self.ev_schedules = new_schedules
                    _LOGGER.info(f"Mottog ny EV-laddplan (preliminär={is_prelim}): {schedules}")
                    if hasattr(self, "async_set_updated_data"):
                        self.async_set_updated_data(self.data)
                    elif hasattr(self, "async_update_listeners"):
                        self.async_update_listeners()
                    # Uppdatera grafdatan utan att spamma POST /signal (som har 5/min rate limit)
                    await self._async_refresh_graph_data()
                else:
                    _LOGGER.error(f"Fel vid hämtning av EV-laddplan: {resp.status} {await resp.text()}")
        except Exception as e:
            _LOGGER.error(f"Kunde inte anropa EV-API: {e}")

    async def _async_refresh_graph_data(self):
        """Hämtar enbart ny grafdata (/ha_graph_data) utan att trigga ett fullt /signal-anrop."""
        if not self.data or not isinstance(self.data, dict):
            return
        try:
            session = async_get_clientsession(self.hass)
            history_hours = int(self.config.get("graph_history_hours", 24))
            base_api_url = getattr(self, "base_api_url", self.config.get("api_url", "").rstrip("/"))
            graph_url = f"{base_api_url}/ha_graph_data?history_hours={history_hours}"
            async with session.get(
                graph_url, headers={"X-API-Key": self.api_key}, timeout=aiohttp.ClientTimeout(total=30)
            ) as graph_response:
                if graph_response.status == 200:
                    graph_data = await graph_response.json()
                    for entry in graph_data.get("history", []):
                        if "current_solar_kw" in entry:
                            entry["solar_kw"] = entry.pop("current_solar_kw")
                    self.data["graph_data"] = graph_data
                    self.data["last_update_time"] = dt_util.now().isoformat()
                    if hasattr(self, "async_set_updated_data"):
                        self.async_set_updated_data(self.data)
                    elif hasattr(self, "async_update_listeners"):
                        self.async_update_listeners()
        except Exception as e:
            _LOGGER.debug("Kunde inte uppdatera grafdata efter EV-ändring: %s", e)

    async def async_clear_ev_charging(self, car_id):
        """Wrapper för att förhindra race conditions."""
        async with self._ev_lock:
            await self._async_clear_ev_charging_locked(car_id)

    async def _async_clear_ev_charging_locked(self, car_id):
        """Avbryter EV-laddning och nollställer molnet samt den lokala sensorn."""
        from .const import CONF_EV_C1_NAME, CONF_EV_C2_NAME

        cname = None
        if car_id == "car1":
            cname = self.config.get(CONF_EV_C1_NAME, "Bil 1")
        elif car_id == "car2":
            cname = self.config.get(CONF_EV_C2_NAME, "Bil 2")

        if not cname:
            return

        # 1. Rensa sensorn lokalt
        self._ev_schedules_seeded = True
        was_prelim = False
        if hasattr(self, "ev_preliminary_cars"):
            was_prelim = car_id in self.ev_preliminary_cars
            self.ev_preliminary_cars.discard(car_id)
        had_schedule = hasattr(self, "ev_schedules") and cname in self.ev_schedules
        if had_schedule:
            self.ev_schedules = {k: v for k, v in self.ev_schedules.items() if k != cname}
        if had_schedule or was_prelim:
            if hasattr(self, "async_set_updated_data"):
                self.async_set_updated_data(self.data)
            elif hasattr(self, "async_update_listeners"):
                self.async_update_listeners()
            _LOGGER.info(f"Nollställde EV-schemat lokalt för {cname}")

        # 2. Skicka DELETE till backend
        base_url = getattr(self, "base_api_url", self.config.get("api_url", "").rstrip("/"))
        url = f"{base_url}/api/ev/plan/{cname}"
        headers = {"X-API-Key": self.api_key}
        session = async_get_clientsession(self.hass)

        try:
            async with session.delete(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.info(f"Schemat för {cname} raderades i molnet.")
                    # Uppdatera grafdatan utan att spamma POST /signal (som har 5/min rate limit)
                    await self._async_refresh_graph_data()
                else:
                    _LOGGER.error(f"Kunde inte radera EV-schema i molnet: {resp.status} {await resp.text()}")
        except Exception as e:
            _LOGGER.error(f"Fel vid radering av EV-schema i molnet: {e}")

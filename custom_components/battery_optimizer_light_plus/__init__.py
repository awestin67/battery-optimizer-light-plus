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
from homeassistant.core import HomeAssistant, ServiceCall, CoreState # type: ignore
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN # type: ignore
from homeassistant.helpers.event import async_track_state_change_event, async_call_later # type: ignore
from homeassistant.helpers.aiohttp_client import async_get_clientsession # type: ignore
try:
    from homeassistant.components.http import HomeAssistantView # type: ignore
except ImportError:
    class HomeAssistantView:
        """Fallback för testmiljöer som saknar den fullständiga http-komponenten."""
from homeassistant.loader import async_get_integration # type: ignore
from .coordinator import BatteryOptimizerLightCoordinator
from .const import (
    DOMAIN,
    CONF_SOC_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_API_URL,
    CONF_API_KEY,
    CONF_GRID_SENSOR,
    CONF_GRID_SENSOR_INVERT,
    CONF_BATTERY_SENSOR_INVERT,
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_SONNEN,
    CONF_BATTERY_STATUS_SENSOR,
    CONF_BATTERY_STATUS_KEYWORDS,
    CONF_VIRTUAL_LOAD_SENSOR,
    DEFAULT_BATTERY_STATUS_KEYWORDS,
    CONF_EXTERNAL_CONTROL_SENSOR,
    CONF_WATER_HEATER_SWITCH,
    CONF_EV_CHARGING_SENSOR,
    CONF_EV_C1_IS_CHARGING,
    CONF_EV_C2_IS_CHARGING,
)

_LOGGER = logging.getLogger(__name__)

# --- KONFIGURATION ---
LIMIT_ENTITY = "sensor.optimizer_light_peak_limit"


def _is_ext_pause_state(state_obj) -> bool:
    """Kontrollerar om en state-instans för extern styrning representerar aktiv paus."""
    if not state_obj or state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False
    return str(state_obj.state).strip().lower() in ("on", "true", "1", "active", "yes", "på", "sant")


def _is_ev_charging_state(state_obj) -> bool:
    """Kontrollerar om en state-instans för elbilsladdning representerar aktiv laddning."""
    if not state_obj or state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False
    val = str(state_obj.state).strip().lower()
    if val in ("on", "true", "charging", "boosting", "1", "på", "charge", "sant"):
        return True
    try:
        return float(val) > 0
    except (ValueError, TypeError):
        return False


def _is_ev_cable_connected_state(state_obj) -> bool:
    """Kontrollerar om en state-instans för laddkabel representerar att kabeln är ansluten."""
    if not state_obj or state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return False
    val = str(state_obj.state).strip().lower()
    return val in (
        "on",
        "true",
        "1",
        "connected",
        "plugged_in",
        "plugged in",
        "ev connected",
        "waiting for ev",
        "charging",
        "boosting",
        "ready",
        "conserving",
        "complete",
        "completed",
        "paused",
        "på",
        "sant",
        "ansluten",
    )


async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up from a config entry."""
    config = dict(entry.data)
    if entry.options:
        config.update(entry.options)

    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version)

    coordinator = BatteryOptimizerLightCoordinator(hass, config, version)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Skapa och registrera den interna API-länken för grafdatan
    if "battery_optimizer_graph_view" not in hass.data[DOMAIN]:
        hass.http.register_view(BatteryOptimizerGraphView(hass))
        hass.data[DOMAIN]["battery_optimizer_graph_view"] = True

    # Initiera PeakGuard och injicera den valda batteri-logiken
    peak_guard = PeakGuard(hass, config, coordinator, coordinator.battery_api)
    coordinator.peak_guard = peak_guard

    # Hämta virtuell last-sensor från config (kan vara None)
    virtual_load_entity = config.get(CONF_VIRTUAL_LOAD_SENSOR)

    if config.get(CONF_BATTERY_TYPE) == BATTERY_TYPE_SONNEN:
        # Initiera firmware-version om metoden finns
        if hasattr(coordinator.battery_api, "async_init_version"):
            try:
                await coordinator.battery_api.async_init_version()
            except Exception as ver_err:
                _LOGGER.warning("Kunde inte hämta Sonnen firmware-version vid setup: %s", ver_err)

        # Starta Sonne-specifik polling var 10:e sekund INNAN vi frågar molnet första gången
        await coordinator.battery_api.coordinator.async_config_entry_first_refresh()

        def _sonnen_updated():
            hass.async_create_task(peak_guard.update(virtual_load_entity, LIMIT_ENTITY))

        # Låt Sonnen-uppdateringar trigga PeakGuard blixtsnabbt!
        coordinator.battery_api.coordinator.async_add_listener(_sonnen_updated)

    # Smart VVB: Hantera automatisk styrning av VVB-switch om användaren pekat ut en sådan
    water_heater_switch = config.get(CONF_WATER_HEATER_SWITCH)

    async def _handle_water_heater_control():
        if not water_heater_switch or not coordinator.data:
            return

        boost = bool(coordinator.data.get("water_heater_boost", False))
        current_state = hass.states.get(water_heater_switch)
        target_state = "on" if boost else "off"

        if current_state is None or current_state.state != target_state:
            service_name = "turn_on" if boost else "turn_off"
            domain = water_heater_switch.split(".")[0] if "." in water_heater_switch else "homeassistant"
            if domain not in ("switch", "input_boolean"):
                domain = "homeassistant"

            _LOGGER.info(
                f"Smart VVB: Sätter {water_heater_switch} till {target_state.upper()} "
                f"(Orsak: {coordinator.data.get('water_heater_reason', 'Ingen orsak')})"
            )
            try:
                await hass.services.async_call(
                    domain,
                    service_name,
                    {"entity_id": water_heater_switch},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.error(f"Kunde inte styra VVB-switch {water_heater_switch}: {err}")

    # Kör första uppdateringen mot molnet NU, när det lokala batteriet är redo att svara med SoC
    await coordinator.async_config_entry_first_refresh()

    if water_heater_switch:
        await _handle_water_heater_control()

    def _cloud_updated():
        hass.async_create_task(peak_guard.update(virtual_load_entity, LIMIT_ENTITY))
        if water_heater_switch:
            hass.async_create_task(_handle_water_heater_control())

    coordinator.async_add_listener(_cloud_updated)

    # När första uppdateringen har lyckats och vi vet att integrationen startar ordentligt,
    # sätter vi upp den schemalagda timern (detta förhindrar timer-läckor vid HA-omstarter).
    coordinator.setup_timer()

    # --- BAKGRUNDSBEVAKNING ---
    ev_priority_entities = set()

    async def on_load_change(event):
        """Körs tyst i bakgrunden varje gång lasten eller styrstatus ändras."""
        if hass.state == CoreState.running:
            await peak_guard.update(virtual_load_entity, LIMIT_ENTITY)
            if event and hasattr(event, "data") and isinstance(event.data, dict):
                changed_ent = event.data.get("entity_id")
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")
                if (
                    old_state is not None
                    and new_state is not None
                    and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                ):
                    if changed_ent == ext_entity and (
                        _is_ext_pause_state(old_state) != _is_ext_pause_state(new_state)
                    ):
                        await coordinator.async_request_refresh()
                    elif changed_ent in ev_priority_entities and (
                        _is_ev_charging_state(old_state) != _is_ev_charging_state(new_state)
                    ):
                        await coordinator.async_request_refresh()

    # Samla alla sensorer vi ska lyssna på
    entities_to_track = []

    # 1. Last-sensorer
    if virtual_load_entity:
        entities_to_track.append(virtual_load_entity)
        _LOGGER.info(f"PeakGuard monitoring virtual load: {virtual_load_entity}")
    else:
        grid_entity = config.get(CONF_GRID_SENSOR)
        bat_entity = config.get(CONF_BATTERY_POWER_SENSOR)
        if grid_entity:
            entities_to_track.append(grid_entity)
        if bat_entity:
            entities_to_track.append(bat_entity)
        _LOGGER.info(f"PeakGuard calculating load from: {grid_entity} + {bat_entity}")

    # 2. Status-sensor (för Maintenance)
    status_entity = config.get(CONF_BATTERY_STATUS_SENSOR)
    if status_entity:
        entities_to_track.append(status_entity)
        _LOGGER.info(f"PeakGuard monitoring battery status: {status_entity}")

    # 3. Extern Paus-sensor (Prio 1)
    ext_entity = config.get(CONF_EXTERNAL_CONTROL_SENSOR)
    if ext_entity:
        entities_to_track.append(ext_entity)
        _LOGGER.info(f"PeakGuard monitoring external control sensor: {ext_entity}")

    # 4. Elbilsladdningssensorer (Prio 2)
    for ev_key in (CONF_EV_CHARGING_SENSOR, CONF_EV_C1_IS_CHARGING, CONF_EV_C2_IS_CHARGING):
        ev_ent = config.get(ev_key)
        if ev_ent:
            if ev_ent not in entities_to_track:
                entities_to_track.append(ev_ent)
            ev_priority_entities.add(ev_ent)
            _LOGGER.info(f"PeakGuard monitoring EV charging sensor: {ev_ent}")

    # Starta bevakning
    if entities_to_track:
        entry.async_on_unload(
            async_track_state_change_event(hass, entities_to_track, on_load_change)
        )

    async def handle_run_peak_guard(call: ServiceCall):
        v_load = call.data.get("virtual_load_entity", virtual_load_entity)
        limit = call.data.get("limit_entity", LIMIT_ENTITY)
        await peak_guard.update(v_load, limit)

    hass.services.async_register(DOMAIN, "run_peak_guard", handle_run_peak_guard)

    async def handle_plan_ev_charging(call: ServiceCall):
        car_id = call.data.get("car_id", "all")
        _LOGGER.info(f"Triggering EV Smart Charging plan for {car_id}")
        await coordinator.async_plan_ev_charging(car_id)

    hass.services.async_register(DOMAIN, "plan_ev_charging", handle_plan_ev_charging)

    # Lyssna på ev_cable_connected och EV-helpers för automatiskt anrop
    from .const import (
        CONF_EV_C1_CABLE_CONNECTED,
        CONF_EV_C1_TARGET_KWH,
        CONF_EV_C1_DEPART_TIME,
        CONF_EV_C1_MAX_KW,
        CONF_EV_C2_CABLE_CONNECTED,
        CONF_EV_C2_TARGET_KWH,
        CONF_EV_C2_DEPART_TIME,
        CONF_EV_C2_MAX_KW,
    )

    async def _on_ev_connected(event):
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state and new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            ent_id = event.data.get("entity_id")
            new_connected = _is_ev_cable_connected_state(new_state)
            old_connected = (
                _is_ev_cable_connected_state(old_state)
                if old_state and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                else None
            )
            if old_connected == new_connected:
                return
            if new_connected:
                _LOGGER.info(f"EV Cable Connected detected on {ent_id}, generating plan...")
                if ent_id == config.get(CONF_EV_C1_CABLE_CONNECTED):
                    await coordinator.async_plan_ev_charging("car1")
                elif ent_id == config.get(CONF_EV_C2_CABLE_CONNECTED):
                    await coordinator.async_plan_ev_charging("car2")
            else:
                _LOGGER.info(f"EV Cable Disconnected detected on {ent_id}, clearing plan...")
                if ent_id == config.get(CONF_EV_C1_CABLE_CONNECTED):
                    await coordinator.async_clear_ev_charging("car1")
                elif ent_id == config.get(CONF_EV_C2_CABLE_CONNECTED):
                    await coordinator.async_clear_ev_charging("car2")

    ev_triggers = []
    if config.get(CONF_EV_C1_CABLE_CONNECTED):
        ev_triggers.append(config.get(CONF_EV_C1_CABLE_CONNECTED))
    if config.get(CONF_EV_C2_CABLE_CONNECTED):
        ev_triggers.append(config.get(CONF_EV_C2_CABLE_CONNECTED))

    if ev_triggers:
        entry.async_on_unload(
            async_track_state_change_event(hass, ev_triggers, _on_ev_connected)
        )

    c1_helpers = [
        config.get(k)
        for k in (CONF_EV_C1_TARGET_KWH, CONF_EV_C1_DEPART_TIME, CONF_EV_C1_MAX_KW)
        if config.get(k)
    ]
    c2_helpers = [
        config.get(k)
        for k in (CONF_EV_C2_TARGET_KWH, CONF_EV_C2_DEPART_TIME, CONF_EV_C2_MAX_KW)
        if config.get(k)
    ]

    # Debounce: väntar tills användaren slutat ändra (t.ex. dra i ett reglage) innan planen skapas om
    EV_REPLAN_DEBOUNCE_S = 3
    pending_replans = {}

    def _schedule_replan(car_key):
        unsub = pending_replans.pop(car_key, None)
        if unsub:
            unsub()

        async def _run(_now):
            pending_replans.pop(car_key, None)
            await coordinator.async_plan_ev_charging(car_key)

        pending_replans[car_key] = async_call_later(hass, EV_REPLAN_DEBOUNCE_S, _run)

    def _cancel_pending_replans():
        for unsub in list(pending_replans.values()):
            unsub()
        pending_replans.clear()

    entry.async_on_unload(_cancel_pending_replans)

    async def _on_ev_helper_changed(event):
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        # Ignorera första tillståndet (uppstart/återställning) och oförändrade värden
        if old_state is None or old_state.state == new_state.state:
            return

        ent_id = event.data.get("entity_id")
        if ent_id in c1_helpers:
            c1_cable_ent = config.get(CONF_EV_C1_CABLE_CONNECTED)
            c1_cable = hass.states.get(c1_cable_ent) if c1_cable_ent else None
            if _is_ev_cable_connected_state(c1_cable):
                _LOGGER.info(f"EV Helper {ent_id} changed while Car 1 connected, regenerating plan...")
                _schedule_replan("car1")
        if ent_id in c2_helpers:
            c2_cable_ent = config.get(CONF_EV_C2_CABLE_CONNECTED)
            c2_cable = hass.states.get(c2_cable_ent) if c2_cable_ent else None
            if _is_ev_cable_connected_state(c2_cable):
                _LOGGER.info(f"EV Helper {ent_id} changed while Car 2 connected, regenerating plan...")
                _schedule_replan("car2")

    all_ev_helpers = list(dict.fromkeys(c1_helpers + c2_helpers))
    if all_ev_helpers:
        entry.async_on_unload(
            async_track_state_change_event(hass, all_ev_helpers, _on_ev_helper_changed)
        )

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "switch"])
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Om laddkabeln redan är inkopplad vid uppstart eller när inställningar sparas, skapa laddplan direkt
    for car_key, cable_conf in (("car1", CONF_EV_C1_CABLE_CONNECTED), ("car2", CONF_EV_C2_CABLE_CONNECTED)):
        cable_ent = config.get(cable_conf)
        if cable_ent:
            cable_state = hass.states.get(cable_ent)
            if _is_ev_cable_connected_state(cable_state):
                _LOGGER.info(
                    "EV Cable %s already connected at setup, generating initial plan for %s...",
                    cable_ent,
                    car_key,
                )
                hass.async_create_task(coordinator.async_plan_ev_charging(car_key))

    return True

class PeakGuard:
    """Hanterar logiken för effektvakten."""

    def __init__(self, hass: HomeAssistant, config, coordinator, battery_controller):
        self.hass = hass
        self.config = config
        self.coordinator = coordinator
        self.battery = battery_controller
        self._has_reported = False
        self._hold_command_sent = False  # Flagga för att undvika upprepade kommandon
        self._capacity_exceeded_logged = False  # Flagga för att logga överlast en gång
        self._in_maintenance = False  # Flagga för underhållsläge
        self._maintenance_reason = None  # Orsak till underhållsläge
        self._maintenance_cooldown_start = None # Tidsstämpel för när underhållssignalen försvann
        self._ev_charging_paused = False  # Flagga för Prio 2 (Tvinga Spara/Vila via Elbilsladdning)
        self._last_sent_command = None  # Håller koll på senaste kommandot för att undvika spam
        self._is_updating = False  # Lås för att förhindra överlappande exekvering

    @property
    def is_active(self):
        return self._has_reported

    @property
    def in_maintenance(self):
        return self._in_maintenance

    @property
    def maintenance_reason(self):
        return self._maintenance_reason

    @property
    def ev_charging_paused(self):
        return self._ev_charging_paused

    def _has_ev_charging_sensor_configured(self) -> bool:
        return any(
            self.config.get(k)
            for k in (CONF_EV_CHARGING_SENSOR, CONF_EV_C1_IS_CHARGING, CONF_EV_C2_IS_CHARGING)
        )

    def _is_ev_charging_active(self) -> bool:
        """Kontrollerar om någon konfigurerad elbilsladdningssensor rapporterar aktiv laddning."""
        for ev_key in (CONF_EV_CHARGING_SENSOR, CONF_EV_C1_IS_CHARGING, CONF_EV_C2_IS_CHARGING):
            entity_id = self.config.get(ev_key)
            if entity_id and _is_ev_charging_state(self.hass.states.get(entity_id)):
                return True
        return False

    def _set_reported_state(self, state: bool):
        if self._has_reported != state:
            self._has_reported = state
            # När vi går in i peak-läge är ett "hold"-kommando inte längre relevant.
            if state is True:
                self._hold_command_sent = False
            else:
                # Återställ flaggor när toppen är över
                self._capacity_exceeded_logged = False
            self._last_sent_command = None
            self.coordinator.async_update_listeners()

    def _set_local_action(self, action: str, target_kw: float):
        """Uppdaterar coordinatorns data lokalt (triggar sensorer för Generic-batterier)."""
        if self.coordinator.data:
            updated = False
            if self.coordinator.data.get("action") != action:
                self.coordinator.data["action"] = action
                updated = True
            if self.coordinator.data.get("target_power_kw") != target_kw:
                self.coordinator.data["target_power_kw"] = target_kw
                updated = True
            if updated:
                self.coordinator.async_update_listeners()

    async def update(self, virtual_load_id, limit_id):
        if self._is_updating:
            return
        self._is_updating = True

        try:
            # 0. Kontrollera om Peak Shaving är aktivt (vänta tills första molnsvaret bekräftat client_mode)
            if not self.coordinator.data:
                return
            is_active = True
            limit_enforced = True
            client_mode = "ACTIVE"
            if self.coordinator.data:
                def _parse_bool(val, default=False):
                    if val is None:
                        return default
                    if isinstance(val, str):
                        v = val.strip().lower()
                        if v in ("false", "0", "no", "off", "inactive", ""):
                            return False
                        if v in ("true", "1", "yes", "on", "active"):
                            return True
                    return bool(val)

                global_active = _parse_bool(self.coordinator.data.get("is_active"), True)
                is_active = _parse_bool(self.coordinator.data.get("is_peak_shaving_active"), True)
                # Styr strypning av nätladdning enbart på backendens boolean, inte på statussträngen
                limit_enforced = global_active and is_active
                pg_status = self.coordinator.data.get("peakguard_status")
                client_mode = self.coordinator.data.get("client_mode", "ACTIVE")

                if not global_active:
                    is_active = False
                elif pg_status and str(pg_status).strip().lower().startswith(("paus", "off")):
                    # Backend skickar t.ex. "Paused", "Pausad (Elbilsladdning)", "Off".
                    # Övriga statusar ("Active (Low-Peak)", "Kapar till X kW" m.fl.) betyder att vakten är aktiv.
                    is_active = False

            if client_mode == "PASSIVE":
                # Om vi är i passivt läge låter vi Edge-enheten sköta all lokal styrning.
                # Återställ lokala flaggor så de inte stör dashboards.
                if self.is_active:
                    self._set_reported_state(False)
                if self._in_maintenance or self._ev_charging_paused:
                    self._in_maintenance = False
                    self._maintenance_reason = None
                    self._ev_charging_paused = False
                    self.coordinator.async_update_listeners()
                return

            # Om Peak Shaving är inaktiverat från backend, avbryter vi bara lastkapningen.
            if not is_active:
                # Stäng av eventuell pågående peak-hantering
                if self.is_active:
                    _LOGGER.info("PeakGuard is disabled by backend. Clearing active peak.")
                    self._set_reported_state(False)
                # OBS! Vi avbryter INTE (return) här längre.
                # Molnets action ska fortsätta respekteras lokalt oavsett denna inställning.

            # 0.1 Kontrollera Extern Paus (CheckWatt/FCR) - PRIO 1
            resumed_from_maintenance = False
            ext_entity = self.config.get(CONF_EXTERNAL_CONTROL_SENSOR)
            external_pause = _is_ext_pause_state(self.hass.states.get(ext_entity)) if ext_entity else False

            if external_pause:
                self._maintenance_cooldown_start = None
                if self._ev_charging_paused:
                    self._ev_charging_paused = False
                if not self._in_maintenance:
                    _LOGGER.info(f"⏸️ External pause sensor active ({ext_entity}). Pausing Battery Optimizer.")
                    self._in_maintenance = True
                    self._maintenance_reason = "External Control Active"
                    self._last_sent_command = None
                    self._hold_command_sent = False
                    self.coordinator.async_update_listeners()
                    # Släpp eventuella egna lås så externa system kan ta över
                    try:
                        await self.battery.apply_action("IDLE")
                    except Exception as e:
                        _LOGGER.error(f"Failed to send IDLE on external pause: {e}")

                if self.is_active:
                    self._set_reported_state(False)
                return
            elif self._in_maintenance and self._maintenance_reason == "External Control Active":
                _LOGGER.info(f"▶️ External pause sensor cleared ({ext_entity}). Resuming Battery Optimizer.")
                self._in_maintenance = False
                self._maintenance_reason = None
                self._maintenance_cooldown_start = None
                self._last_sent_command = None
                self._hold_command_sent = False
                resumed_from_maintenance = True
                self.coordinator.async_update_listeners()

            # 0.2 Kontrollera Batteristatus (Maintenance/Full Charge) - PRIO 1b
            val_display = None
            if hasattr(self.battery, "get_status_text"):
                val_display = await self.battery.get_status_text()

            if val_display is None:
                status_entity = self.config.get(CONF_BATTERY_STATUS_SENSOR)
                if status_entity:
                    status_state = self.hass.states.get(status_entity)
                    if not status_state or status_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                        _LOGGER.debug(f"Status sensor {status_entity} is unavailable/unknown. Skipping update.")
                        return
                    val_display = str(status_state.state)

            if val_display:
                # Hämta nyckelord från config (eller använd default)
                keywords_str = self.config.get(CONF_BATTERY_STATUS_KEYWORDS)
                # Fallback om konfigurationen är tom eller saknas
                if not keywords_str or not str(keywords_str).strip():
                    keywords_str = DEFAULT_BATTERY_STATUS_KEYWORDS

                keywords = [k.strip().lower() for k in keywords_str.split(",") if k.strip()]

                # Ignorera tomma värden för att undvika fladder
                if not val_display or not val_display.strip():
                    return

                val_lower = val_display.lower()

                # Debug-loggning för att spåra matchningen
                _LOGGER.debug(f"Maintenance check: Status='{val_lower}' Keywords={keywords}")

                if any(k in val_lower for k in keywords):
                    self._maintenance_cooldown_start = None # Återställ cooldown om vi ser signalen igen
                    if self._ev_charging_paused:
                        self._ev_charging_paused = False
                    if not self._in_maintenance:
                        _LOGGER.info(f"🔋 Maintenance mode detected ({val_display}). Pausing control.")
                        self._in_maintenance = True
                        self._last_sent_command = None
                        self._hold_command_sent = False
                        self.coordinator.async_update_listeners()

                    self._maintenance_reason = val_display

                    if self.is_active:
                        self._set_reported_state(False)
                    return
                elif self._in_maintenance:
                    # Signalen är borta, men vi väntar lite (debounce) för att undvika fladder
                    if self._maintenance_cooldown_start is None:
                        self._maintenance_cooldown_start = dt_util.utcnow()
                        _LOGGER.debug(f"Maintenance signal lost (Status: {val_display}). Starting 60s cooldown.")
                        return

                    if dt_util.utcnow() - self._maintenance_cooldown_start < timedelta(seconds=60):
                        return

                    _LOGGER.info(f"🔋 Maintenance mode ended. Status is '{val_display}'. Resuming control.")
                    self._in_maintenance = False
                    self._maintenance_reason = None
                    self._maintenance_cooldown_start = None
                    self._last_sent_command = None
                    self._hold_command_sent = False
                    resumed_from_maintenance = True
                    self.coordinator.async_update_listeners()

            # 0.3 Kontrollera Elbilsladdning (Tvinga Spara/Vila via Elbilsladdning) - PRIO 2
            ev_charging_local = self._is_ev_charging_active()
            ev_state_changed = False
            pg_status_str = str(pg_status or "").strip()
            is_solar_exceeds_ev = pg_status_str == "Pausad (Sol > Elbil)"
            is_stale_ev_pause = (
                not ev_charging_local
                and self._has_ev_charging_sensor_configured()
                and pg_status_str in ("Pausad (Elbilsladdning)", "Pausad (Sol > Elbil)")
            )
            is_stale_ext_pause = (
                not external_pause
                and bool(ext_entity)
                and pg_status_str == "Pausad (Extern styrning)"
            )

            if ev_charging_local:
                is_active = False
                if self.is_active:
                    _LOGGER.info("🚗 EV charging detected locally. Clearing active PeakGuard.")
                    self._set_reported_state(False)
                if not self._ev_charging_paused:
                    _LOGGER.info("🚗 EV charging active (Prio 2). Enforcing battery HOLD/save mode.")
                    self._ev_charging_paused = True
                    self._last_sent_command = None
                    self._hold_command_sent = False
                    ev_state_changed = True
                    self.coordinator.async_update_listeners()
            else:
                if self._ev_charging_paused:
                    _LOGGER.info("🚗 EV charging ended (Prio 2 cleared). Resuming normal BOLP control (Prio 3).")
                    self._ev_charging_paused = False
                    self._last_sent_command = None
                    self._hold_command_sent = False
                    ev_state_changed = True
                    resumed_from_maintenance = True
                    self.coordinator.async_update_listeners()
                if (
                    (is_stale_ev_pause or is_stale_ext_pause)
                    and global_active
                    and _parse_bool(self.coordinator.data.get("is_peak_shaving_active"), True)
                ):
                    is_active = True

            # 1. Hämta Gränsvärdet
            limit_w = None
            if self.coordinator.data and "peak_power_kw" in self.coordinator.data:
                try:
                    raw_limit = float(self.coordinator.data["peak_power_kw"])
                    limit_w = raw_limit * 1000.0 if raw_limit < 100 else raw_limit
                except (ValueError, TypeError):
                    pass

            if limit_w is None:
                limit_state = self.hass.states.get(limit_id)
                if not limit_state or limit_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                    _LOGGER.debug(f"Peak limit sensor {limit_id} is unavailable. Aborting.")
                    return
                try:
                    raw_limit = float(limit_state.state)
                    limit_w = raw_limit * 1000.0 if raw_limit < 100 else raw_limit
                except (ValueError, TypeError):
                    return

            # Skydd: Om gränsvärdet är orimligt lågt (t.ex. 0), avbryt.
            if limit_w < 100:
                _LOGGER.debug(f"Peak limit is too low ({limit_w} W). Ignoring to prevent false triggering.")
                return

            # 2. Hämta Lasten
            current_load = None

            # --- FÖRSÖK 1: Användarens konfigurerade HA-sensorer (Prio 1) ---
            if virtual_load_id:
                # Använd manuellt vald sensor
                load_state = self.hass.states.get(virtual_load_id)
                if load_state and load_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                    try:
                        current_load = float(load_state.state)
                    except ValueError:
                        pass
            else:
                # Beräkna automatiskt: Grid + Batteri
                grid_id = self.config.get(CONF_GRID_SENSOR)
                bat_id = self.config.get(CONF_BATTERY_POWER_SENSOR)
                if grid_id and bat_id:
                    grid_state = self.hass.states.get(grid_id)
                    bat_state = self.hass.states.get(bat_id)

                    # Säkerställ att minst en av dem har ett vettigt värde
                    if (grid_state and grid_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]) or \
                       (bat_state and bat_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                        try:
                            grid_val = (
                                float(grid_state.state)
                                if grid_state and grid_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
                                else 0.0
                            )
                            bat_val = (
                                float(bat_state.state)
                                if bat_state and bat_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
                                else 0.0
                            )

                            if self.config.get(CONF_BATTERY_SENSOR_INVERT, False):
                                bat_val = -bat_val

                            if self.config.get(CONF_GRID_SENSOR_INVERT, False):
                                grid_val = -grid_val
                            current_load = grid_val + bat_val
                        except ValueError:
                            pass

            # --- FÖRSÖK 2: Interna batterimetoder (Smart Fallback) ---
            if current_load is None and hasattr(self.battery, "get_virtual_load"):
                current_load = await self.battery.get_virtual_load()

            if current_load is None:
                _LOGGER.debug("Could not calculate current_load. Aborting.")
                return

            # --- TYST FILTER ---
            wake_up_threshold = limit_w * 0.90

            # Hämta moln-action tidigt för att se om vi behöver övervaka laddning
            cloud_action = "HOLD"
            if self.coordinator.data:
                if "cloud_action" in self.coordinator.data:
                    cloud_action = str(self.coordinator.data.get("cloud_action")).upper()
                elif "action" in self.coordinator.data:
                    cloud_action = str(self.coordinator.data.get("action")).upper()

            # Prio 2: Vid aktiv elbilsladdning tvingas Spara/Vila (HOLD), såvida inte molnet beordrat
            # CHARGE (parallell nätladdning) eller IDLE pga "Pausad (Sol > Elbil)" (solöverskott > hus + bil)
            if ev_charging_local and cloud_action != "CHARGE" and not is_solar_exceeds_ev:
                cloud_action = "HOLD"
            elif is_stale_ev_pause and cloud_action == "HOLD":
                # Elbilsladdningen har nyss avslutats lokalt men coordinator.data har kvar gammal EV-HOLD
                cloud_action = "IDLE"

            # Kontrollera om batteriet rör på sig (för att kunna tvinga stopp vid HOLD)
            bat_is_moving = False
            bat_val = None

            # --- FÖRSÖK 1: Användarens konfigurerade HA-sensorer ---
            bat_entity = self.config.get(CONF_BATTERY_POWER_SENSOR)
            if bat_entity:
                b_state = self.hass.states.get(bat_entity)
                if b_state and b_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                    try:
                        b_val = float(b_state.state)
                        if self.config.get(CONF_BATTERY_SENSOR_INVERT, False):
                            b_val = -b_val
                        bat_val = b_val
                        if abs(bat_val) > 100:
                            bat_is_moving = True
                    except ValueError:
                        pass

            # --- FÖRSÖK 2: Interna batterimetoder ---
            if bat_val is None and hasattr(self.battery, "get_battery_power"):
                bat_val = await self.battery.get_battery_power()
                if bat_val is not None and abs(bat_val) > 100:
                    bat_is_moving = True

            # Avbryt bara om:
            # 1. Ingen peak är aktiv.
            # 2. Vi inte precis återupptagit drift efter extern paus / underhållsläge eller ändrad EV-laddstatus.
            # 3. Lasten är under varningsgränsen.
            # 4. Vi INTE laddar (för då måste vi kolla säkringen).
            # 5. Vi INTE behöver tvinga stopp (HOLD + Battery Moving).
            if (
                not self._has_reported
                and not resumed_from_maintenance
                and not ev_state_changed
                and not (ev_charging_local and self._last_sent_command != "HOLD")
                and current_load < wake_up_threshold
                and cloud_action != "CHARGE"
                and not (cloud_action == "HOLD" and bat_is_moving)
            ):
                return

            # 3. Hämta SoC
            soc = None
            if hasattr(self.battery, "get_current_soc"):
                soc = await self.battery.get_current_soc()

            if soc is None:
                soc_entity = self.config.get(CONF_SOC_SENSOR)
                if soc_entity:
                    soc_state = self.hass.states.get(soc_entity)
                    if soc_state and soc_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                        try:
                            soc = float(soc_state.state)
                        except ValueError:
                            pass

            if soc is None:
                soc = 0.0

            # 4. Gränser
            safe_limit = limit_w - 1000

            # Kontrollera om molnet redan kör obegränsad IDLE (egenförbrukning / Mode 2).
            # I obegränsad IDLE täcker växelriktaren automatiskt 100 % av husets last ned till 0 W
            # (vilket är betydligt strängare än limit_w). Om PeakGuard då skulle tvinga in manuell
            # DISCHARGE(current_load - limit_w) stryps batteriurladdningen till endast överskottet
            # ovanför limit_w! Undantag: om Skyddad Solladdning spärrar urladdning (export_limit == 0).
            site_limits_check = (
                (self.coordinator.data.get("site_limits") or self.coordinator.data.get("sonnen_site_limits"))
                if self.coordinator.data
                else None
            )
            is_protected_solar_idle = (
                isinstance(site_limits_check, dict)
                and site_limits_check.get("p_bess_inv_max_export_limit") == 0
            )
            is_unrestricted_idle = (cloud_action == "IDLE" and not is_protected_solar_idle)

            # --- NY LOGIK MED HYSTERES ---

            # Steg 1: Bestäm tillstånd (På / Av)
            if is_unrestricted_idle:
                if self._has_reported:
                    _LOGGER.info(
                        f"✅ PEAK CLEARED (Cloud is in unrestricted IDLE / Self-Consumption). "
                        f"Load: {current_load} W. Returning to IDLE so battery covers full house load."
                    )
                    self._set_reported_state(False)
                    await self._report_peak_clear(current_load, limit_w)
            elif is_active and not self._has_reported and current_load > limit_w and soc > 0:
                _LOGGER.info(f"🚨 PEAK DETECTED! Load: {current_load} W > Limit: {limit_w} W. Engaging battery.")
                self._set_reported_state(True)
                await self._report_peak(current_load, limit_w)

            elif self._has_reported and current_load <= safe_limit:
                _LOGGER.info(f"✅ PEAK CLEARED. Load: {current_load} W. Returning to strategy.")
                self._set_reported_state(False)
                await self._report_peak_clear(current_load, limit_w)

            # Steg 2: Agera baserat på tillstånd
            if self._has_reported and soc > 0:
                # TILLSTÅND PÅ: Justera urladdning
                max_inverter = 3300.0
                if self.coordinator.data and "max_discharge_kw" in self.coordinator.data:
                    val = self.coordinator.data.get("max_discharge_kw")
                    if val is not None:
                        max_inverter = float(val) * 1000.0

                need = current_load - limit_w

                # Detektera om vi inte klarar att hålla gränsen
                if need > max_inverter:
                    if not self._capacity_exceeded_logged:
                        _LOGGER.warning(
                            f"PeakGuard capacity exceeded! Need: {need} W > Max: {max_inverter} W. "
                            f"Limit {limit_w} W cannot be held."
                        )
                        self._capacity_exceeded_logged = True
                        await self._report_peak_failure(current_load, limit_w)

                power_to_discharge = min(max(0, need), max_inverter)

                if power_to_discharge > 100:  # Skicka bara kommando om det finns ett verkligt behov
                    self._set_local_action("DISCHARGE", power_to_discharge / 1000.0)
                    await self.battery.apply_action("DISCHARGE", power_to_discharge / 1000.0)
                    self._last_sent_command = "PEAK"

            else:
                # TILLSTÅND AV: Återgå till molnstrategi
                # cloud_action är redan hämtad ovan

                if cloud_action != "HOLD":
                    self._hold_command_sent = False  # Återställ om molnet vill något annat

                if cloud_action == "CHARGE":
                    # Kontrollera att laddning inte överskrider gränsvärdet
                    target_kw = 0.0
                    if self.coordinator.data:
                        if "cloud_target_power_kw" in self.coordinator.data:
                            target_kw = float(self.coordinator.data.get("cloud_target_power_kw", 0.0))
                        elif "target_power_kw" in self.coordinator.data:
                            target_kw = float(self.coordinator.data.get("target_power_kw", 0.0))

                    target_w = target_kw * 1000.0
                    # Marginal på 200W för att vara säker (endast om en effektgräns gäller)
                    available_w = (limit_w - current_load - 200.0) if limit_enforced else target_w

                    if limit_enforced and target_w > available_w:
                        throttled_w = max(0, int(available_w))
                        # Avrunda till närmaste 50W för att minska fladder
                        throttled_w = int(throttled_w / 50) * 50

                        _LOGGER.warning(
                            f"⚠️ CHARGE THROTTLED! Cloud: {target_w} W. Available: {available_w:.0f} W. "
                            f"Limit: {limit_w} W. Setting: {throttled_w} W."
                        )
                        self._set_local_action("CHARGE", throttled_w / 1000.0)
                        await self.battery.apply_action("CHARGE", throttled_w / 1000.0)
                        self._last_sent_command = "CHARGE"
                    else:
                        self._set_local_action("CHARGE", target_kw)
                        if self._last_sent_command != "CHARGE_UNTHROTTLED":
                            await self.battery.apply_action("CHARGE", target_kw)
                            self._last_sent_command = "CHARGE_UNTHROTTLED"

                elif cloud_action == "DISCHARGE":
                    target_kw = 0.0
                    if self.coordinator.data:
                        if "cloud_target_power_kw" in self.coordinator.data:
                            target_kw = float(self.coordinator.data.get("cloud_target_power_kw", 0.0))
                        elif "target_power_kw" in self.coordinator.data:
                            target_kw = float(self.coordinator.data.get("target_power_kw", 0.0))
                    self._set_local_action("DISCHARGE", target_kw)
                    if self._last_sent_command != "DISCHARGE":
                        await self.battery.apply_action("DISCHARGE", target_kw)
                        self._last_sent_command = "DISCHARGE"

                elif cloud_action == "HOLD":
                    self._set_local_action("HOLD", 0.0)
                    bat_power = None

                    # --- FÖRSÖK 1: Användarens konfigurerade HA-sensorer ---
                    bat_entity = self.config.get(CONF_BATTERY_POWER_SENSOR)
                    if bat_entity:
                        bat_state = self.hass.states.get(bat_entity)
                        if bat_state and bat_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
                            try:
                                bat_power = float(bat_state.state)
                                if self.config.get(CONF_BATTERY_SENSOR_INVERT, False):
                                    bat_power = -bat_power
                            except ValueError:
                                pass

                    # --- FÖRSÖK 2: Interna batterimetoder ---
                    if bat_power is None and hasattr(self.battery, "get_battery_power"):
                        bat_power = await self.battery.get_battery_power()

                    if bat_power is None:
                        bat_power = 0.0

                    is_hold_violation = (
                        bat_power > 100
                        if getattr(self.battery, "is_modern_ems", False) is True
                        else abs(bat_power) > 100
                    )

                    if (
                        is_hold_violation
                        or resumed_from_maintenance
                        or ev_state_changed
                        or (ev_charging_local and self._last_sent_command != "HOLD")
                    ):
                        if not self._hold_command_sent:
                            _LOGGER.info(
                                f"⚙️ Executing HOLD command. Battery is active ({bat_power} W), "
                                "enforcing pause."
                            )
                            site_limits = (
                                self.coordinator.data.get("sonnen_site_limits") if self.coordinator.data else None
                            )
                            try:
                                if site_limits is not None:
                                    await self.battery.apply_action("HOLD", sonnen_site_limits=site_limits)
                                else:
                                    await self.battery.apply_action("HOLD")
                            except TypeError:
                                await self.battery.apply_action("HOLD")
                            self._hold_command_sent = True
                            self._last_sent_command = "HOLD"
                    else:
                        # Batteriet är redan stilla, så nollställ flaggan.
                        if self._hold_command_sent:
                            _LOGGER.debug("Battery is now idle, resetting hold_command_sent flag.")
                        self._hold_command_sent = False

                elif cloud_action == "IDLE":
                    self._set_local_action("IDLE", 0.0)
                    if self._last_sent_command != "IDLE":
                        _LOGGER.info(
                            "⚙️ Executing IDLE (Auto) command to battery. "
                            f"(CloudAction={cloud_action})"
                        )
                        site_limits = (
                            self.coordinator.data.get("sonnen_site_limits") if self.coordinator.data else None
                        )
                        try:
                            if site_limits is not None:
                                await self.battery.apply_action("IDLE", sonnen_site_limits=site_limits)
                            else:
                                await self.battery.apply_action("IDLE")
                        except TypeError:
                            await self.battery.apply_action("IDLE")
                        self._last_sent_command = "IDLE"

                else:
                    pass  # Okänt läge -> Gör inget
        except Exception as e:
            _LOGGER.error(f"Error in PeakGuard update: {e}", exc_info=True)
        finally:
            self._is_updating = False

    @property
    def _base_api_url(self) -> str:
        raw_url = str(self.config.get(CONF_API_URL, "")).strip().rstrip("/")
        if raw_url and not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raw_url = f"https://{raw_url}"
        return raw_url

    async def _report_peak(self, grid_w, limit_w):
        try:
            api_url = f"{self._base_api_url}/report_peak"
            payload = {
                "grid_power_kw": round(grid_w / 1000.0, 2),
                "limit_kw": round(limit_w / 1000.0, 2)
            }
            headers = {"X-API-Key": self.config[CONF_API_KEY]}
            session = async_get_clientsession(self.hass)
            async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.debug(f"Cloud report sent: PeakGuard Triggered: {payload['grid_power_kw']} kW")
        except Exception as e:
            _LOGGER.error(f"Failed to report peak: {e}")

    async def _report_peak_clear(self, grid_w, limit_w):
        try:
            api_url = f"{self._base_api_url}/report_peak_clear"
            payload = {
                "grid_power_kw": round(grid_w / 1000.0, 2),
                "limit_kw": round(limit_w / 1000.0, 2)
            }
            headers = {"X-API-Key": self.config[CONF_API_KEY]}
            session = async_get_clientsession(self.hass)
            async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.debug(f"Cloud report sent: PeakGuard Cleared: {payload['grid_power_kw']} kW")
        except Exception as e:
            _LOGGER.error(f"Failed to report peak clear: {e}")

    async def _report_peak_failure(self, grid_w, limit_w):
        try:
            api_url = f"{self._base_api_url}/report_peak_failure"
            payload = {
                "grid_power_kw": round(grid_w / 1000.0, 2),
                "limit_kw": round(limit_w / 1000.0, 2)
            }
            headers = {"X-API-Key": self.config[CONF_API_KEY]}
            session = async_get_clientsession(self.hass)
            async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    _LOGGER.debug(f"Cloud report sent: PeakGuard Failure: {payload['grid_power_kw']} kW")
        except Exception as e:
            _LOGGER.error(f"Failed to report peak failure: {e}")


async def update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor", "switch"])
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(coordinator, "unsub_timer") and callable(coordinator.unsub_timer):
            coordinator.unsub_timer()
    return unload_ok

class BatteryOptimizerGraphView(HomeAssistantView):
    """Exponerar grafdata via ett internt API för att slippa 16KB-gränsen på sensorattribut."""
    url = "/api/battery_optimizer_graph_data"
    name = "api:battery_optimizer_graph_data"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def get(self, request):
        result = {}
        domain_data = self.hass.data.get(DOMAIN, {})
        for entry_id, coordinator in domain_data.items():
            if hasattr(coordinator, "data"):
                graph_data = coordinator.data.get("graph_data", {}) if coordinator.data else {}
                result[entry_id] = graph_data
        return self.json(result)

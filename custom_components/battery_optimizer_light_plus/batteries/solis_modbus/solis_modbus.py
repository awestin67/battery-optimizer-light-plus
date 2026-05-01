# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import logging
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.exceptions import ServiceNotFound
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

# Möjliga 'translation_key' eller delar av 'object_id' för entiteter.
KEYS_RC_MODE = ["rc_force_charge_discharge", "rc_mode", "remote_control_mode"]
KEYS_RC_CHARGE_POWER = ["rc_force_charge_power", "rc_charge_power", "charge_power_limit"]
KEYS_RC_DISCHARGE_POWER = ["rc_force_discharge_power", "rc_discharge_power", "discharge_power_limit"]
KEYS_RC_TIMEOUT = ["rc_timeout", "timeout"]
KEYS_BATTERY_DISCHARGE_LIMIT = ["battery_discharge_limit_power", "discharge_limit_power"]

class SolisModbusBattery(BatteryApi):
    """A class to interact with the Solis Modbus battery integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        soc_entity: str,
        device_status_entity: str | None = None,
        max_discharge_entity: str | None = None,
        grid_entity: str | None = None,
        invert_grid: bool = False
    ):
        """Initialize the SolisModbusBattery object."""
        self._hass = hass
        self._device_id = device_id
        self._soc_entity = soc_entity
        self._device_status_entity = device_status_entity
        self._max_discharge_entity = max_discharge_entity
        self._grid_entity = grid_entity
        self._invert_grid = invert_grid

    def _get_related_devices(self) -> set[str]:
        """Hämtar alla relaterade enhets-ID:n inom samma Solis-integration."""
        from homeassistant.helpers import device_registry as dr
        dr_reg = dr.async_get(self._hass)
        related_devices = {self._device_id}
        device = dr_reg.async_get(self._device_id)
        if device and device.config_entries:
            config_entry_id = next(iter(device.config_entries))
            for dev in dr_reg.devices.values():
                if config_entry_id in dev.config_entries:
                    related_devices.add(dev.id)
        return related_devices

    async def _find_entity(self, domain: str, partial_keys: list[str]) -> str | None:
        """Hittar en entitet dynamiskt genom att testa flera möjliga nyckelord."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain == domain:
                    name_check = (
                        f"{entry.translation_key or ''} "
                        f"{entry.object_id or ''} "
                        f"{entry.unique_id or ''}"
                    ).lower()
                    for key in partial_keys:
                        if key in name_check:
                            _LOGGER.debug(f"Found entity {entry.entity_id} for key {key}")
                            return entry.entity_id

        _LOGGER.warning(f"Could not find any {domain} entity with keys matching '{partial_keys}'")
        return None

    def _get_rc_option(self, entity_id: str, mode: str) -> str:
        """Hittar rätt driftläge i dropdown-menyn oavsett integrationens version."""
        state = self._hass.states.get(entity_id)
        options = state.attributes.get("options", []) if state else []
        for opt in options:
            opt_lower = opt.lower()
            if mode == "charge" and "charge" in opt_lower and "discharge" not in opt_lower:
                return opt
            if mode == "discharge" and "discharge" in opt_lower:
                return opt
            if mode == "none" and ("none" in opt_lower or "auto" in opt_lower or "self" in opt_lower):
                return opt
        if mode == "charge":
            return "Solis RC Force Battery Charge"
        if mode == "discharge":
            return "Solis RC Force Battery Discharge"
        return "None"

    async def get_current_soc(self) -> float | None:
        """Get the battery's state of charge (SoC)."""
        if not self._soc_entity:
            return None

        soc_state = self._hass.states.get(self._soc_entity)
        if soc_state and soc_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(soc_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid SoC value: {soc_state.state}")
                return None
        return None

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        action_upper = action.upper()

        try:
            # TODO: Implementera den specifika Solis Modbus-logiken här.
            # Om du till exempel behöver anropa en service för att sätta 'Timed Charge/Discharge'
            # eller ändra en number-entitet.
            _LOGGER.debug(f"Solis Modbus applying action: {action_upper} with {power_w} W")
            # 1. Hitta relevanta entiteter dynamiskt
            mode_select_entity = await self._find_entity("select", KEYS_RC_MODE)
            charge_power_entity = await self._find_entity("number", KEYS_RC_CHARGE_POWER)
            discharge_power_entity = await self._find_entity("number", KEYS_RC_DISCHARGE_POWER)
            timeout_entity = await self._find_entity("number", KEYS_RC_TIMEOUT)
            discharge_limit_entity = await self._find_entity("number", KEYS_BATTERY_DISCHARGE_LIMIT)

            if not mode_select_entity:
                _LOGGER.error("Could not find Solis RC mode select entity. Cannot control battery.")
                return

            opt_charge = self._get_rc_option(mode_select_entity, "charge")
            opt_discharge = self._get_rc_option(mode_select_entity, "discharge")
            opt_none = self._get_rc_option(mode_select_entity, "none")

            # Eftersom PeakGuard uppdaterar var 5:e minut och 30s sätter vi timeout till 15 minuter
            # för att förhindra att växelriktaren stänger av kommandot för tidigt.
            if timeout_entity and action_upper in ["CHARGE", "DISCHARGE", "HOLD"]:
                try:
                    await self._hass.services.async_call(
                        "number", "set_value",
                        {"entity_id": timeout_entity, "value": 15},
                        blocking=False,
                    )
                except Exception as e:
                    _LOGGER.debug(f"Failed to set RC timeout: {e}")

            # Säkerställ att eventuell paus släpps om vi ska styra batteriet
            if action_upper in ["CHARGE", "DISCHARGE"] and discharge_limit_entity:
                state_obj = self._hass.states.get(discharge_limit_entity)
                if state_obj:
                    try:
                        if float(state_obj.state) == 0:
                            max_val = state_obj.attributes.get("max", 5000)
                            await self._hass.services.async_call(
                                "number", "set_value",
                                {"entity_id": discharge_limit_entity, "value": max_val},
                                blocking=False,
                            )
                    except ValueError:
                        pass

            # 2. Agera baserat på action
            if action_upper == "CHARGE":
                if not charge_power_entity:
                    _LOGGER.error("Could not find Solis RC charge power number entity.")
                    return

                val = power_w
                state = self._hass.states.get(charge_power_entity)
                if state:
                    min_val = state.attributes.get("min")
                    max_val = state.attributes.get("max")
                    if min_val is not None and val < float(min_val):
                        _LOGGER.debug(
                            f"Solis: Begränsar laddningseffekt från {val} W "
                            f"till växelriktarens gräns {min_val} W"
                        )
                        val = int(float(min_val))
                    if max_val is not None and val > float(max_val):
                        _LOGGER.debug(
                            f"Solis: Begränsar laddningseffekt från {val} W "
                            f"till växelriktarens gräns {max_val} W"
                        )
                        val = int(float(max_val))

                # Sätt laddeffekt
                await self._hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": charge_power_entity, "value": val},
                    blocking=True,
                )
                # Sätt läge till RC Charge
                await self._hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": mode_select_entity, "option": opt_charge},
                    blocking=True,
                )
                _LOGGER.info(f"Solis: Set mode to RC Charge with {power_w} W.")

            elif action_upper == "DISCHARGE":
                if not discharge_power_entity:
                    _LOGGER.error("Could not find Solis RC discharge power number entity.")
                    return

                val = power_w
                state = self._hass.states.get(discharge_power_entity)
                if state:
                    min_val = state.attributes.get("min")
                    max_val = state.attributes.get("max")
                    if min_val is not None and val < float(min_val):
                        _LOGGER.debug(
                            f"Solis: Begränsar urladdningseffekt från {val} W "
                            f"till växelriktarens gräns {min_val} W"
                        )
                        val = int(float(min_val))
                    if max_val is not None and val > float(max_val):
                        _LOGGER.debug(
                            f"Solis: Begränsar urladdningseffekt från {val} W "
                            f"till växelriktarens gräns {max_val} W"
                        )
                        val = int(float(max_val))

                # Sätt urladdningseffekt
                await self._hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": discharge_power_entity, "value": val},
                    blocking=True,
                )
                # Sätt läge till RC Discharge
                await self._hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": mode_select_entity, "option": opt_discharge},
                    blocking=True,
                )
                _LOGGER.info(f"Solis: Set mode to RC Discharge with {power_w} W.")

            elif action_upper == "HOLD":
                if not discharge_limit_entity:
                    _LOGGER.error("Could not find Solis discharge limit number entity for HOLD.")
                    return

                # Sätt urladdningsgräns till 0 W för att pausa batteriet
                await self._hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": discharge_limit_entity, "value": 0},
                    blocking=True,
                )
                # Säkerställ att RC-styrningen är avstängd (Auto) så solcellerna får ladda
                await self._hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": mode_select_entity, "option": opt_none},
                    blocking=True,
                )
                _LOGGER.info("Solis: Set Discharge Limit to 0 W for HOLD.")

            elif action_upper == "IDLE":
                if discharge_limit_entity:
                    # Återställ urladdningsgränsen till max (Home Assistant vet vad max är via attributet)
                    state_obj = self._hass.states.get(discharge_limit_entity)
                    max_val = state_obj.attributes.get("max", 5000) if state_obj else 5000

                    await self._hass.services.async_call(
                        "number", "set_value",
                        {"entity_id": discharge_limit_entity, "value": max_val},
                        blocking=True,
                    )
                # IDLE betyder att vi stänger av RC-läget och återgår till Auto
                await self._hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": mode_select_entity, "option": opt_none},
                    blocking=True,
                )
                _LOGGER.info(f"Solis: Restored discharge limit and set mode to {opt_none} (Auto) for IDLE.")

            else:
                _LOGGER.warning(f"Unknown action for Solis: {action}")

        except ServiceNotFound as e:
            _LOGGER.warning("Solis service not found: %s. A required integration might not be loaded.", e)
        except Exception as e:
            _LOGGER.error("Fel vid aktivering av Solis Modbus-åtgärd '%s': %s", action, e, exc_info=True)

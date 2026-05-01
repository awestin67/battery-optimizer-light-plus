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
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class SigenergyBattery(BatteryApi):
    """A class to interact with the Sigenergy battery integration."""

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
        """Initialize the SigenergyBattery object."""
        self._hass = hass
        self._device_id = device_id
        self._soc_entity = soc_entity
        self._device_status_entity = device_status_entity
        self._max_discharge_entity = max_discharge_entity
        self._grid_entity = grid_entity
        self._invert_grid = invert_grid

    async def get_current_soc(self) -> float | None:
        """Get the battery's state of charge (SoC)."""
        if not self._soc_entity:
            return None

        soc_state = self._hass.states.get(self._soc_entity)
        if soc_state and soc_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(soc_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid SoC value from Sigenergy: {soc_state.state}")
                return None
        return None

    def _get_related_devices(self) -> set[str]:
        """Hittar alla enheter som tillhör samma config_entry."""
        registry = dr.async_get(self._hass)
        device = registry.devices.get(self._device_id)
        if not device:
            return {self._device_id}

        related_devices = set()
        for entry_id in device.config_entries:
            for dev in registry.devices.values():
                if entry_id in dev.config_entries:
                    related_devices.add(dev.id)
        return related_devices

    async def _find_entity(self, domain: str, partial_keys: list[str]) -> str | None:
        """Hittar en entitet dynamiskt genom att testa flera möjliga nyckelord."""
        registry = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        for dev_id in related_devices:
            entries = er.async_entries_for_device(registry, dev_id)
            for entry in entries:
                if entry.domain == domain:
                    name_check = (
                        f"{entry.translation_key or ''} "
                        f"{entry.object_id or ''} "
                        f"{entry.unique_id or ''}"
                    ).lower()
                    for key in partial_keys:
                        if key in name_check:
                            return entry.entity_id
        return None

    def _get_target_val(self, entity_id: str, target_kw: float) -> float:
        """Säkerställer rätt enhet (W vs kW) dynamiskt utifrån sensorns inbyggda max-gräns."""
        state = self._hass.states.get(entity_id)
        is_kw = True
        if state and "max" in state.attributes:
            try:
                if float(state.attributes["max"]) > 500:
                    is_kw = False
            except ValueError:
                pass
        return target_kw if is_kw else float(int(target_kw * 1000))

    def _get_sigenergy_mode(self, entity_id: str, mode: str) -> str:
        """Hittar rätt driftläge i dropdown-menyn oavsett integrationens version."""
        state = self._hass.states.get(entity_id)
        options = state.attributes.get("options", []) if state else []
        for opt in options:
            opt_lower = opt.lower()
            if mode == "charge" and "charging" in opt_lower:
                return opt
            if mode == "discharge" and "discharging" in opt_lower:
                return opt
            if mode == "standby" and "standby" in opt_lower:
                return opt
            if mode == "idle" and "maximum self consumption" in opt_lower:
                return opt
        if mode == "charge":
            return "Command Charging (PV First)"
        if mode == "discharge":
            return "Command Discharging (PV First)"
        if mode == "standby":
            return "Standby"
        return "Maximum Self Consumption"

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        mode_entity = await self._find_entity(
            "select", ["ems_control_mode", "control_mode"]
        )
        charge_power_entity = await self._find_entity(
            "number", ["max_charging_limit", "max_charge_power", "charging_limit"]
        )
        discharge_power_entity = await self._find_entity(
            "number", ["max_discharging_limit", "max_discharge_power", "discharging_limit"]
        )

        if not mode_entity:
            _LOGGER.warning("Sigenergy: Kunde inte hitta 'select'-entiteten för ems_control_mode.")
            return

        opt_charge = self._get_sigenergy_mode(mode_entity, "charge")
        opt_discharge = self._get_sigenergy_mode(mode_entity, "discharge")
        opt_standby = self._get_sigenergy_mode(mode_entity, "standby")
        opt_idle = self._get_sigenergy_mode(mode_entity, "idle")

        try:
            if action == "CHARGE":
                if charge_power_entity:
                    val = self._get_target_val(charge_power_entity, target_kw)
                    state = self._hass.states.get(charge_power_entity)
                    if state:
                        min_val = state.attributes.get("min")
                        max_val = state.attributes.get("max")
                        if min_val is not None and val < float(min_val):
                            _LOGGER.debug(
                                f"Sigenergy: Begränsar laddningseffekt från {val} kW "
                                f"till växelriktarens gräns {min_val} kW"
                            )
                            val = float(min_val)
                        if max_val is not None and val > float(max_val):
                            _LOGGER.debug(
                                f"Sigenergy: Begränsar laddningseffekt från {val} kW "
                                f"till växelriktarens gräns {max_val} kW"
                            )
                            val = float(max_val)

                    await self._hass.services.async_call(
                        "number",
                        "set_value",
                        {"entity_id": charge_power_entity, "value": val},
                        blocking=True,
                    )
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": opt_charge},
                    blocking=True,
                )

            elif action == "DISCHARGE":
                if discharge_power_entity:
                    val = self._get_target_val(discharge_power_entity, target_kw)
                    state = self._hass.states.get(discharge_power_entity)
                    if state:
                        min_val = state.attributes.get("min")
                        max_val = state.attributes.get("max")
                        if min_val is not None and val < float(min_val):
                            _LOGGER.debug(
                                f"Sigenergy: Begränsar urladdningseffekt från {val} kW "
                                f"till växelriktarens gräns {min_val} kW"
                            )
                            val = float(min_val)
                        if max_val is not None and val > float(max_val):
                            _LOGGER.debug(
                                f"Sigenergy: Begränsar urladdningseffekt från {val} kW "
                                f"till växelriktarens gräns {max_val} kW"
                            )
                            val = float(max_val)

                    await self._hass.services.async_call(
                        "number",
                        "set_value",
                        {"entity_id": discharge_power_entity, "value": val},
                        blocking=True,
                    )
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": opt_discharge},
                    blocking=True,
                )

            elif action == "HOLD":
                # Sätt effektgränserna till 0 för att vara säker på att batteriet pausas
                if charge_power_entity:
                    await self._hass.services.async_call(
                        "number", "set_value", {"entity_id": charge_power_entity, "value": 0}, blocking=True
                    )
                if discharge_power_entity:
                    await self._hass.services.async_call(
                        "number", "set_value", {"entity_id": discharge_power_entity, "value": 0}, blocking=True
                    )
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": opt_standby},
                    blocking=True,
                )

            elif action == "IDLE":
                for entity_id in [charge_power_entity, discharge_power_entity]:
                    if entity_id:
                        state = self._hass.states.get(entity_id)
                        # Säkrare fallback-värde än 100.0 kW
                        max_val = 15.0
                        if state and "max" in state.attributes:
                            try:
                                max_val = float(state.attributes["max"])
                            except (ValueError, TypeError):
                                _LOGGER.warning(f"Could not parse 'max' attribute for {entity_id}")
                        await self._hass.services.async_call(
                            "number",
                            "set_value",
                            {"entity_id": entity_id, "value": max_val},
                            blocking=True,
                        )
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": opt_idle},
                    blocking=True,
                )

        except (ServiceNotFound, HomeAssistantError) as e:
            _LOGGER.warning(f"Sigenergy service call failed: {e}")
        except Exception as e:
            _LOGGER.error(f"Fel vid applicering av Sigenergy-kommando: {e}", exc_info=True)

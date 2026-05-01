# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class SolintegBattery(BatteryApi):
    """A class to interact with a Solinteg battery integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        soc_entity: str,
        device_status_entity: str | None = None,
        max_discharge_entity: str | None = None,
        grid_entity: str | None = None,
        invert_grid: bool = False,
        invert_battery: bool = False
    ):
        """Initialize the SolintegBattery object."""
        self._hass = hass
        self._device_id = device_id
        self._soc_entity = soc_entity
        self._device_status_entity = device_status_entity
        self._max_discharge_entity = max_discharge_entity
        self._grid_entity = grid_entity
        self._invert_grid = invert_grid
        self._invert_battery = invert_battery

    async def get_current_soc(self) -> float | None:
        """Hämtar batteriets laddningsnivå (SoC)."""
        if not self._soc_entity:
            return None
        state = self._hass.states.get(self._soc_entity)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                pass
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

    def _get_solinteg_mode(self, entity_id: str, mode: str) -> str:
        """Hittar rätt driftläge i dropdown-menyn oavsett integrationens version."""
        state = self._hass.states.get(entity_id)
        options = state.attributes.get("options", []) if state else []
        for opt in options:
            opt_lower = opt.lower()
            if mode == "auto" and ("self" in opt_lower or "auto" in opt_lower):
                return opt
            if mode == "manual" and (
                "charge" in opt_lower or "discharge" in opt_lower or
                "manual" in opt_lower or "ems" in opt_lower
            ):
                return opt
        return "Self Use" if mode == "auto" else "Charge-Discharge"

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        _LOGGER.debug(f"Solinteg applying action: {action} with target {power_w} W")

        working_mode_entity = await self._find_entity(
            "select", ["working_mode", "operation_mode", "mode"]
        )
        power_target_entity = await self._find_entity(
            "number", ["charge_discharge_power", "power_target", "charge_power"]
        )

        if not working_mode_entity:
            _LOGGER.error(f"Solinteg: Kunde inte hitta working_mode entitet för enhet {self._device_id}")
            return

        opt_auto = self._get_solinteg_mode(working_mode_entity, "auto")
        opt_manual = self._get_solinteg_mode(working_mode_entity, "manual")

        # Bestäm läge och effekt
        mode = opt_auto
        target_val = 0

        if action == "IDLE":
            mode = opt_auto
        elif action == "HOLD":
            mode = opt_manual
            target_val = 0
        elif action == "CHARGE":
            mode = opt_manual
            target_val = power_w if self._invert_battery else -power_w
        elif action == "DISCHARGE":
            mode = opt_manual
            target_val = -power_w if self._invert_battery else power_w

        # Kontrollera och begränsa effekten utifrån växelriktarens gränser (min/max)
        if power_target_entity and action in ["CHARGE", "DISCHARGE"]:
            target_state = self._hass.states.get(power_target_entity)
            if target_state:
                min_val = target_state.attributes.get("min")
                max_val = target_state.attributes.get("max")
                if min_val is not None and target_val < float(min_val):
                    _LOGGER.debug(
                        f"Solinteg: Begränsar laddningseffekt från {target_val} W "
                        f"till växelriktarens gräns {min_val} W"
                    )
                    target_val = int(float(min_val))
                if max_val is not None and target_val > float(max_val):
                    _LOGGER.debug(
                        f"Solinteg: Begränsar urladdningseffekt från {target_val} W "
                        f"till växelriktarens gräns {max_val} W"
                    )
                    target_val = int(float(max_val))

        # Sätt driftläget
        await self._hass.services.async_call(
            "select", "select_option",
            {"entity_id": working_mode_entity, "option": mode},
            blocking=True
        )

        # Sätt effekten om en number-entitet hittades (och vi inte är i IDLE)
        if power_target_entity and action != "IDLE":
            await self._hass.services.async_call(
                "number", "set_value",
                {"entity_id": power_target_entity, "value": target_val},
                blocking=True
            )

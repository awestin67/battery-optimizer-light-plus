# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import logging
from homeassistant.core import HomeAssistant
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

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        _LOGGER.debug(f"Solinteg applying action: {action} with target {power_w} W")

        registry = er.async_get(self._hass)
        entries = er.async_entries_for_device(registry, self._device_id)

        working_mode_entity = None
        power_target_entity = None

        for entry in entries:
            name_check = entry.unique_id or entry.entity_id
            if entry.domain == "select" and "working_mode" in name_check:
                working_mode_entity = entry.entity_id
            if entry.domain == "number" and ("charge_discharge_power" in name_check or "power_target" in name_check):
                power_target_entity = entry.entity_id

        if not working_mode_entity:
            _LOGGER.error(f"Solinteg: Kunde inte hitta working_mode entitet för enhet {self._device_id}")
            return

        # Bestäm läge och effekt
        mode = "Self Use" # Standard Auto-läge
        target_val = 0

        if action == "IDLE":
            mode = "Self Use"
        elif action == "HOLD":
            mode = "Charge-Discharge"
            target_val = 0
        elif action == "CHARGE":
            mode = "Charge-Discharge"
            target_val = power_w if self._invert_battery else -power_w
        elif action == "DISCHARGE":
            mode = "Charge-Discharge"
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

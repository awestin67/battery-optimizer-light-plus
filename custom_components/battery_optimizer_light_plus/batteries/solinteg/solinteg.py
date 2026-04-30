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
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
        invert_grid: bool = False
    ):
        """Initialize the SolintegBattery object."""
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
                _LOGGER.warning(f"Invalid SoC value from Solinteg: {soc_state.state}")
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

    async def _find_entity(self, domain: str, partial_key: str) -> str | None:
        """Hittar en entitet baserat på domän och en del av dess unique_id."""
        registry = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        for dev_id in related_devices:
            entries = er.async_entries_for_device(registry, dev_id)
            for entry in entries:
                if entry.domain == domain and partial_key in entry.unique_id:
                    _LOGGER.debug(f"Found entity {entry.entity_id} for key {partial_key}")
                    return entry.entity_id

        _LOGGER.warning(f"Could not find any {domain} entity with unique_id containing '{partial_key}'")
        return None

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        mode_entity = await self._find_entity("select", "working_mode")
        power_entity = await self._find_entity("number", "battery_charge_discharge_power_target")

        if not mode_entity or not power_entity:
            _LOGGER.error("Could not find all required Solinteg entities (working_mode, "
                          "battery_charge_discharge_power_target).")
            return

        try:
            if action == "CHARGE":
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": "EMS BattCtrl"},
                    blocking=True,
                )
                await self._hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": power_entity, "value": -target_kw},
                    blocking=True,
                )
            elif action == "DISCHARGE":
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": "EMS BattCtrl"},
                    blocking=True,
                )
                await self._hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": power_entity, "value": target_kw},
                    blocking=True,
                )
            elif action == "HOLD":
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": "EMS BattCtrl"},
                    blocking=True,
                )
                await self._hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": power_entity, "value": 0},
                    blocking=True,
                )
            elif action == "IDLE":
                # Återställ effekten till 0 för säkerhets skull innan vi byter läge
                await self._hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": power_entity, "value": 0},
                    blocking=True,
                )
                await self._hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": mode_entity, "option": "General"},
                    blocking=True,
                )

        except (ServiceNotFound, HomeAssistantError) as e:
            _LOGGER.warning(f"Solinteg service call failed: {e}")
        except Exception as e:
            _LOGGER.error(f"Fel vid applicering av Solinteg-kommando: {e}", exc_info=True)

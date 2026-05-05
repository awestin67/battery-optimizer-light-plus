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
from homeassistant.exceptions import ServiceNotFound
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

class HuaweiBattery(BatteryApi):
    """A class to interact with the Huawei battery."""

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
        """Initialize the HuaweiBattery object."""
        self._hass = hass
        self._device_id = device_id
        self._soc_entity = soc_entity
        self._device_status_entity = device_status_entity
        self._max_discharge_entity = max_discharge_entity
        self._grid_entity = grid_entity
        self._invert_grid = invert_grid

    def _get_related_devices(self) -> set[str]:
        """Hämtar alla relaterade enhets-ID:n (Inverter, Batteri, Meter) inom samma Huawei-integration."""
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

    async def get_current_soc(self) -> float | None:
        """Get the battery's state of charge (SoC)."""
        soc_state = self._hass.states.get(self._soc_entity)
        if soc_state and soc_state.state not in ("unknown", "unavailable"):
            try:
                return float(soc_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid SoC value: {soc_state.state}")
                return None
        return None

    async def get_status_text(self) -> str | None:
        """Hämtar enhetsstatus för automatisk konfiguration i PeakGuard."""
        if self._device_status_entity:
            state = self._hass.states.get(self._device_status_entity)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return str(state.state)
        return None

    async def get_solar_power(self) -> float | None:
        """Hämtar solproduktion i Watt (DC Input Power)."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        total_solar_power = 0.0
        found_solar = False

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain == "sensor" and entry.translation_key in [
                    "inverter_input_power",
                    "input_power",
                    "pv_power",
                ]:
                    state = self._hass.states.get(entry.entity_id)
                    if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        try:
                            val = float(state.state)
                            if state.attributes.get("unit_of_measurement") == "kW":
                                val *= 1000.0
                            total_solar_power += val
                            found_solar = True
                        except ValueError:
                            pass

        return total_solar_power if found_solar else None

    async def get_house_consumption(self) -> float | None:
        """Försöker hitta Huaweis inbyggda husförbrukningssensor automatiskt tvärs över anläggningen."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain == "sensor":
                    # EMMA-enheten rapporterar huslast i Watt
                    if entry.translation_key == "load_power":
                        state = self._hass.states.get(entry.entity_id)
                        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                            try:
                                return float(state.state)
                            except ValueError:
                                pass
                    # SDongle-enheten rapporterar huslast i kiloWatt (kW)
                    elif entry.translation_key == "sdongle_load_power":
                        state = self._hass.states.get(entry.entity_id)
                        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                            try:
                                return float(state.state) * 1000.0
                            except ValueError:
                                pass

        return None

    async def get_calculated_consumption(self) -> float | None:
        """Beräknar husförbrukning via formeln: Grid Import + Inverter Active Power."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        if self._grid_entity:
            grid_state = self._hass.states.get(self._grid_entity)
            if grid_state and grid_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    grid_val = float(grid_state.state)
                    if self._invert_grid:
                        grid_val = -grid_val

                    # Hitta Inverter Active Power (summera över alla växelriktare i anläggningen)
                    total_inv_val = 0.0
                    found_inv = False

                    for d_id in related_devices:
                        entries = er.async_entries_for_device(er_reg, d_id)
                        for entry in entries:
                            if entry.domain == "sensor" and entry.translation_key == "active_power":
                                inv_state = self._hass.states.get(entry.entity_id)
                                if inv_state and inv_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                                    try:
                                        total_inv_val += float(inv_state.state)
                                        found_inv = True
                                    except ValueError:
                                        pass

                    if found_inv:
                        return grid_val + total_inv_val
                except ValueError:
                    pass

        return None

    async def _get_max_discharge_entity(self) -> str | None:
        """Hittar number-entiteten för max urladdningseffekt via konfig eller enhetsregistret."""
        if getattr(self, "_max_discharge_entity", None):
            return self._max_discharge_entity

        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        valid_keys = [
            "storage_maximum_discharge_power",
            "storage_maximum_discharging_power",
            "battery_maximum_discharge_power",
            "battery_maximum_discharging_power",
            "maximum_discharging_power"
        ]

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain == "number" and entry.translation_key in valid_keys:
                    return entry.entity_id
        return None

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        action_upper = action.upper()

        try:
            discharge_entity = await self._get_max_discharge_entity()

            # --- ÅTERSTÄLL URLADDNINGSSPRÄRR ---
            # Om vi ska ladda, ladda ur, eller gå till IDLE, måste vi se till att
            # urladdningsspärren lyfts om den var satt till 0 av ett tidigare HOLD.
            if action_upper in ["CHARGE", "DISCHARGE", "IDLE"] and discharge_entity:
                state = self._hass.states.get(discharge_entity)
                current_discharge = -1.0
                if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    try:
                        current_discharge = float(state.state)
                    except ValueError:
                        pass

                if current_discharge == 0:
                    # 1. Fallback: Sensorns max-attribut
                    restore_val = 2500.0
                    if "max" in state.attributes:
                        try:
                            restore_val = float(state.attributes["max"])
                        except ValueError:
                            pass

                    # 2. Primärt: Hämta användarens valda gräns från molnet (Omstartssäker!)
                    domain_data = self._hass.data.get("battery_optimizer_light_plus", {})
                    for coord in domain_data.values():
                        if hasattr(coord, "data") and isinstance(coord.data, dict):
                            cloud_max = coord.data.get("max_discharge_kw")
                            if cloud_max:
                                restore_val = float(cloud_max) * 1000.0
                                break

                    await self._hass.services.async_call(
                        "number", "set_value",
                        {"entity_id": discharge_entity, "value": restore_val},
                        blocking=True
                    )

            if action_upper == "CHARGE":
                await self._hass.services.async_call(
                    "huawei_solar",
                    "forcible_charge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
                    blocking=True,
                )
            elif action_upper == "DISCHARGE":
                await self._hass.services.async_call(
                    "huawei_solar",
                    "forcible_discharge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
                    blocking=True,
                )
            elif action_upper == "HOLD":
                if discharge_entity:
                    state = self._hass.states.get(discharge_entity)
                    current_discharge = 1.0  # Anta att den kan ladda ur om vi inte vet säkert
                    if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        try:
                            current_discharge = float(state.state)
                        except ValueError:
                            pass

                    # Slitageskydd för EEPROM: Skriv bara om vi vet att värdet är > 0,
                    # eller om sensorn är otillgänglig och vi vill garantera spärren.
                    if current_discharge > 0:
                        await self._hass.services.async_call(
                            "number", "set_value",
                            {"entity_id": discharge_entity, "value": 0},
                            blocking=True
                        )

                # Stoppa eventuella pågående forcible_charge / discharge
                await self._hass.services.async_call(
                    "huawei_solar", "stop_forcible_charge", {"device_id": self._device_id}, blocking=True
                )
            elif action_upper == "IDLE":
                await self._hass.services.async_call(
                    "huawei_solar", "stop_forcible_charge", {"device_id": self._device_id}, blocking=True
                )
            else:
                _LOGGER.warning(f"Unknown action for Huawei: {action}")
        except ServiceNotFound as e:
            _LOGGER.warning(
                "Huawei service not found: %s. The 'huawei_solar' integration might be starting up. "
                "Please check your setup.", e
            )
        except Exception as e:
            _LOGGER.error("An unexpected error occurred while applying Huawei action '%s': %s",
            action,
            e,
            exc_info=True,
            )

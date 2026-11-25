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

import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.exceptions import ServiceNotFound
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)


def _safe_lower(val) -> str:
    """Returnerar lowercase-sträng om val är en str, annars tom sträng."""
    return val.lower() if isinstance(val, str) else ""


def _safe_attrs(state) -> dict:
    """Returnerar state.attributes som dict (säkert även för mocks i tester)."""
    attrs = getattr(state, "attributes", None)
    return attrs if isinstance(attrs, dict) else {}

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

    async def _get_charge_from_grid_entity(self) -> str | None:
        """Hittar switch-entiteten för 'Charge from Grid' / 'Ladda från växelström' (reg 47087)."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        valid_keys = (
            "storage_charge_from_grid_function",
            "charge_from_grid",
            "charge_from_ac",
        )

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain != "switch":
                    continue
                uid = _safe_lower(getattr(entry, "unique_id", None))
                ent_id = _safe_lower(getattr(entry, "entity_id", None))
                if (
                    entry.translation_key in valid_keys
                    or "storage_charge_from_grid_function" in uid
                    or ent_id.endswith(("_charge_from_grid", "_charge_from_ac"))
                ):
                    return entry.entity_id
        return None

    async def _get_grid_charge_cutoff_soc_entity(self) -> str | None:
        """Hittar number-entiteten för 'Grid charge cutoff SoC' (reg 47088)."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        valid_keys = (
            "storage_grid_charge_cutoff_state_of_charge",
            "grid_charge_cutoff_soc",
            "grid_charge_cutoff_state_of_charge",
        )

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain != "number":
                    continue
                uid = _safe_lower(getattr(entry, "unique_id", None))
                ent_id = _safe_lower(getattr(entry, "entity_id", None))
                if (
                    entry.translation_key in valid_keys
                    or "grid_charge_cutoff" in uid
                    or "grid_charge_cutoff" in ent_id
                ):
                    return entry.entity_id
        return None

    async def _get_grid_charge_max_power_entity(self) -> str | None:
        """Hittar number-entiteten för 'Grid charge maximum power' (reg 47084 / 47242)."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        valid_keys = (
            "storage_power_of_charge_from_grid",
            "storage_maximum_power_of_charge_from_grid",
            "storage_maximum_charge_from_grid_power",
            "grid_charge_maximum_power",
            "maximum_power_of_charge_from_grid",
            "power_of_charge_from_grid",
        )
        patterns = (
            "power_of_charge_from_grid",
            "charge_from_grid_power",
            "grid_charge_maximum_power",
        )

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain != "number":
                    continue
                uid = _safe_lower(getattr(entry, "unique_id", None))
                ent_id = _safe_lower(getattr(entry, "entity_id", None))
                if (
                    entry.translation_key in valid_keys
                    or any(p in uid for p in patterns)
                    or any(p in ent_id for p in patterns)
                ):
                    return entry.entity_id
        return None

    async def _get_max_charge_entity(self) -> str | None:
        """Hittar number-entiteten för max laddningseffekt (STORAGE_MAXIMUM_CHARGE_POWER)."""
        from homeassistant.helpers import entity_registry as er
        er_reg = er.async_get(self._hass)
        related_devices = self._get_related_devices()

        valid_keys = (
            "storage_maximum_charging_power",
            "storage_maximum_charge_power",
            "battery_maximum_charging_power",
            "battery_maximum_charge_power",
            "maximum_charging_power",
        )

        for d_id in related_devices:
            entries = er.async_entries_for_device(er_reg, d_id)
            for entry in entries:
                if entry.domain != "number":
                    continue
                uid = _safe_lower(getattr(entry, "unique_id", None))
                if entry.translation_key in valid_keys or "maximum_charging_power" in uid:
                    return entry.entity_id
        return None

    async def _async_call_with_retry(
        self, domain: str, service: str, service_data: dict, retries: int = 1
    ) -> None:
        """Anropar en HA-tjänst med 1 återförsök vid tillfälligt Modbus-anslutningsfel."""
        for attempt in range(retries + 1):
            try:
                await self._hass.services.async_call(
                    domain, service, service_data, blocking=True
                )
                return
            except ServiceNotFound:
                raise
            except Exception as err:
                err_text = str(err).lower()
                is_transient = any(
                    kw in err_text
                    for kw in ("connection", "modbus", "timeout", "disconnect")
                )
                if is_transient and attempt < retries:
                    _LOGGER.warning(
                        "Tillfälligt Huawei Modbus-fel vid %s.%s (%s) – väntar 2 s och försöker igen.",
                        domain,
                        service,
                        err,
                    )
                    await asyncio.sleep(2.0)
                    continue
                raise

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt."""
        power_w = int(target_kw * 1000)
        action_upper = action.upper()

        try:
            discharge_entity = await self._get_max_discharge_entity()
            wrote_register = False

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
                    attrs = _safe_attrs(state)
                    if "max" in attrs:
                        try:
                            restore_val = float(attrs["max"])
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

                    await self._async_call_with_retry(
                        "number",
                        "set_value",
                        {"entity_id": discharge_entity, "value": restore_val},
                    )
                    wrote_register = True

            if action_upper == "CHARGE":
                # 1. Säkerställ att 'Charge from Grid' (reg 47087) är påslagen
                charge_from_grid_entity = await self._get_charge_from_grid_entity()
                if charge_from_grid_entity:
                    cfg_state = self._hass.states.get(charge_from_grid_entity)
                    if cfg_state and cfg_state.state == "off":
                        if wrote_register:
                            await asyncio.sleep(1.0)
                        _LOGGER.info(
                            "Huawei 'Charge from Grid' (%s) är avstängd – slår på den inför tvingad nätladdning.",
                            charge_from_grid_entity,
                        )
                        await self._async_call_with_retry(
                            "switch",
                            "turn_on",
                            {"entity_id": charge_from_grid_entity},
                        )
                        wrote_register = True
                    elif cfg_state is None or cfg_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        _LOGGER.debug(
                            "Huawei 'Charge from Grid' (%s) har status '%s' – kan inte verifiera AC-laddning.",
                            charge_from_grid_entity,
                            cfg_state.state if cfg_state else None,
                        )
                else:
                    _LOGGER.debug(
                        "Hittade ingen 'Charge from Grid'-switch för Huawei-enhet %s "
                        "(kontrollera Elevate permissions / att entiteten är aktiverad).",
                        self._device_id,
                    )

                # 2. Säkerställ att 'Grid charge cutoff SoC' (reg 47088) inte blockerar AC-laddning
                cutoff_entity = await self._get_grid_charge_cutoff_soc_entity()
                if cutoff_entity:
                    cutoff_state = self._hass.states.get(cutoff_entity)
                    if cutoff_state and cutoff_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        try:
                            current_cutoff = float(cutoff_state.state)
                            attrs = _safe_attrs(cutoff_state)
                            target_cutoff = float(attrs.get("max", 100.0))
                            if current_cutoff < target_cutoff:
                                if wrote_register:
                                    await asyncio.sleep(1.0)
                                _LOGGER.info(
                                    "Huawei 'Grid charge cutoff SoC' (%s) är %.0f%% – "
                                    "höjer till %.0f%% inför nätladdning.",
                                    cutoff_entity,
                                    current_cutoff,
                                    target_cutoff,
                                )
                                await self._async_call_with_retry(
                                    "number",
                                    "set_value",
                                    {"entity_id": cutoff_entity, "value": target_cutoff},
                                )
                                wrote_register = True
                        except (ValueError, TypeError):
                            pass

                # 3. Säkerställ att 'Grid charge maximum power' (reg 47084/47242) inte stryper AC-laddning
                grid_max_entity = await self._get_grid_charge_max_power_entity()
                if grid_max_entity and power_w > 0:
                    gmax_state = self._hass.states.get(grid_max_entity)
                    if gmax_state and gmax_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        try:
                            current_gmax = float(gmax_state.state)
                            attrs = _safe_attrs(gmax_state)
                            is_kw = attrs.get("unit_of_measurement") == "kW"
                            desired_gmax = (power_w / 1000.0) if is_kw else float(power_w)
                            if "max" in attrs:
                                desired_gmax = min(desired_gmax, float(attrs["max"]))
                            if "min" in attrs:
                                desired_gmax = max(desired_gmax, float(attrs["min"]))
                            if current_gmax < desired_gmax:
                                if wrote_register:
                                    await asyncio.sleep(1.0)
                                _LOGGER.info(
                                    "Huawei 'Grid charge maximum power' (%s) är %s – höjer till %s inför nätladdning.",
                                    grid_max_entity,
                                    current_gmax,
                                    desired_gmax,
                                )
                                await self._async_call_with_retry(
                                    "number",
                                    "set_value",
                                    {"entity_id": grid_max_entity, "value": desired_gmax},
                                )
                                wrote_register = True
                        except (ValueError, TypeError):
                            pass

                # 4. Begränsa power_w mot batteriets max laddningseffekt så forcible_charge inte kastar ValueError
                max_charge_entity = await self._get_max_charge_entity()
                if max_charge_entity and power_w > 0:
                    mc_state = self._hass.states.get(max_charge_entity)
                    if mc_state and mc_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                        try:
                            max_charge_w = float(mc_state.state)
                            attrs = _safe_attrs(mc_state)
                            if attrs.get("unit_of_measurement") == "kW":
                                max_charge_w *= 1000.0
                            if max_charge_w > 0 and power_w > max_charge_w:
                                _LOGGER.info(
                                    "Huawei max laddningseffekt (%s) är %.0f W – begränsar forcible_charge från %d W.",
                                    max_charge_entity,
                                    max_charge_w,
                                    power_w,
                                )
                                power_w = int(max_charge_w)
                        except (ValueError, TypeError):
                            pass

                # Ge växelriktaren/SDongle en kort paus innan forcible_charge om vi skrivit register nyss
                if wrote_register:
                    await asyncio.sleep(1.0)

                await self._async_call_with_retry(
                    "huawei_solar",
                    "forcible_charge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
                )
            elif action_upper == "DISCHARGE":
                if wrote_register:
                    await asyncio.sleep(1.0)
                await self._async_call_with_retry(
                    "huawei_solar",
                    "forcible_discharge",
                    {"device_id": self._device_id, "power": power_w, "duration": 60},
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
                        await self._async_call_with_retry(
                            "number",
                            "set_value",
                            {"entity_id": discharge_entity, "value": 0},
                        )
                        wrote_register = True

                if wrote_register:
                    await asyncio.sleep(1.0)

                # Stoppa eventuella pågående forcible_charge / discharge
                await self._async_call_with_retry(
                    "huawei_solar",
                    "stop_forcible_charge",
                    {"device_id": self._device_id},
                )
            elif action_upper == "IDLE":
                if wrote_register:
                    await asyncio.sleep(1.0)
                await self._async_call_with_retry(
                    "huawei_solar",
                    "stop_forcible_charge",
                    {"device_id": self._device_id},
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

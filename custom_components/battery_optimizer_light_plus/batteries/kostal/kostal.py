# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import logging
import struct
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE  # type: ignore
from ..base import BatteryApi

_LOGGER = logging.getLogger(__name__)

# Modbus-register för extern batteristyrning (Float32, 2 register, Big-Endian)
KOSTAL_BATTERY_POWER_REGISTER = 1034


class KostalBattery(BatteryApi):
    """Batteriadapter för Kostal Plenticore via Modbus TCP.

    Läser sensordata från den officiella kostal_plenticore-integrationen (REST-API).
    Styr batteriet via direkt Modbus TCP till register 1034 (Float32).

    Teckenkonvention för register 1034:
      - Negativt värde = Ladda batteriet (CHARGE)
      - Positivt värde = Ladda ur batteriet (DISCHARGE)
      - Noll           = Stoppa laddning/urladdning (HOLD)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int = 1502,
        slave_id: int = 71,
        soc_entity: str | None = None,
        grid_entity: str | None = None,
        battery_power_entity: str | None = None,
        load_entity: str | None = None,
        solar_entity: str | None = None,
        status_entity: str | None = None,
    ):
        """Initiera KostalBattery.

        Args:
            hass: Home Assistant-instans.
            host: IP-adress till Kostal Plenticore-växelriktaren.
            port: Modbus TCP-port (standard 1502).
            slave_id: Modbus slav-ID (standard 71).
            soc_entity: Entity ID för batteriets SoC-sensor.
            grid_entity: Entity ID för näteffekt-sensor (Grid_P).
            battery_power_entity: Entity ID för batterieffekt-sensor.
            load_entity: Entity ID för husförbruknings-sensor (Home_P).
            solar_entity: Entity ID för solproduktions-sensor (Dc_P).
            status_entity: Entity ID för växelriktarens status-sensor.
        """
        self._hass = hass
        self._host = host
        self._port = port
        self._slave_id = slave_id
        self._soc_entity = soc_entity
        self._grid_entity = grid_entity
        self._battery_power_entity = battery_power_entity
        self._load_entity = load_entity
        self._solar_entity = solar_entity
        self._status_entity = status_entity

    def _read_sensor(self, entity_id: str | None) -> float | None:
        """Läser ett numeriskt värde från en HA-sensor."""
        if not entity_id:
            return None
        state = self._hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                val = float(state.state)
                unit = state.attributes.get("unit_of_measurement")
                if unit and unit.lower() in ["kw", "kilowatt"]:
                    val *= 1000.0
                return val
            except (ValueError, TypeError):
                pass
        return None

    async def get_current_soc(self) -> float | None:
        """Hämtar batteriets aktuella laddningsgrad (SoC) i procent."""
        return self._read_sensor(self._soc_entity)

    async def get_house_consumption(self) -> float | None:
        """Returnerar husets rena förbrukning i Watt från Kostals Home_P-sensor."""
        return self._read_sensor(self._load_entity)

    async def get_solar_power(self) -> float | None:
        """Hämtar solproduktion i Watt från Kostals Dc_P-sensor."""
        return self._read_sensor(self._solar_entity)

    async def get_status_text(self) -> str | None:
        """Hämtar växelriktarens driftstatus för underhållsläge."""
        if self._status_entity:
            state_obj = self._hass.states.get(self._status_entity)
            if state_obj and state_obj.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return str(state_obj.state)
        return None

    @staticmethod
    def _float_to_registers(value: float) -> list[int]:
        """Konverterar ett flyttal till två 16-bitars Modbus-register (Big-Endian).

        Kostal Plenticore förväntar Float32 (IEEE 754) i Big-Endian-ordning
        uppdelat på två konsekutiva 16-bitars register.
        """
        packed = struct.pack(">f", value)
        reg_high = struct.unpack(">H", packed[0:2])[0]
        reg_low = struct.unpack(">H", packed[2:4])[0]
        return [reg_high, reg_low]

    async def _write_modbus_register(self, value_watts: float) -> bool:
        """Skriver ett Float32-värde till Modbus-register 1034 på växelriktaren.

        Använder pymodbus AsyncModbusTcpClient för asynkron TCP-kommunikation.
        Returnerar True vid lyckad skrivning, False vid fel.
        """
        try:
            from pymodbus.client import AsyncModbusTcpClient  # type: ignore
        except ImportError:
            _LOGGER.error(
                "pymodbus är inte installerat. Kan inte styra Kostal Plenticore. "
                "Installera med: pip install pymodbus"
            )
            return False

        registers = self._float_to_registers(value_watts)

        try:
            client = AsyncModbusTcpClient(
                host=self._host,
                port=self._port,
            )
            await client.connect()

            if not client.connected:
                _LOGGER.error(
                    "Kunde inte ansluta till Kostal Plenticore Modbus TCP "
                    "på %s:%s", self._host, self._port
                )
                return False

            try:
                result = await client.write_registers(
                    address=KOSTAL_BATTERY_POWER_REGISTER,
                    values=registers,
                    slave=self._slave_id,
                )

                if result.isError():
                    _LOGGER.error(
                        "Modbus-skrivning misslyckades för register %s: %s",
                        KOSTAL_BATTERY_POWER_REGISTER, result
                    )
                    return False

                _LOGGER.debug(
                    "Kostal Modbus: Skrev %.1f W till register %s (regs=%s)",
                    value_watts, KOSTAL_BATTERY_POWER_REGISTER, registers
                )
                return True
            finally:
                client.close()

        except Exception:
            _LOGGER.exception(
                "Oväntat fel vid Modbus-kommunikation med Kostal Plenticore "
                "på %s:%s", self._host, self._port
            )
            return False

    async def apply_action(self, action: str, target_kw: float = 0.0):
        """Verkställer ett beslut från molnet eller lokalt via Modbus TCP.

        Args:
            action: 'CHARGE', 'DISCHARGE', 'HOLD', eller 'IDLE'.
            target_kw: Måleffekt i kW (t.ex. 3.5 för 3500 W).

        Teckenkonvention för register 1034:
            CHARGE    -> Negativt värde (t.ex. -3500.0 W)
            DISCHARGE -> Positivt värde (t.ex. +3500.0 W)
            HOLD      -> 0.0 W (fryser batteristatus)
            IDLE      -> 0.0 W (växelriktarens watchdog återställer till auto)
        """
        power_w = abs(target_kw * 1000.0)

        if action == "CHARGE":
            modbus_value = -power_w
        elif action == "DISCHARGE":
            modbus_value = power_w
        elif action in ("HOLD", "IDLE"):
            modbus_value = 0.0
        else:
            _LOGGER.warning("Kostal: Okänd action '%s', ignorerar", action)
            return

        _LOGGER.debug(
            "Kostal apply_action: %s med target %.1f kW -> "
            "skriver %.1f W till Modbus register %s",
            action, target_kw, modbus_value, KOSTAL_BATTERY_POWER_REGISTER
        )

        await self._write_modbus_register(modbus_value)

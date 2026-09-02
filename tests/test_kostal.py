# Battery Optimizer Light
# Copyright (C) 2026 @awestin67
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import pytest
import struct
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from custom_components.battery_optimizer_light_plus.battery_factory import create_battery_api
from custom_components.battery_optimizer_light_plus.const import (
    CONF_BATTERY_TYPE,
    BATTERY_TYPE_KOSTAL,
    CONF_HOST,
    CONF_PORT,
    CONF_SOC_SENSOR,
    CONF_GRID_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_VIRTUAL_LOAD_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_DEVICE_STATUS_ENTITY,
)
from custom_components.battery_optimizer_light_plus.batteries.kostal.kostal import (
    KostalBattery,
    KOSTAL_BATTERY_POWER_REGISTER,
)


def test_create_kostal_battery_from_factory(mock_hass):
    """Testar att KostalBattery skapas korrekt via battery_factory."""
    config = {
        CONF_BATTERY_TYPE: BATTERY_TYPE_KOSTAL,
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 1502,
        CONF_SOC_SENSOR: "sensor.plenticore_battery_soc",
        CONF_GRID_SENSOR: "sensor.plenticore_grid_power",
        CONF_BATTERY_POWER_SENSOR: "sensor.plenticore_battery_power",
        CONF_VIRTUAL_LOAD_SENSOR: "sensor.plenticore_home_power",
        CONF_SOLAR_SENSOR: "sensor.plenticore_solar_power",
        CONF_DEVICE_STATUS_ENTITY: "sensor.plenticore_inverter_state",
    }

    battery = create_battery_api(mock_hass, config)
    assert isinstance(battery, KostalBattery)
    assert battery._host == "192.168.1.100"
    assert battery._port == 1502
    assert battery._slave_id == 71
    assert battery._soc_entity == "sensor.plenticore_battery_soc"
    assert battery._load_entity == "sensor.plenticore_home_power"
    assert battery._solar_entity == "sensor.plenticore_solar_power"



@pytest.fixture
def mock_hass():
    """Skapar en fejkad Home Assistant-instans."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states.get = MagicMock()
    return hass


@pytest.fixture
def kostal_battery(mock_hass):
    """Skapar en instans av KostalBattery för testerna."""
    return KostalBattery(
        hass=mock_hass,
        host="192.168.1.100",
        port=1502,
        slave_id=71,
        soc_entity="sensor.plenticore_battery_soc",
        grid_entity="sensor.plenticore_grid_power",
        battery_power_entity="sensor.plenticore_battery_power",
        load_entity="sensor.plenticore_home_power",
        solar_entity="sensor.plenticore_solar_power",
        status_entity="sensor.plenticore_inverter_state",
    )


# === SoC ===

@pytest.mark.asyncio
async def test_get_current_soc(kostal_battery, mock_hass):
    """Krav: SoC ska hämtas korrekt från Home Assistant state maskinen."""
    mock_state = MagicMock()
    mock_state.state = "75.0"
    mock_state.attributes = {"unit_of_measurement": "%"}
    mock_hass.states.get.return_value = mock_state

    soc = await kostal_battery.get_current_soc()
    assert soc == 75.0
    mock_hass.states.get.assert_called_once_with("sensor.plenticore_battery_soc")


@pytest.mark.asyncio
async def test_get_current_soc_unavailable(kostal_battery, mock_hass):
    """Krav: Om SoC-sensorn är otillgänglig ska None returneras."""
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state

    soc = await kostal_battery.get_current_soc()
    assert soc is None


@pytest.mark.asyncio
async def test_get_current_soc_no_entity(mock_hass):
    """Krav: Om ingen SoC-entitet konfigurerats ska None returneras."""
    battery = KostalBattery(hass=mock_hass, host="192.168.1.100")
    soc = await battery.get_current_soc()
    assert soc is None


# === Husförbrukning ===

@pytest.mark.asyncio
async def test_get_house_consumption(kostal_battery, mock_hass):
    """Krav: Husförbrukning ska hämtas från Home_P-sensorn."""
    mock_state = MagicMock()
    mock_state.state = "2500.0"
    mock_state.attributes = {"unit_of_measurement": "W"}
    mock_hass.states.get.return_value = mock_state

    consumption = await kostal_battery.get_house_consumption()
    assert consumption == 2500.0


@pytest.mark.asyncio
async def test_get_house_consumption_kw_unit(kostal_battery, mock_hass):
    """Krav: Om enheten är kW ska värdet konverteras till W."""
    mock_state = MagicMock()
    mock_state.state = "2.5"
    mock_state.attributes = {"unit_of_measurement": "kW"}
    mock_hass.states.get.return_value = mock_state

    consumption = await kostal_battery.get_house_consumption()
    assert consumption == 2500.0


# === Solproduktion ===

@pytest.mark.asyncio
async def test_get_solar_power(kostal_battery, mock_hass):
    """Krav: Solproduktion ska hämtas från Dc_P-sensorn."""
    mock_state = MagicMock()
    mock_state.state = "4200.0"
    mock_state.attributes = {"unit_of_measurement": "W"}
    mock_hass.states.get.return_value = mock_state

    solar = await kostal_battery.get_solar_power()
    assert solar == 4200.0


# === Driftstatus (get_status_text) ===

@pytest.mark.asyncio
async def test_get_status_text(kostal_battery, mock_hass):
    """Krav: get_status_text ska hämta rätt värde om status_entity är satt."""
    mock_state = MagicMock()
    mock_state.state = "FeedIn"
    mock_hass.states.get.return_value = mock_state

    status = await kostal_battery.get_status_text()
    assert status == "FeedIn"
    mock_hass.states.get.assert_called_once_with("sensor.plenticore_inverter_state")


@pytest.mark.asyncio
async def test_get_status_text_unavailable(kostal_battery, mock_hass):
    """Krav: get_status_text ska returnera None om sensorn är unavailable eller unknown."""
    mock_state = MagicMock()
    mock_state.state = STATE_UNAVAILABLE
    mock_hass.states.get.return_value = mock_state

    assert await kostal_battery.get_status_text() is None

    mock_state.state = STATE_UNKNOWN
    assert await kostal_battery.get_status_text() is None


@pytest.mark.asyncio
async def test_get_status_text_no_entity(mock_hass):
    """Krav: get_status_text ska returnera None om ingen status_entity är konfigurerad."""
    battery = KostalBattery(hass=mock_hass, host="192.168.1.100")
    assert await battery.get_status_text() is None


# === Float32-konvertering ===

def test_float_to_registers_positive():
    """Krav: Positivt Float32-tal ska packas korrekt i Big-Endian."""
    regs = KostalBattery._float_to_registers(3500.0)
    # Verifiera genom att packa tillbaka till float
    packed = struct.pack(">HH", regs[0], regs[1])
    result = struct.unpack(">f", packed)[0]
    assert abs(result - 3500.0) < 0.1


def test_float_to_registers_negative():
    """Krav: Negativt Float32-tal (laddning) ska packas korrekt."""
    regs = KostalBattery._float_to_registers(-3500.0)
    packed = struct.pack(">HH", regs[0], regs[1])
    result = struct.unpack(">f", packed)[0]
    assert abs(result - (-3500.0)) < 0.1


def test_float_to_registers_zero():
    """Krav: Noll ska packas korrekt (HOLD/IDLE)."""
    regs = KostalBattery._float_to_registers(0.0)
    packed = struct.pack(">HH", regs[0], regs[1])
    result = struct.unpack(">f", packed)[0]
    assert result == 0.0


# === apply_action (Modbus-skrivning) ===

@pytest.mark.asyncio
async def test_apply_action_charge(kostal_battery):
    """Krav: CHARGE 3.0 kW ska skriva -3000.0 W till Modbus-register 1034."""
    with patch.object(kostal_battery, "_write_modbus_register", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = True
        await kostal_battery.apply_action("CHARGE", 3.0)
        mock_write.assert_called_once_with(-3000.0)


@pytest.mark.asyncio
async def test_apply_action_discharge(kostal_battery):
    """Krav: DISCHARGE 2.5 kW ska skriva +2500.0 W till Modbus-register 1034."""
    with patch.object(kostal_battery, "_write_modbus_register", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = True
        await kostal_battery.apply_action("DISCHARGE", 2.5)
        mock_write.assert_called_once_with(2500.0)


@pytest.mark.asyncio
async def test_apply_action_hold(kostal_battery):
    """Krav: HOLD ska skriva 0.0 W till Modbus-register 1034."""
    with patch.object(kostal_battery, "_write_modbus_register", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = True
        await kostal_battery.apply_action("HOLD", 0.0)
        mock_write.assert_called_once_with(0.0)


@pytest.mark.asyncio
async def test_apply_action_idle(kostal_battery):
    """Krav: IDLE ska skriva 0.0 W till Modbus-register 1034."""
    with patch.object(kostal_battery, "_write_modbus_register", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = True
        await kostal_battery.apply_action("IDLE", 0.0)
        mock_write.assert_called_once_with(0.0)


@pytest.mark.asyncio
async def test_apply_action_unknown(kostal_battery):
    """Krav: Okänd action ska ignoreras utan Modbus-skrivning."""
    with patch.object(kostal_battery, "_write_modbus_register", new_callable=AsyncMock) as mock_write:
        await kostal_battery.apply_action("UNKNOWN_ACTION", 1.0)
        mock_write.assert_not_called()


# === Modbus TCP-anslutning ===

@pytest.mark.asyncio
async def test_write_modbus_register_success(kostal_battery):
    """Krav: Lyckad Modbus-skrivning ska returnera True."""
    mock_client = AsyncMock()
    mock_client.close = MagicMock()
    mock_client.connected = True
    mock_result = MagicMock()
    mock_result.isError.return_value = False
    mock_client.write_registers.return_value = mock_result

    with patch(
        "pymodbus.client.AsyncModbusTcpClient",
        return_value=mock_client,
    ):
        result = await kostal_battery._write_modbus_register(3500.0)
        assert result is True
        mock_client.connect.assert_awaited_once()
        mock_client.write_registers.assert_awaited_once()
        call_kwargs = mock_client.write_registers.call_args
        assert call_kwargs.kwargs["address"] == KOSTAL_BATTERY_POWER_REGISTER
        assert call_kwargs.kwargs["slave"] == 71
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_write_modbus_register_connection_failure(kostal_battery):
    """Krav: Om Modbus-anslutningen misslyckas ska False returneras."""
    mock_client = AsyncMock()
    mock_client.connected = False

    with patch(
        "pymodbus.client.AsyncModbusTcpClient",
        return_value=mock_client,
    ):
        result = await kostal_battery._write_modbus_register(3500.0)
        assert result is False


@pytest.mark.asyncio
async def test_write_modbus_register_write_error(kostal_battery):
    """Krav: Om Modbus-skrivningen returnerar fel ska False returneras."""
    mock_client = AsyncMock()
    mock_client.close = MagicMock()
    mock_client.connected = True
    mock_result = MagicMock()
    mock_result.isError.return_value = True
    mock_client.write_registers.return_value = mock_result

    with patch(
        "pymodbus.client.AsyncModbusTcpClient",
        return_value=mock_client,
    ):
        result = await kostal_battery._write_modbus_register(3500.0)
        assert result is False
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_write_modbus_register_exception(kostal_battery):
    """Krav: Om ett undantag kastas ska False returneras."""
    mock_client = AsyncMock()
    mock_client.connect.side_effect = ConnectionRefusedError("Connection refused")

    with patch(
        "pymodbus.client.AsyncModbusTcpClient",
        return_value=mock_client,
    ):
        result = await kostal_battery._write_modbus_register(3500.0)
        assert result is False


# === Convenience-metoder (ärvda från BatteryApi) ===

@pytest.mark.asyncio
async def test_force_charge_convenience(kostal_battery):
    """Krav: force_charge(3000) ska anropa apply_action('CHARGE', 3.0)."""
    with patch.object(kostal_battery, "apply_action", new_callable=AsyncMock) as mock_action:
        await kostal_battery.force_charge(3000)
        mock_action.assert_called_once_with("CHARGE", 3.0)


@pytest.mark.asyncio
async def test_force_discharge_convenience(kostal_battery):
    """Krav: force_discharge(2500) ska anropa apply_action('DISCHARGE', 2.5)."""
    with patch.object(kostal_battery, "apply_action", new_callable=AsyncMock) as mock_action:
        await kostal_battery.force_discharge(2500)
        mock_action.assert_called_once_with("DISCHARGE", 2.5)


@pytest.mark.asyncio
async def test_set_auto_mode_convenience(kostal_battery):
    """Krav: set_auto_mode() ska anropa apply_action('IDLE', 0.0)."""
    with patch.object(kostal_battery, "apply_action", new_callable=AsyncMock) as mock_action:
        await kostal_battery.set_auto_mode()
        mock_action.assert_called_once_with("IDLE", 0.0)

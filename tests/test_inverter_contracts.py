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

"""Kontraktstester mot externa växelriktar-integrationer.

Validerar att källkoden i lokalt klonade repon i code_projects/
fortfarande tillhandahåller de tjänster, fält och sensornycklar
som Battery Optimizer Light förväntar sig.
"""

from pathlib import Path
import pytest

CODE_PROJECTS_DIR = Path(__file__).resolve().parent.parent.parent


def _parse_yaml_services(file_path: Path) -> dict:
    """Läser in services.yaml via PyYAML om tillgängligt, annars en inbyggd parser."""
    try:
        import yaml  # type: ignore
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
    except ImportError:
        pass

    services = {}
    current_service = None
    in_fields = False
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            raw_line = line.rstrip()
            if not raw_line or raw_line.strip().startswith("#"):
                continue

            if not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                current_service = line.split(":")[0].strip()
                services[current_service] = {"fields": {}}
                in_fields = False
            elif current_service:
                stripped = line.strip()
                if stripped.startswith("fields:"):
                    in_fields = True
                elif in_fields:
                    indent = len(line) - len(line.lstrip(" "))
                    if indent == 4 and ":" in stripped:
                        field_name = stripped.split(":")[0].strip()
                        services[current_service]["fields"][field_name] = {}
                    elif indent < 4 and not stripped.startswith("fields:"):
                        in_fields = False

    return services


def _read_component_texts(target_dir: Path) -> str:
    """Läser all kod (py, json, yaml) inom en katalog till en gemensam lowercase-sträng."""
    all_text = []
    for ext in ("*.py", "*.json", "*.yaml"):
        for f in target_dir.rglob(ext):
            try:
                all_text.append(f.read_text(encoding="utf-8", errors="ignore").lower())
            except Exception:
                pass
    return "\n".join(all_text)


class TestInverterContracts:
    """Verifierar kontrakt mot klonade växelriktar-repon."""

    def test_huawei_solar_contract(self):
        """Validerar att huawei_solar tillhandahåller förväntade tjänster och sensornycklar."""
        repo_dir = CODE_PROJECTS_DIR / "huawei_solar"
        if not repo_dir.exists():
            pytest.skip("huawei_solar är inte klonat i code_projects/")

        svc_file = repo_dir / "services.yaml"
        assert svc_file.exists(), "huawei_solar saknar services.yaml!"

        services = _parse_yaml_services(svc_file)

        # Tjänster vi anropar
        assert "forcible_charge" in services, "Tjänsten 'forcible_charge' saknas i huawei_solar!"
        assert "forcible_discharge" in services, "Tjänsten 'forcible_discharge' saknas i huawei_solar!"
        assert "stop_forcible_charge" in services, "Tjänsten 'stop_forcible_charge' saknas i huawei_solar!"

        # Parametrar
        charge_fields = services["forcible_charge"].get("fields", {})
        assert "power" in charge_fields, "Fältet 'power' saknas i huawei_solar forcible_charge!"
        assert "duration" in charge_fields, "Fältet 'duration' saknas i huawei_solar forcible_charge!"

        discharge_fields = services["forcible_discharge"].get("fields", {})
        assert "power" in discharge_fields, "Fältet 'power' saknas i huawei_solar forcible_discharge!"
        assert "duration" in discharge_fields, "Fältet 'duration' saknas i huawei_solar forcible_discharge!"

        # Sensornycklar (åtminstone en av dessa måste finnas för solproduktionsdetektering)
        code_text = _read_component_texts(repo_dir)
        has_solar_key = any(k in code_text for k in ["input_power", "inverter_input_power", "pv_power"])
        assert has_solar_key, "Ingen av de förväntade solproduktionsnycklarna hittades i huawei_solar!"

    def test_homevolt_contract(self):
        """Validerar att homeassistant-homevolt-local tillhandahåller schemaläggningstjänsten."""
        repo_dir = CODE_PROJECTS_DIR / "homeassistant-homevolt-local"
        if not repo_dir.exists():
            pytest.skip("homeassistant-homevolt-local är inte klonat i code_projects/")

        svc_candidates = list(repo_dir.rglob("services.yaml"))
        assert svc_candidates, "homevolt_local saknar services.yaml!"

        services = _parse_yaml_services(svc_candidates[0])

        assert "add_schedule" in services, "Tjänsten 'add_schedule' saknas i homevolt_local!"
        fields = services["add_schedule"].get("fields", {})
        for req in ["mode", "setpoint", "from_time", "to_time"]:
            assert req in fields, f"Fältet '{req}' saknas i homevolt_local add_schedule!"

    def test_solis_modbus_contract(self):
        """Validerar att solis_modbus har styr- och övervakningsnycklar."""
        repo_dir = CODE_PROJECTS_DIR / "solis_modbus"
        if not repo_dir.exists():
            pytest.skip("solis_modbus är inte klonat i code_projects/")

        code_text = _read_component_texts(repo_dir / "custom_components" / "solis_modbus")

        # Driftläge (select)
        assert any(k in code_text for k in ["rc_force_charge_discharge", "rc_mode", "remote_control_mode"]), (
            "solis_modbus saknar nyckel för fjärrstyrningsläge (rc_mode/rc_force_charge_discharge)!"
        )

        # Laddningseffekt (number)
        assert any(k in code_text for k in ["rc_force_charge_power", "rc_charge_power", "charge_power_limit"]), (
            "solis_modbus saknar nyckel för laddningseffekt (rc_force_charge_power)!"
        )

        # Urladdningseffekt (number)
        discharge_keys = ["rc_force_discharge_power", "rc_discharge_power", "discharge_power_limit"]
        assert any(k in code_text for k in discharge_keys), (
            "solis_modbus saknar nyckel för urladdningseffekt (rc_force_discharge_power)!"
        )

        # Urladdningsgräns (number)
        assert any(k in code_text for k in ["battery_discharge_limit_power", "discharge_limit_power"]), (
            "solis_modbus saknar nyckel för batteriurladdningsgräns!"
        )

    def test_sigenergy_contract(self):
        """Validerar att Sigenergy-Local-Modbus har styr- och begränsningsnycklar."""
        repo_dir = CODE_PROJECTS_DIR / "Sigenergy-Local-Modbus"
        if not repo_dir.exists():
            pytest.skip("Sigenergy-Local-Modbus är inte klonat i code_projects/")

        comp_dir = repo_dir / "custom_components" / "sigen"
        if not comp_dir.exists():
            comp_dir = repo_dir
        code_text = _read_component_texts(comp_dir)

        assert any(k in code_text for k in ["ems_control_mode", "control_mode"]), (
            "Sigenergy saknar nyckel för ems_control_mode!"
        )
        assert any(k in code_text for k in ["max_charging_limit", "max_charge_power", "charging_limit"]), (
            "Sigenergy saknar nyckel för max_charging_limit!"
        )
        assert any(k in code_text for k in ["max_discharging_limit", "max_discharge_power", "discharging_limit"]), (
            "Sigenergy saknar nyckel för max_discharging_limit!"
        )

    def test_solax_solinteg_contract(self):
        """Validerar att homeassistant-solax-modbus har styrnycklar för Solinteg."""
        repo_dir = CODE_PROJECTS_DIR / "homeassistant-solax-modbus"
        if not repo_dir.exists():
            pytest.skip("homeassistant-solax-modbus är inte klonat i code_projects/")

        code_text = _read_component_texts(repo_dir / "custom_components" / "solax_modbus")

        assert any(k in code_text for k in ["working_mode", "operation_mode", "mode"]), (
            "homeassistant-solax-modbus saknar working_mode för Solinteg!"
        )
        assert any(k in code_text for k in ["charge_discharge_power", "power_target", "charge_power"]), (
            "homeassistant-solax-modbus saknar charge_discharge_power för Solinteg!"
        )

    def test_kostal_contract(self):
        """Validerar att kostal_plenticore komponenten finns i klonat HA core repo."""
        repo_dir = CODE_PROJECTS_DIR / "kostal_plenticore_repo"
        if not repo_dir.exists():
            pytest.skip("kostal_plenticore_repo är inte klonat i code_projects/")

        comp_dir = repo_dir / "homeassistant" / "components" / "kostal_plenticore"
        assert comp_dir.exists(), "kostal_plenticore komponenten saknas i kostal_plenticore_repo!"

    def test_solarman_contract(self):
        """Validerar att solarman integrationen finns i klonat repo."""
        repo_dir = CODE_PROJECTS_DIR / "home_assistant_solarman"
        if not repo_dir.exists():
            pytest.skip("home_assistant_solarman är inte klonat i code_projects/")

        comp_dir = repo_dir / "custom_components" / "solarman"
        assert comp_dir.exists(), "solarman komponenten saknas i home_assistant_solarman!"

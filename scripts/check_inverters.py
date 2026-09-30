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

"""Script för att övervaka och validera kompatibilitet med externa växelriktar-integrationer.

Kontrollerar:
1. Lokala git-statusar och om nya commits/taggar finns på GitHub.
2. Automatiskt 'git pull' för alla klonade repon (--pull).
3. Kontraktstestning: säkerställer att förväntade services.yaml och translation keys
   fortfarande existerar i källkoden hos respektive integration.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
CODE_PROJECTS_DIR = BASE_DIR.parent


class InverterConfig(TypedDict):
    name: str
    dir: str
    repo: str
    adapter: str | None
    services_path: str | None
    expected_services: dict[str, list[str]]
    component_dir: str
    expected_key_groups: list[list[str]]


# Konfiguration över alla externa integrationer vi har beroenden till
INVERTERS: list[InverterConfig] = [
    {
        "name": "Huawei Solar",
        "dir": "huawei_solar",
        "repo": "wlcrs/huawei_solar",
        "adapter": "batteries/huawei/huawei.py",
        "services_path": "services.yaml",
        "expected_services": {
            "forcible_charge": ["power", "duration"],
            "forcible_discharge": ["power", "duration"],
            "stop_forcible_charge": [],
        },
        "component_dir": "",
        "expected_key_groups": [
            ["input_power", "inverter_input_power", "pv_power"],
        ],
    },
    {
        "name": "Homevolt Local",
        "dir": "homeassistant-homevolt-local",
        "repo": "JohNan/homeassistant-homevolt-local",
        "adapter": "batteries/homevolt/homevolt.py",
        "services_path": "custom_components/homevolt_local/services.yaml",
        "expected_services": {
            "add_schedule": ["mode", "setpoint", "from_time", "to_time"],
        },
        "component_dir": "custom_components/homevolt_local",
        "expected_key_groups": [],
    },
    {
        "name": "Solis Modbus",
        "dir": "solis_modbus",
        "repo": "Pho3niX90/solis_modbus",
        "adapter": "batteries/solis_modbus/solis_modbus.py",
        "services_path": None,
        "expected_services": {},
        "component_dir": "custom_components/solis_modbus",
        "expected_key_groups": [
            ["rc_force_charge_discharge", "rc_mode", "remote_control_mode"],
            ["rc_force_charge_power", "rc_charge_power", "charge_power_limit"],
            ["rc_force_discharge_power", "rc_discharge_power", "discharge_power_limit"],
            ["battery_discharge_limit_power", "discharge_limit_power"],
        ],
    },
    {
        "name": "Sigenergy Local Modbus",
        "dir": "Sigenergy-Local-Modbus",
        "repo": "TypQxQ/Sigenergy-Local-Modbus",
        "adapter": "batteries/sigenergy/sigenergy.py",
        "services_path": None,
        "expected_services": {},
        "component_dir": "custom_components/sigen",
        "expected_key_groups": [
            ["ems_control_mode", "control_mode"],
            ["max_charging_limit", "max_charge_power", "charging_limit"],
            ["max_discharging_limit", "max_discharge_power", "discharging_limit"],
        ],
    },
    {
        "name": "SolaX Modbus (Solinteg)",
        "dir": "homeassistant-solax-modbus",
        "repo": "wills106/homeassistant-solax-modbus",
        "adapter": "batteries/solinteg/solinteg.py",
        "services_path": None,
        "expected_services": {},
        "component_dir": "custom_components/solax_modbus",
        "expected_key_groups": [
            ["working_mode", "operation_mode", "mode"],
            ["charge_discharge_power", "power_target", "charge_power"],
        ],
    },
    {
        "name": "Kostal Plenticore",
        "dir": "kostal_plenticore_repo",
        "repo": "home-assistant/core",
        "adapter": "batteries/kostal/kostal.py",
        "services_path": None,
        "expected_services": {},
        "component_dir": "homeassistant/components/kostal_plenticore",
        "expected_key_groups": [],
    },
    {
        "name": "Solarman",
        "dir": "home_assistant_solarman",
        "repo": "StephanJoubert/home_assistant_solarman",
        "adapter": None,
        "services_path": None,
        "expected_services": {},
        "component_dir": "custom_components/solarman",
        "expected_key_groups": [],
    },
]


def run_git(cwd: Path, args: list[str]) -> str:
    """Kör ett git-kommando i given katalog."""
    try:
        res = subprocess.check_output(
            ["git", "-C", str(cwd)] + args,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        return res.decode("utf-8").strip()
    except Exception:
        return ""


def get_github_latest_release(repo_slug: str, token: str | None = None) -> dict | None:
    """Hämtar information om senaste release eller tagg från GitHub API."""
    try:
        import requests
    except ImportError:
        return None

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "tag": data.get("tag_name", "N/A"),
                "name": data.get("name", ""),
                "date": data.get("published_at", "")[:10],
                "url": data.get("html_url", f"https://github.com/{repo_slug}/releases"),
            }
        elif resp.status_code == 404:
            tags_url = f"https://api.github.com/repos/{repo_slug}/tags?per_page=1"
            t_resp = requests.get(tags_url, headers=headers, timeout=6)
            if t_resp.status_code == 200 and t_resp.json():
                latest_tag = t_resp.json()[0].get("name", "N/A")
                return {
                    "tag": latest_tag,
                    "name": latest_tag,
                    "date": "Senaste tagg",
                    "url": f"https://github.com/{repo_slug}/releases",
                }
    except Exception:
        pass
    return None


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


def validate_contract(inv: InverterConfig, repo_dir: Path) -> list[str]:
    """Validerar att källkoden i repo_dir uppfyller BOLP-kontraktet."""
    errors = []

    # 1. Validera services.yaml
    services_path = inv.get("services_path")
    if services_path:
        svc_file = repo_dir / services_path
        if not svc_file.exists():
            candidates = list(repo_dir.rglob("services.yaml"))
            if candidates:
                svc_file = candidates[0]

        if not svc_file.exists():
            errors.append(f"Filen '{services_path}' hittades inte!")
        else:
            try:
                data = _parse_yaml_services(svc_file)

                for svc_name, expected_fields in inv["expected_services"].items():
                    if svc_name not in data:
                        errors.append(f"Tjänsten '{svc_name}' saknas i {svc_file.name}!")
                    else:
                        fields = data[svc_name].get("fields", {})
                        for field in expected_fields:
                            if field not in fields:
                                errors.append(
                                    f"Tjänsten '{svc_name}' saknar förväntat fält '{field}'!"
                                )
            except Exception as e:
                errors.append(f"Kunde inte tolka {svc_file}: {e}")

    # 2. Validera expected_key_groups
    key_groups = inv.get("expected_key_groups", [])
    if key_groups:
        comp_dir = repo_dir / inv.get("component_dir", "")
        target_dir = comp_dir if comp_dir.exists() else repo_dir

        all_text = ""
        for ext in ("*.py", "*.json", "*.yaml"):
            for f in target_dir.rglob(ext):
                try:
                    all_text += f.read_text(encoding="utf-8", errors="ignore").lower() + "\n"
                except Exception:
                    pass

        for group in key_groups:
            found_any = any(k.lower() in all_text for k in group)
            if not found_any:
                errors.append(
                    f"Ingen matchande nyckel från gruppen [{', '.join(group)}] hittades i kodbasen!"
                )

    return errors


def get_inverter_compatibility_markdown(fetch_github: bool = True) -> str:
    """Genererar en formaterad markdown-tabell över verifierade växelriktare för release notes."""
    lines = [
        "### 🔌 Verified Inverter Integrations",
        "This release has been contract-tested and verified against the following integration versions:",
        "",
        "| Inverter | Repository | Latest Release | Verified Commit | Status |",
        "|---|---|---|---|---|",
    ]
    token = os.getenv("GITHUB_TOKEN")

    for inv in INVERTERS:
        name = inv["name"]
        repo = inv["repo"]
        dir_name = inv["dir"]
        repo_dir = CODE_PROJECTS_DIR / dir_name

        if not repo_dir.exists():
            lines.append(f"| {name} | [`{repo}`](https://github.com/{repo}) | - | - | ⚠️ Not installed locally |")
            continue

        gh_tag = "-"
        if fetch_github:
            gh_data = get_github_latest_release(repo, token=token)
            if gh_data:
                gh_tag = gh_data.get("tag", "-")

        commit = run_git(repo_dir, ["log", "-1", "--format=%cs (%h)"])
        errors = validate_contract(inv, repo_dir)
        status = "✅ Verified" if not errors else f"❌ {len(errors)} issues"
        lines.append(f"| {name} | [`{repo}`](https://github.com/{repo}) | `{gh_tag}` | `{commit}` | {status} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Övervaka och validera kompatibilitet med externa växelriktar-integrationer."
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Kör 'git pull' i samtliga klonade inverter-repon.",
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Hoppa över GitHub API-anrop (snabbare körning utan nätverk).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Avbryt med felkod om någon växelriktare saknas lokalt.",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")

    print("\n" + "=" * 70)
    print(" 🔌 BATTERY OPTIMIZER LIGHT - VÄXELRIKTAR-STATUS & KONTRAKTSKOLL")
    print("=" * 70)
    print(f"📁 Basmapp: {CODE_PROJECTS_DIR.resolve()}\n")

    summary_rows = []
    has_contract_error = False
    has_missing_repo = False

    for inv in INVERTERS:
        name = inv["name"]
        repo_slug = inv["repo"]
        dir_name = inv["dir"]
        repo_dir = CODE_PROJECTS_DIR / dir_name

        print(f"🔍 Undersöker {name} ({dir_name})...")

        if not repo_dir.exists():
            print(f"   ⚠️  Mappen '{dir_name}' saknas i {CODE_PROJECTS_DIR}.\n")
            summary_rows.append((name, "Saknas lokalt", "-", "❌ Ej installerad"))
            has_missing_repo = True
            continue

        if not (repo_dir / ".git").exists():
            print(f"   ⚠️  '{dir_name}' är inte ett git-repository.\n")
            summary_rows.append((name, "Ej git-repo", "-", "⚠️ Ingen git"))
            has_missing_repo = True
            continue

        # Git info
        branch = run_git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
        last_commit = run_git(repo_dir, ["log", "-1", "--format=%cs %h %s"])
        commit_short = last_commit[:35] + ("..." if len(last_commit) > 35 else "")

        # Om --pull är begärt
        if args.pull:
            print("   ⬇️  Kör 'git pull'...")
            pull_res = run_git(repo_dir, ["pull"])
            print(f"      {pull_res}")
            # Uppdatera last_commit efter pull
            last_commit = run_git(repo_dir, ["log", "-1", "--format=%cs %h %s"])
            commit_short = last_commit[:35] + ("..." if len(last_commit) > 35 else "")

        # GitHub release info
        gh_info_str = "Hoppades över"
        gh_url = f"https://github.com/{repo_slug}/releases"
        if not args.skip_github:
            gh_release = get_github_latest_release(repo_slug, token=token)
            if gh_release:
                gh_info_str = f"{gh_release['tag']} ({gh_release['date']})"
                gh_url = gh_release.get("url", gh_url)
            else:
                gh_info_str = "Ingen release/API-gräns"

        # Kontraktsvalidering
        contract_errors = validate_contract(inv, repo_dir)
        status_str = "✅ Kompatibel"
        if contract_errors:
            has_contract_error = True
            status_str = f"❌ {len(contract_errors)} fel"
            print(f"   🚨 Kontraktsfel för {name}:")
            for err in contract_errors:
                print(f"      • {err}")
        else:
            print("   ✅ Kontrakt godkänt: alla nödvändiga tjänster och nycklar hittades.")

        print(f"   📌 Lokal commit : {commit_short} (branch: {branch})")
        print(f"   🌐 GitHub release: {gh_info_str}")
        print(f"   🔗 Changelog     : {gh_url}\n")

        summary_rows.append((name, commit_short, gh_info_str, status_str))

    # Skriv ut sammanställningstabell
    print("\n" + "=" * 70)
    print(" 📊 SAMMANSTÄLLNING")
    print("=" * 70)
    fmt = "{:<24} {:<32} {:<22} {:<15}"
    print(fmt.format("Integration", "Lokal commit", "Senaste release", "Status"))
    print("-" * 95)
    for r in summary_rows:
        print(fmt.format(r[0][:23], r[1][:31], r[2][:21], r[3]))
    print("=" * 70)
    print("Tips: Kör 'python scripts/check_inverters.py --pull' för att synka ner senaste kod.")
    print("=" * 70 + "\n")

    if has_contract_error:
        print("❌ Kontraktsvalidering misslyckades för en eller flera växelriktare!\n")
        sys.exit(1)

    if args.strict and has_missing_repo:
        print("❌ En eller flera växelriktare saknas lokalt i strict-läge!\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

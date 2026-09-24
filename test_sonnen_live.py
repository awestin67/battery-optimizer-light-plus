#!/usr/bin/env python3
"""Interaktivt testskript för att testa Sonnens API direkt mot batteriet."""
import argparse
import json
import sys
import requests

def test_endpoint(title: str, method: str, url: str, headers: dict, data=None, json_data=None):
    print(f"\n{'='*70}")
    print(f"👉 {title}")
    print(f"   {method} {url}")
    if json_data is not None:
        print(f"   JSON Body: {json.dumps(json_data)}")
    if data is not None:
        print(f"   Form Data: {data}")
    print(f"{'-'*70}")

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=5)
        elif method.upper() == "PUT":
            if json_data is not None:
                resp = requests.put(url, headers=headers, json=json_data, timeout=5)
            else:
                resp = requests.put(url, headers=headers, data=data, timeout=5)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, json=json_data or {}, timeout=5)
        else:
            print(f"❌ Okänd metod: {method}")
            return None

        status_icon = "✅" if resp.status_code in (200, 201, 204) else "❌"
        print(f"   Status: {status_icon} {resp.status_code} {resp.reason}")
        try:
            body = resp.json()
            print(f"   Response: {json.dumps(body, indent=2)}")
        except Exception:
            print(f"   Response Text: {resp.text.strip()}")
        return resp
    except Exception as e:
        print(f"   ❌ Anropsfel: {e}")
        return None

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Testa Sonnen API V2 direkt.")
    parser.add_argument("ip", nargs="?", help="Batteriets IP-adress (t.ex. 192.168.1.50)")
    parser.add_argument(
        "--test-only",
        choices=["status", "limits", "config", "diag"],
        help="Kör endast en kategori av tester",
    )
    args = parser.parse_args()

    ip = args.ip
    token = args.token

    if not ip:
        ip = input("Ange batteriets IP-adress: ").strip()
    if not token:
        token = input("Ange Auth-Token: ").strip()

    if not ip or not token:
        print("❌ IP-adress och Auth-Token krävs för att köra testerna.")
        sys.exit(1)

    base_url = f"http://{ip.replace('http://', '').replace('https://', '').rstrip('/')}:80"
    headers_json = {
        "Auth-Token": token,
        "Content-Type": "application/json"
    }
    headers_form = {
        "Auth-Token": token
    }

    print(f"\n🚀 Startar Sonnen API-test mot {base_url}")
    print(f"   Auth-Token: {token[:4]}...{token[-4:] if len(token) > 8 else ''}")

    # =========================================================================
    # STEG 1: Kontrollera grundstatus och nuvarande konfiguration
    # =========================================================================
    if not args.test_only or args.test_only == "status":
        test_endpoint("1.1 Läs systemstatus (öppen)", "GET", f"{base_url}/api/v2/status", headers_json)
        test_endpoint("1.2 Läs konfiguration", "GET", f"{base_url}/api/v2/configurations", headers_json)
        test_endpoint("1.3 Läs firmware-version", "GET", f"{base_url}/api/v2/configurations/DE_Software", headers_json)
        test_endpoint("1.4 Läs aktiva site limits", "GET", f"{base_url}/api/v2/site/limits", headers_json)

    # =========================================================================
    # STEG 2: Testa PUT /api/v2/site/limits med olika payloads och duration-format
    # =========================================================================
    if not args.test_only or args.test_only == "limits":
        print(f"\n{'#'*70}")
        print("### TESTNING AV PUT /api/v2/site/limits")
        print(f"{'#'*70}")

        # Test A: duration PT30S (Swagger standard) med p_gcp_max_import_limit
        test_endpoint(
            "2.1 Test: duration 'PT30S' (Swagger standard) + p_gcp_max_import_limit: 4500",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"duration": "PT30S", "p_gcp_max_import_limit": 4500}
        )

        # Test B: duration PT600S (10 minuter i sekundformat) med p_gcp_max_import_limit
        test_endpoint(
            "2.2 Test: duration 'PT600S' (10 min i sekunder) + p_gcp_max_import_limit: 4500",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"duration": "PT600S", "p_gcp_max_import_limit": 4500}
        )

        # Test C: Utan duration (använd batteriets standardtimeout)
        test_endpoint(
            "2.3 Test: Utan duration + p_gcp_max_import_limit: 4500",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"p_gcp_max_import_limit": 4500}
        )

        # Test D: duration PT10M (för att bekräfta om 'M' var orsaken till 400-felet)
        test_endpoint(
            "2.4 Test: duration 'PT10M' (minutformat) + p_gcp_max_import_limit: 4500",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"duration": "PT10M", "p_gcp_max_import_limit": 4500}
        )

        # Test E: Smart HOLD (p_bess_inv_max_export_limit: 0)
        test_endpoint(
            "2.5 Test: Smart HOLD (p_bess_inv_max_export_limit: 0, duration: 'PT30S')",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"duration": "PT30S", "p_bess_inv_max_export_limit": 0}
        )

        # Test F: Både GCP-gräns och Inverter exportgräns
        test_endpoint(
            "2.6 Test: Både GCP-import och Inverter-export (duration: 'PT30S')",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={
                "duration": "PT30S",
                "p_bess_inv_max_export_limit": 0,
                "p_gcp_max_import_limit": 4500
            }
        )

        # Test G: Tom payload (verifiera om 'no limits' ger felet 'Site limits can only be set in EM2')
        test_endpoint(
            "2.7 Test: Tom payload enbart duration: 'PT30S' (förväntas ge 400 'no limits specified')",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={"duration": "PT30S"}
        )

    # =========================================================================
    # STEG 3: Testa ändring av driftläge via site/configurations och configurations
    # =========================================================================
    if not args.test_only or args.test_only == "config":
        print(f"\n{'#'*70}")
        print("### TESTNING AV DRIFTLÄGESÄNDRING")
        print(f"{'#'*70}")

        test_endpoint(
            "3.1 Sätt Mode 2 via PUT /api/v2/site/configurations (JSON)",
            "PUT",
            f"{base_url}/api/v2/site/configurations",
            headers_json,
            json_data={"EM_OperatingMode": "2", "EM_USOC": "0"}
        )

        test_endpoint(
            "3.2 Sätt Mode 2 via PUT /api/v2/configurations (Form-encoded)",
            "PUT",
            f"{base_url}/api/v2/configurations",
            headers_form,
            data={"EM_OperatingMode": "2"}
        )

    # =========================================================================
    # STEG 4: Avancerad diagnostik (Full payload, setpoint och legacy endpoints)
    # =========================================================================
    if not args.test_only or args.test_only == "diag":
        print(f"\n{'#'*70}")
        print("### STEG 4: AVANCERAD DIAGNOSTIK")
        print(f"{'#'*70}")

        # Test 4.1: Exakt Swagger-exempel med alla fält ifyllda
        test_endpoint(
            "4.1 Exakt Swagger-exempel med alla gränser ifyllda",
            "PUT",
            f"{base_url}/api/v2/site/limits",
            headers_json,
            json_data={
                "duration": "PT30S",
                "i_bess_storage_max_charge_limit": 32,
                "i_bess_storage_max_discharge_limit": 16,
                "p_bess_inv_max_export_limit": 3300,
                "p_bess_inv_max_import_limit": 3300,
                "p_gcp_max_export_limit": 4500,
                "p_gcp_max_import_limit": 4500
            }
        )

        # Test 4.2: Testa PUT /api/v2/site/setpoint
        test_endpoint(
            "4.2 Testa PUT /api/v2/site/setpoint (nollställning)",
            "PUT",
            f"{base_url}/api/v2/site/setpoint",
            headers_json,
            json_data={
                "duration": "PT30S",
                "p_bess_inv_export_import_setpoint": 0
            }
        )

        # Test 4.3: Testa legacy POST setpoint/charge/0
        test_endpoint(
            "4.3 Testa legacy POST /api/v2/setpoint/charge/0",
            "POST",
            f"{base_url}/api/v2/setpoint/charge/0",
            headers_json
        )

        # Test 4.4: Testa legacy POST setpoint/discharge/0
        test_endpoint(
            "4.4 Testa legacy POST /api/v2/setpoint/discharge/0",
            "POST",
            f"{base_url}/api/v2/setpoint/discharge/0",
            headers_json
        )

    print(f"\n{'='*70}")
    print("🏁 Testskriptet har slutförts!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()

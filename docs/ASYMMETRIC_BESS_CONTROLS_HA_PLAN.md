# Implementationsplan: Asymmetrisk BESS-styrning (Huawei, Sigenergy, Solis)

**Mål:** Utnyttja separata laddnings- och urladdningsbegränsningar för växelriktare från **Huawei**, **Sigenergy** och **Solis** i Home Assistant-komponenten (`battery_optimizer_light_plus`), så att de kan dra nytta av de asymmetriska driftlägena som skickas från optimeringsmolnet:
- **Smart Sol-Export (`action == "HOLD"`):** `reason = "[Smart Sol-Export] Säljer solöverskott till nätet pga högt pris (X.X kW)"`
- **Skyddad Solladdning (`action == "IDLE"`):** `reason = "[Skyddad Solladdning] Laddar solöverskott (X.X kW)"`

---

## 📌 1. Bakgrund & Arkitektur

### Vad molntjänsten skickar (`battery-optimizer-light`)
Molntjänsten skickar med generiska BESS-gränser via `site_limits` i varje besluts-payload:
```json
{
  "action": "HOLD",
  "reason": "[Smart Sol-Export] Säljer solöverskott till nätet pga högt pris (3.2 kW)",
  "site_limits": {
    "p_bess_inv_max_import_limit": 0,
    "p_bess_inv_max_export_limit": null
  }
}
```

Koordinatorn i Home Assistant ([`coordinator.py`](../custom_components/battery_optimizer_light_plus/coordinator.py)) vidarebefordrar redan `site_limits` till alla batteridrivrutiner via:
```python
await self.battery_api.apply_action(
    action,
    target_kw,
    site_limits=site_limits,
    sonnen_site_limits=site_limits,
)
```

### De 4 Driftstillstånden

| Tillstånd | Molnets `action` | `p_bess_inv_max_import_limit` | `p_bess_inv_max_export_limit` | Innebörd för hårdvaran |
|---|:---:|:---:|:---:|---|
| **Normal IDLE** | `IDLE` | `None` | `None` | Fri egenförbrukning: batteriet får ladda från sol och täcka husets förbrukning. |
| **Skyddad Solladdning** | `IDLE` | `None` | `0` W | Batteriet får ladda sol, men **spärras från urladdning** så att laddningen sparas till kvällstoppen. |
| **Smart Sol-Export** | `HOLD` | `0` W | `None` | Batteriet **spärras från laddning** (solel tvingas ut på nätet till toppris), men får urladda för att stötta huset vid moln/spikar. |
| **Ren HOLD** | `HOLD` | `0` W | `0` W | Både laddning och urladdning frysta (buffertskydd eller fryst batteri). |

---

## 🔌 2. Implementation per Inverter

### A. Huawei Solar (`huawei.py`)

Integrationen `wlcx/huawei_solar` styr batteriet via `number`-entiteter och tjänster (`forcible_charge`, `forcible_discharge`, `stop_forcible_charge`).

#### 1. Nya entiteter & funktioner
* Befintlig urladdningsentitet: `_get_max_discharge_entity()` (`storage_maximum_discharge_power` i W).
* **Ny metod:** `_get_max_charge_entity()`:
  * Söker efter: `["storage_maximum_charge_power", "storage_maximum_charging_power", "maximum_charging_power", "battery_maximum_charge_power"]`.

#### 2. Styrlogik i `apply_action`
* **Smart Sol-Export (`HOLD` + `export is None`):**
  1. `storage_maximum_charge_power` sätts till `0 W` (hindrar batteriet från att absorbera solenergi; solel tvingas till nätet).
  2. `storage_maximum_discharge_power` återställs till användarens maxgräns (batteriet kan stötta huset vid moln/spikar).
  3. `stop_forcible_charge` anropas så att växelriktaren arbetar i standardläge (Maximise Self-Consumption).
* **Skyddad Solladdning (`IDLE` + `export == 0`):**
  1. `storage_maximum_discharge_power` sätts till `0 W` (spärrar urladdning till huset).
  2. `storage_maximum_charge_power` återställs till max (batteriet laddas av solöverskott).
  3. `stop_forcible_charge` anropas.
* **Ren HOLD (`HOLD` + `export == 0`):**
  1. Både `charge_power` och `discharge_power` sätts till `0 W`.
  2. `stop_forcible_charge` anropas.
* **Normal IDLE (`IDLE` + `export is None`):**
  1. Både `charge_power` och `discharge_power` återställs till max.
  2. `stop_forcible_charge` anropas.

---

### B. Sigenergy (`sigenergy.py`)

Sigenergy har två `number`-entiteter i kW (`max_charging_limit` och `max_discharging_limit`) samt ett driftläge (`select.ems_control_mode`).

#### 1. Driftlägesval i `ems_control_mode`
* `"Maximum Self Consumption"` = Lokal reglering baserad på satta effektgränser.
* `"Standby"` = Batteriet helt fryst (både laddning och urladdning 0 kW).

#### 2. Styrlogik i `apply_action`
* **Smart Sol-Export (`HOLD` + `export is None`):**
  1. `charge_power_entity` sätts till `0 kW` (solel tvingas ut på elnätet).
  2. `discharge_power_entity` återställs till max (parerar huslaster).
  3. `mode_entity` sätts till `"Maximum Self Consumption"` (inte Standby, för att tillåta urladdning).
* **Skyddad Solladdning (`IDLE` + `export == 0`):**
  1. `discharge_power_entity` sätts till `0 kW` (spärrar urladdning till huset).
  2. `charge_power_entity` återställs till max (solladdning fri).
  3. `mode_entity` sätts till `"Maximum Self Consumption"`.
* **Ren HOLD (`HOLD` + `export == 0`):**
  1. `charge_power_entity` sätts till `0 kW`, `discharge_power_entity` sätts till `0 kW`.
  2. `mode_entity` sätts till `"Standby"`.
* **Normal IDLE:**
  1. Både `charge_power_entity` och `discharge_power_entity` återställs till max.
  2. `mode_entity` sätts till `"Maximum Self Consumption"`.

---

### C. Solis Modbus (`solis_modbus.py`)

Solis Modbus styr via Modbus-register exponerade som HA-entiteter.

#### 1. Nya entiteter & konstanter
* Befintlig: `KEYS_BATTERY_DISCHARGE_LIMIT = ["battery_discharge_limit_power", "discharge_limit_power"]`.
* **Ny:** `KEYS_BATTERY_CHARGE_LIMIT = ["battery_charge_limit_power", "charge_limit_power"]`.

#### 2. Styrlogik i `apply_action`
* **Smart Sol-Export (`HOLD` + `export is None`):**
  1. `charge_limit_entity` sätts till `0 W` (förhindrar solladdning; solel exporteras).
  2. `discharge_limit_entity` återställs till max (batteriet täcker husbehov).
  3. `mode_select_entity` sätts till `opt_none` (Auto / Self-consumption).
* **Skyddad Solladdning (`IDLE` + `export == 0`):**
  1. `discharge_limit_entity` sätts till `0 W` (spärrar urladdning till huset).
  2. `charge_limit_entity` återställs till max (batteriet laddas från sol).
  3. `mode_select_entity` sätts till `opt_none` (Auto).
* **Ren HOLD (`HOLD` + `export == 0`):**
  1. Både `discharge_limit_entity` och `charge_limit_entity` sätts till `0 W`.
  2. `mode_select_entity` sätts till `opt_none`.
* **Normal IDLE:**
  1. Båda gränserna återställs till max och läget sätts till `opt_none` (Auto).

---

## 🛡️ 3. Säkerhet & Hårdvaruhänsyn

1. **Slitageskydd för EEPROM / Flash-minne:**  
   Växelriktare sparar ofta registerändringar i icke-flyktigt minne. Skrivning via `number.set_value` ska **endast utföras om entitetens nuvarande värde skiljer sig från det nya värdet**.
2. **Graceful Fallback:**  
   Om en anläggning saknar laddningsbegränsnings-entiteten loggas en `DEBUG`-notis och drivrutinen faller sömlöst tillbaka till befintlig logik utan krasch.
3. **Klartext-loggning:**  
   Varje drivrutin loggar tydligt på `DEBUG`-nivå när läget aktiveras:
   * `"Huawei: Aktiverar Smart Sol-Export (laddning 0 W, urladdning fri)"`
   * `"Sigenergy: Aktiverar Skyddad Solladdning (urladdning 0 kW, laddning fri)"`
   * `"Solis: Aktiverar Smart Sol-Export (laddning 0 W, urladdning fri)"`

---

## 🧪 4. Testplan

I repot `battery-optimizer-light-base/tests/`:
1. `tests/test_huawei.py`: Verifiera de 4 driftstillstånden och anropen till `number.set_value`.
2. `tests/test_sigenergy.py`: Verifiera val av `Maximum Self Consumption` vs `Standby` och kW-gränser.
3. `tests/test_solis_modbus.py`: Verifiera Modbus-skrivningar till laddnings- och urladdningsregister.

---

## 🚀 5. Genomförandesteg

1. **Steg 1 (Huawei):** Uppdatera `huawei.py` med `_get_max_charge_entity()` och asymmetrisk hantering i `apply_action`. Skapa enhetstester i `tests/test_huawei.py`.
2. **Steg 2 (Sigenergy):** Uppdatera `sigenergy.py` med asymmetrisk hantering av `charge_power_entity` och `discharge_power_entity` samt korrekt `ems_control_mode`. Skapa tester i `tests/test_sigenergy.py`.
3. **Steg 3 (Solis):** Uppdatera `solis_modbus.py` med `KEYS_BATTERY_CHARGE_LIMIT` och asymmetriska register. Skapa tester i `tests/test_solis_modbus.py`.
4. **Steg 4:** Kör hela testsviten i `battery-optimizer-light-base` (`pytest tests/`) för att säkerställa noll regressioner.

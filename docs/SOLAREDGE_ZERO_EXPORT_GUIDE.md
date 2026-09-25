# 📖 Guide: Dynamisk Exportbegränsning (Zero Export) för SolarEdge & AC-kopplade Solceller

Denna guide beskriver hur du skyddar din anläggning mot **negativa elpriser** när du har ett AC-kopplat system, till exempel ett **Sonnen-batteri** kombinerat med en separat solcellsväxelriktare som **SolarEdge**.

---

## 📌 Bakgrund: Varför behövs en separat styrning för SolarEdge?

I ett **hybridsystem** (där solceller och batteri är anslutna till samma växelriktare) sköter Battery Optimizer Light all exportbegränsning internt.

Men i ett **AC-kopplat system** (där solceller sitter på en separat SolarEdge-växelriktare och batteriet på en separat enhet som Sonnen):
1. **När batteriet har ledig kapacitet:** Sonnen känner av solelöverskottet vid elmätaren och laddar batteriet med effekten från AC-nätet. Ingen export sker.
2. **När batteriet blir 100% fullt:** Sonnen kan inte ta emot mer energi. Eftersom Sonnen inte har någon direkt styrkabel till SolarEdge, fortsätter SolarEdge att mata ut solel på nätet. Vid negativa elpriser innebär detta att du betalar för att exportera el.

För att lösa detta beräknar molnet i realtid en **dynamisk exportgräns** och publicerar den i Home Assistant på:
👉 `sensor.optimizer_light_dynamic_export_limit` (kW)

* **När priset är > 0 kr (eller ingen risk finns):** Sensorn är obegränsad (`unknown`).
* **När priset är < 0 kr:** Sensorn anger `Husets last + vad batteriet hinner suga upp`.
* **När batteriet når 100% vid minuspris:** Sensorn sjunker till enbart **husets faktiska last** (så att nätutbytet blir 0 W).

---

## 🚀 Metod 1: Använd vår färdiga Blueprint (Enklast)

Vi har inkluderat en färdig Home Assistant Blueprint i repot som gör hela jobbet åt dig med några få klick.

### 1. Importera Blueprint
Kopiera länken nedan och lägg till den under **Inställningar -> Automationer & Scener -> Blueprints -> Importera Blueprint** i Home Assistant:

```text
https://github.com/awestin67/battery-optimizer-light-plus/blob/main/blueprints/automation/solaredge_zero_export.yaml
```

*(Eller kopiera filen [`blueprints/automation/solaredge_zero_export.yaml`](../blueprints/automation/solaredge_zero_export.yaml) till din Home Assistant under `/config/blueprints/automation/solaredge_zero_export.yaml`).*

### 2. Skapa automation från Blueprinten
1. Välj **Skapa automation från Blueprint**.
2. Ange din SolarEdge-entitet för aktiv effektgräns (t.ex. `number.solaredge_active_power_limit`).
3. Ange din växelriktares märkeffekt i kW (t.ex. `15` för en SolarEdge SE15k, eller `10` för SE10k).
4. Klicka på **Spara**. Klart!

---

## 🛠️ Metod 2: Manuell Home Assistant Automation (YAML)

Om du föredrar att lägga till automationen manuellt i din `automations.yaml` kan du använda följande kod:

```yaml
alias: ☀️ SolarEdge - Dynamisk Exportbegränsning (Zero Export)
description: Justerar SolarEdge Active Power Limit vid minuspriser baserat på Battery Optimizer Light.
trigger:
  - platform: state
    entity_id: sensor.optimizer_light_dynamic_export_limit
variables:
  # Ändra till din växelriktares storlek i kW (t.ex. 10.0 eller 15.0)
  inverter_capacity_kw: 15.0
  raw_state: "{{ states('sensor.optimizer_light_dynamic_export_limit') }}"
action:
  - choose:
      # 1. Normala priser (inget minuspris) -> Återställ SolarEdge till 100%
      - conditions:
          - condition: template
            value_template: >
              {{ raw_state in ['unknown', 'unavailable', 'none', 'None', ''] or not (raw_state | is_number) }}
        sequence:
          - service: number.set_value
            target:
              entity_id: number.solaredge_active_power_limit
            data:
              value: 100

      # 2. Minuspriser aktiva -> Sätt gräns i % av märkeffekt
      - conditions:
          - condition: template
            value_template: >
              {{ raw_state | is_number }}
        sequence:
          - service: number.set_value
            target:
              entity_id: number.solaredge_active_power_limit
            data:
              value: >
                {% set limit_kw = raw_state | float(0) %}
                {% set cap = inverter_capacity_kw | float(15) %}
                {% if cap > 0 %}
                  {% set pct = ((limit_kw / cap) * 100) | round(0) | int %}
                  {{ [ [pct, 0] | max, 100 ] | min }}
                {% else %}
                  100
                {% endif %}
mode: restart
```

---

## 🏠 Metod 3: För användare med Homey Pro & MQTT

Om du kör **Homey Pro** som central hemautomatiseringsplattform kan du styra SolarEdge via Homey och MQTT:

1. **Skicka sensorn till Homey:** Använd Home Assistants MQTT Statestream eller MQTT Hub för att publicera `homeassistant/sensor/optimizer_light_dynamic_export_limit/state`.
2. **Skapa ett avancerat flöde i Homey:**
   * **Trigger:** *When a message is received on topic `homeassistant/sensor/optimizer_light_dynamic_export_limit/state`*.
   * **Filter:** Kolla att meddelandet inte är exakt lika med en lokal tagg `last_export_limit` (minskar onödiga anrop).
   * **Villkor:**
     * Om värdet är `unknown` -> Sätt SolarEdge Active Power Limit till **100%**.
     * Om värdet är numeriskt -> Räkna ut procent med formeln:
       `{{round(Message received from topic / 15 * 100)}}`
       och skicka kommandot *Set Active Power Limit* till SolarEdge.
     * Uppdatera `last_export_limit`.

---

## 🧪 Hur du testar att styrningen fungerar

1. Gå till **Utvecklarverktyg (Developer Tools) -> Tillstånd (States)** i Home Assistant.
2. Leta upp `sensor.optimizer_light_dynamic_export_limit`.
3. Sätt tillståndet manuellt till t.ex. `3.0`.
4. Kontrollera att `number.solaredge_active_power_limit` omedelbart uppdateras till rätt procentsats (t.ex. `20%` för en 15 kW växelriktare: 3 / 15 = 20%).
5. Sätt tillståndet tillbaka till `unknown` och kontrollera att SolarEdge återgår till `100%`.

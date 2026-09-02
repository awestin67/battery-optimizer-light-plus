# 🔋 Battery Optimizer Light Plus

<img src="https://raw.githubusercontent.com/awestin67/battery-optimizer-light-plus/main/custom_components/battery_optimizer_light_plus/brand/logo.png" alt="Logo" width="200"/>

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate and Test](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml/badge.svg)](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=awestin67&repository=battery-optimizer-light-plus&category=integration)

**Battery Optimizer Light Plus** är en lättviktig hybridlösning som kopplar din Home Assistant till en smart molntjänst för hembatterier.

Systemet kombinerar **Molnintelligens** (för prisoptimering och arbitrage) med **Lokal Kraft** (för blixtsnabb effektvakt/peak shaving direkt i Home Assistant). Allt är nu samlat i **en enda integration** där du enkelt väljer din batterityp vid installationen.

---

## ✨ Funktioner

* **📈 Prisoptimering (Arbitrage):** Laddar när elen är billig och säljer/laddar ur när den är dyr baserat på spotpriser och prognoser.
* **🛡️ Smart Effektvakt (Peak Shaving):** Övervakar husets nettolast i realtid för att kapa effekttoppar lokalt.
    * *Molnstyrning:* Effektvakten kan dynamiskt pausas eller justeras från molnet.
    * *Hysteres:* Inbyggd smart logik förhindrar "fladder" när lasten pendlar runt gränsvärdet.
* **🤖 Zero-Config Automation:** Integrationen lyssnar automatiskt på beslut från molnet och styr ditt batteri. Inga krångliga YAML-skript eller automationer krävs!
* **📊 Analys:** Följ dina besparingar och effekttoppar via vår snygga [Web Dashboard](https://battery-prod.awestinconsulting.se).
* **🚫 Zero Export (Skydd vid negativa priser):** Tar emot en dynamisk exportgräns (kW) från molnet. Används för att förhindra att systemet förlorar pengar på att sälja solel när spotpriset plus din nätnytta understiger noll.
* **🚗 Smart Elbilsstöd (Basic):** Peka ut en sensor från din laddbox i Home Assistant så informeras molnet automatiskt när bilen laddas, vilket förhindrar att ditt hembatteri oavsiktligt töms in i elbilen (sätter batteriet i `HOLD`). **Men det är ännu smartare:** Om systemet känner av att solcellerna producerar mer el än vad huset och elbilen konsumerar tillsammans, övergår det automatiskt till `IDLE` så att hembatteriet kan passa på att laddas upp av det kvarvarande solelöverskottet!
  *(Integrationen känner automatiskt igen tillstånden `on`, `true`, `1`, `charging`, `på`, `charge`, `sant` samt numeriska effektvärden `> 0` W).*
* **🚗 Smart Elbilsstöd (V2 - Sensor-based):** Styr din elbilsladdning automatiskt baserat på elpriset (stöd för upp till 2 bilar)!
    * Peka ut Helpers i Home Assistant (Target kWh, Max kW, Avresetid) och din "cable connected"-sensor.
    * När du sätter i kabeln räknar molnet automatiskt ut när laddningen ska starta och stoppa och exponerar en tidslinje som JSON på en sensor (`sensor.optimizer_light_ev_schedule`).
    * **Hur det fungerar:** Du skapar en egen automation i Home Assistant som läser av tidslinjen och skickar "Start" eller "Stop" till din specifika laddbox (Easee, Zaptec, Tesla, etc) vid rätt tillfälle.
* **🚿 Smart Varmvattenoptimering (VVB Boost):** Optimeraren identifierar solöverskott och billiga eltimmar för att automatiskt värma varmvattenberedare eller aktivera plusvärme på värmepumpar (SG Ready / IVT). Exponeras via en `binary_sensor` och en förklarande statussensor.
* **⏸️ Stöd för CheckWatt & Stödtjänster (Extern Paus):** Om ett externt system behöver exklusiv kontroll över batteriet kan du peka ut en Paus-sensor (t.ex. en `input_boolean` eller status-sensor för CheckWatt). 
  *(Integrationen reagerar automatiskt på tillstånden `on`, `true`, `1`, `active`, `yes`, `på` eller `sant`. Då pausas all styrning från Battery Optimizer och batteriet sätts i `IDLE` så att systemen inte slåss om kommandona).*
* **🔌 Off-grid & Strömavbrottsskydd:** Peka ut en sensor som visar om huset är i off-grid-läge (t.ex. vid strömavbrott). Optimeraren pausas automatiskt tills nätströmmen är tillbaka. *(För Sonnen detekteras detta automatiskt via batteriets eget API).*

---

## 🔌 Stödda Batterier & Krav

### ☀️ Sonnen
Kräver ett Sonnen-batteri med **API v2** aktiverat.
*   **Auth-Token:** Du behöver ditt Auth-Token för lokal styrning. Logga in på ditt batteri (`http://<IP-ADRESS>/dash/login`) som *User*, välj **Software integration**, slå på **JSON API** (Read & Write) och kopiera ditt Auth-Token.
*   **Backup Reserv (EM_USOC):** Om du använder Sonnens backup-funktion (reservström) läser integrationen automatiskt av din reserverade nivå (t.ex. 5%). Denna reserv döljs lokalt så att molnet ser ditt tillgängliga fönster som 0-100%. **Viktigt:** Du måste dra av denna procentandel från din *totala batterikapacitet* när du konfigurerar ditt batteri i molnportalen (t.ex. 22 kWh - 5% = 20.9 kWh) för att AI:n ska räkna rätt på tillgänglig energi.

### 🌑 Huawei Luna2000
Styr Huawei-batterier via den officiella Home Assistant-integrationen.
*   **Krav:** En fungerande, förkonfigurerad installation av den officiella `Huawei Solar`-integrationen.
*   **Notera:** För Huawei inverteras batterisensorn automatiskt så att **Plus (+)** betyder att batteriet **laddar** och **Minus (-)** betyder att det **laddar ur**, vilket matchar standardbeteendet för Huawei Solar-integrationen.

### ⚡ Homevolt
Styr Homevolt-batterier lokalt via Home Assistant.
*   **Krav:** Integrationen [Homevolt Local](https://github.com/JohNan/homeassistant-homevolt-local) (finns att ladda ner via HACS) måste vara installerad och konfigurerad först.
*   **Notera:** Integrationen stöder *Auto-Discovery* och hittar automatiskt dina sensorer för SoC, Batteri, Nät och Huslast vid installationen!

### 🔌 Solis Modbus
Styr Solis-batterier lokalt via Pho3niX90's Solis Modbus-integration.
*   **Krav:** En fungerande, förkonfigurerad installation av [Solis Modbus](https://github.com/hultenvp/solis-sensor) (HACS).
*   **Kompatibilitet:** Byggd och optimerad primärt för **Solis S6 Hybrid** (EH-modeller).
*   **Notera:** Integrationen stöder *Auto-Discovery* och letar automatiskt upp dina mät- och styrentiteter vid installationen. Den anpassar sig dessutom dynamiskt till olika språk och versioner av integrationen!

### 🔋 Sigenergy
Styr Sigenergy-växelriktare lokalt via Modbus.
*   **Krav:** En fungerande, förkonfigurerad installation av [Sigenergy-Local-Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus) (via HACS).
*   **Notera:** Integrationen stöder *Auto-Discovery* och letar automatiskt upp dina mät- och styrentiteter vid installationen. Den känner automatiskt av om integrationen använder Watt (W) eller Kilowatt (kW) och sköter all omvandling!

### 🔋 Solinteg
Styr Solinteg-växelriktare lokalt via Modbus.
*   **Viktigt Krav:** Du *måste* använda integrationen [SolaX Inverter Modbus](https://github.com/wills106/homeassistant-solax-modbus) (via HACS) för att ansluta din Solinteg-växelriktare till Home Assistant. Även fast den heter SolaX, så har den inbyggt stöd för Solinteg. Andra Solinteg-integrationer stöds ej i dagsläget då de saknar standardiserade styrentiteter.
*   **Notera:** Integrationen stöder *Auto-Discovery* och letar automatiskt upp dina mät- och styrentiteter från SolaX-integrationen.

### ☀️ Kostal Plenticore
Styr Kostal Plenticore-växelriktare med anslutet hembatteri (t.ex. BYD Battery-Box) via Modbus TCP.
*   **Krav:** 
    1. Den officiella integrationen [Kostal Plenticore](https://www.home-assistant.io/integrations/kostal_plenticore/) måste vara installerad och konfigurerad i Home Assistant (används för att läsa av sensorer för SoC, husförbrukning, solproduktion och nätutbyte).
    2. **Aktivera extern Modbus-styrning:** Du måste ställa in växelriktaren på extern styrning:
       - Logga in i Kostal Plenticores lokala webbgränssnitt som *Installatör* (eller administratör).
       - Gå till **Inställningar** -> **Batterihantering** (*Battery management*).
       - Välj batteriläge **"Extern styrning via Modbus-protokoll (TCP)"** (*External battery control via Modbus TCP*).
       - Kontrollera att Modbus TCP är aktiverat (standardport: `1502`, slave/enhets-ID: `71`).
*   **Notera:** Integrationen stöder *Auto-Discovery* – den upptäcker din Kostal-växelriktare, hämtar IP-adressen automatiskt från Home Assistant och länkar samman alla sensorer (`battery_soc`, `Home_P`, `Dc_P`, `Grid_P` och `Inverter:State`) helt utan manuell konfiguration!

### ☁️ Generic / Light
För dig som bara vill hämta optimeringsbeslut och räkna ut last lokalt, men sedan styra ditt batteri manuellt via egna automationsflöden. [Se exempel på automation här nere](#-automationer-för-generic--övriga-batterier).

---

## 📦 Installation

### Alternativ 1: Direkt via My Home Assistant (Snabbast)
Klicka på knappen nedan för att öppna integrationen direkt i HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=awestin67&repository=battery-optimizer-light-plus&category=integration)

### Alternativ 2: Sök i HACS
1. Öppna **HACS** i din Home Assistant.
2. Gå till **Integrationer** och sök efter **Battery Optimizer Light Plus**.
3. Klicka på **Ladda ner** och starta om Home Assistant vid behov.

<details>
<summary><b>Installera som anpassat arkiv (om den inte syns i standardkatalogen ännu)</b></summary>

1. Gå till **HACS** -> **Integrationer**.
2. Klicka på de tre prickarna uppe till höger och välj **Anpassade arkiv (Custom repositories)**.
3. Lägg till URL: `https://github.com/awestin67/battery-optimizer-light-plus` och välj kategori **Integration**.
4. Ladda ner "Battery Optimizer Light Plus" och starta om Home Assistant.
</details>

### Konfiguration
1. Gå till **Inställningar** -> **Enheter & Tjänster**.
2. Klicka på **Lägg till integration** och sök efter **Battery Optimizer Light Plus**.
3. Följ guiden:
    * **Steg 1:** Välj vilken typ av batteri du har (Sonnen, Huawei, Homevolt, Solis Modbus, Sigenergy, Solinteg, Kostal Plenticore, Generic).
    * **Steg 2:** Fyll i batterispecifika uppgifter (t.ex. IP och API-token för Sonnen, eller enheter för Huawei).
    * **Steg 3:** Fyll i din API-nyckel från Dashboarden. För alla märken utom Generic hittas de flesta mätvärden och styrentiteter automatiskt med Auto-Discovery. För **Generic** måste du dock manuellt peka ut dina sensorer.
    * **Steg 4 (Valfritt):** Peka ut **Husets totala förbrukning**. Om du saknar en pålitlig nätutbytes-sensor ("Grid Sensor (W) - Husets Nätutbyte") men istället har en sensor som visar husets totala last (t.ex. "House Total Load"), kan du välja den här. Lämna då fältet för Grid Sensor helt tomt!
    * **Steg 5 (Valfritt):** Peka ut din **Elbilsladdning Sensor** för att aktivera det smarta elbilsstödet.
    * **Steg 6 (Valfritt):** Peka ut en sensor för **Pausa Battery Optimizer** om du använder externa stödtjänster (ex. CheckWatt) som ibland behöver egen kontroll över batteriet.
    * **Steg 7 (Valfritt):** Peka ut en sensor för **Off-grid / Strömavbrott** för att tillfälligt pausa optimeraren vid nätbortfall.

**Tips:** Du kan när som helst klicka på **"Konfigurera"** på integrationen i Home Assistant för att ändra dina sensorer eller aktivera inställningar som **"Invertera Batteri Sensor"** (användbart om just din växelriktare rapporterar Plus för laddning istället för urladdning).

---

## 🤖 Användning & Automation

### Automatisk Styrning av Hembatteriet (Zero-Config)
Integrationen är skapad för att fungera direkt ur lådan. Den lyssnar automatiskt på beslut från molnet och styr ditt batteri utan att du behöver bygga några egna skript eller automationer!

### Smart Elbilsladdning (Sensor-baserad)
Integrationen stöder prissmart schemaläggning för **upp till två bilar samtidigt**, vilket garanterar att dina bilar laddas på dygnets billigaste timmar utan att överbelasta din huvudsäkring. Du hanterar själv start/stopp-automationerna i Home Assistant (eftersom olika laddboxar fungerar olika).

#### Steg-för-steg Guide (1 eller 2 bilar)

**Steg 1: Skapa Hjälpare (Helpers)**
Skapa följande Helpers i Home Assistant (*Inställningar -> Enheter och tjänster -> Hjälpare*) för att definiera dina laddbehov. För två bilar skapar du helt enkelt dubbla uppsättningar (t.ex. med ändelsen `_car1` och `_car2`):
- `input_number` för önskat mål i kWh (t.ex. `input_number.ev_target_kwh_car1`). Skala: 0-100.
- `input_number` för bilens maxeffekt i kW (t.ex. `input_number.ev_max_kw_car1`). Skala: 0-22.
- `input_datetime` för önskad avresetid (t.ex. `input_datetime.ev_depart_time_car1`). Ska endast visa Tid (Time).

**Steg 2: Koppla i Integrationen**
1. Gå till *Inställningar -> Enheter och tjänster*.
2. Klicka på **Konfigurera** på Battery Optimizer Light Plus.
3. Välj dina skapade Helpers från rullistorna för **Bil 1**. Ange även din `cable_connected`-sensor och din `is_charging`-sensor från din laddbox.
4. *(Har du en andra bil?)* Fyll i motsvarande rullistor för **Bil 2** längre ner på samma sida.

**Steg 3: Så här fungerar det i praktiken**
1. **Du pluggar in kabeln:** Din `cable_connected`-sensor slår om till `on`. 
2. **Schemat skapas:** Integrationen läser av dina Helpers och beräknar den billigaste tidslinjen. Om du pluggar in båda bilarna, skapas ett optimerat körschema för båda samtidigt!
3. **Data exponeras:** Schemat sparas i sensorn `sensor.optimizer_light_ev_schedule`. Attributet `schedules` innehåller start- och stopptider för dina bilar.

**Steg 4: Din Automation (Exempel)**
Skapa en automation i Home Assistant för respektive bil. Använd `Template` i din trigger för att trigga på starttiden, och passa även på att ställa in laddboxens effekt (`charge_kw`) till det värde som molnet har räknat ut är optimalt!

> **Tips:** Gå till *Automationer -> Skapa ny automation -> Klicka på de tre prickarna uppe till höger och välj "Redigera som YAML"*. Klistra sedan in koden nedan.

I templaten nedan anger du **samma namn för bilen** som du skrev in när du konfigurerade integrationen.

```yaml
# ==========================================
# AUTOMATION 1: Starta laddbox (Bil 1)
# ==========================================
alias: "EV: Starta laddning Bil 1"
trigger:
  - platform: template
    value_template: >-
      {% set car_name = 'Min första bil' %}  # Byt ut mot exakt det namn du gav bilen i integrationen
      {% set schedules = state_attr('sensor.optimizer_light_ev_schedule', 'schedules') %}
      {% if schedules and car_name in schedules and schedules[car_name]|length > 0 %}
        {% set start_time = as_timestamp(schedules[car_name][0]['start']) %}
        {{ now().timestamp() >= start_time }}
      {% else %}
        false
      {% endif %}
action:
  # 1. Ställ in laddboxens effekt baserat på molnets optimering
  - service: number.set_value
    target:
      # Byt ut mot din laddbox entitet för strömgräns (t.ex. number.easee_dynamic_circuit_limit eller Zaptecs motsvarighet)
      entity_id: number.din_laddbox_effekt_car1
    data:
      value: >-
        {% set car_name = 'Min första bil' %}
        {{ state_attr('sensor.optimizer_light_ev_schedule', 'schedules')[car_name][0]['charge_kw'] }}
  # 2. Slå på strömmen
  - service: switch.turn_on
    target:
      # Byt ut mot din laddbox entitet för start/stopp (t.ex. switch.easee_is_enabled eller liknande strömbrytare)
      entity_id: switch.din_laddbox_car1

# ==========================================
# AUTOMATION 2: Starta laddbox (Bil 2)
# ==========================================
alias: "EV: Starta laddning Bil 2"
trigger:
  - platform: template
    value_template: >-
      {% set car_name = 'Min andra bil' %}  # Byt ut mot exakt det namn du gav bilen i integrationen
      {% set schedules = state_attr('sensor.optimizer_light_ev_schedule', 'schedules') %}
      {% if schedules and car_name in schedules and schedules[car_name]|length > 0 %}
        {% set start_time = as_timestamp(schedules[car_name][0]['start']) %}
        {{ now().timestamp() >= start_time }}
      {% else %}
        false
      {% endif %}
action:
  # 1. Ställ in laddboxens effekt
  - service: number.set_value
    target:
      # Byt ut mot entiteten för laddbox nummer 2
      entity_id: number.din_laddbox_effekt_car2
    data:
      value: >-
        {% set car_name = 'Min andra bil' %}
        {{ state_attr('sensor.optimizer_light_ev_schedule', 'schedules')[car_name][0]['charge_kw'] }}
  # 2. Slå på strömmen
  - service: switch.turn_on
    target:
      # Byt ut mot start-entiteten för laddbox nummer 2
      entity_id: switch.din_laddbox_car2
```

> [!IMPORTANT]
> **Automatiskt Pausat Husbatteri:** Se till att du har angett en sensor för "Bilen laddar" (t.ex. din laddbox effekt-mätare) i integrationens inställningar. När laddboxen börjar dra ström känner integrationen av det och signalerar till molnet. Detta säkerställer att ditt husbatteri automatiskt **pausas** och inte slösas bort på elbilen!

### 🚿 Smart Varmvattenoptimering (VVB Boost)

När integrationen körs skapas automatiskt två entiteter för smart varmvattenstyrning:
* `binary_sensor.battery_optimizer_water_heater_boost`: Slår om till `on` när optimeraren beordrar extra varmvattenuppvärmning (t.ex. vid billiga eltimmar eller vid solöverskott när hembatteriet är fulladdat).
* `sensor.battery_optimizer_water_heater_reason`: Visar den aktuella orsaken i klartext (t.ex. *"Solöverskott (1.4 kW) | Batteri 94%"*).

#### Styra din VVB / Värmepump:

Det finns två sätt att koppla din hårdvara:

* **Alternativ 1 (Enklast – Direkt i inställningarna):**
  Gå till *Inställningar -> Enheter och tjänster -> Battery Optimizer Light Plus -> Konfigurera*:
  - Välj din switch under **Varmvattenberedare / Plusvärme (Switch)**. Integrationen slår då automatiskt på och av switchen åt dig i realtid!
  - *(Valfritt)* Välj din temperatursensor under **Varmvattentemperatur Sensor**. Temperaturen skickas då till molnet så att boost spärras automatiskt om tanken når inställd maxtemperatur (t.ex. 65 °C).

* **Alternativ 2 (Via Automation):**
  Om du har avancerade villkor eller vill styra via scripts/klimatenheter kan du lämna switch-fältet tomt och istället skapa en vanlig Home Assistant-automation mot signalen `binary_sensor.battery_optimizer_water_heater_boost`:

#### 1. Automation: IVT / Värmepump (Plusvärme / SG Ready)
Koppla signalen till din värmepumps Plusvärme-switch eller SG Ready-ingång:

```yaml
alias: "🚿 IVT Plusvärme (Smart VVB)"
description: "Aktiverar Plusvärme på värmepumpen vid billig el eller solöverskott"
trigger:
  - platform: state
    entity_id: binary_sensor.battery_optimizer_water_heater_boost
condition: []
action:
  - if:
      - condition: state
        entity_id: binary_sensor.battery_optimizer_water_heater_boost
        state: "on"
    then:
      - service: switch.turn_on
        target:
          entity_id: switch.ivt_extra_varmvatten   # <-- Din IVT Plusvärme entity
    else:
      - service: switch.turn_off
        target:
          entity_id: switch.ivt_extra_varmvatten   # <-- Din IVT Plusvärme entity
mode: restart
```

#### 2. Automation: Extra VVB (Shelly-relä / Kontaktor)
Om du styr en elpatron eller extra beredare via ett Shelly-relä eller kontaktor:

```yaml
alias: "🚿 Extra VVB Kontaktor (Smart VVB)"
description: "Slår till elpatronen vid billig el eller solöverskott"
trigger:
  - platform: state
    entity_id: binary_sensor.battery_optimizer_water_heater_boost
condition: []
action:
  - if:
      - condition: state
        entity_id: binary_sensor.battery_optimizer_water_heater_boost
        state: "on"
    then:
      - service: switch.turn_on
        target:
          entity_id: switch.shelly_extra_vvb       # <-- Din Shelly-brytare
    else:
      - service: switch.turn_off
        target:
          entity_id: switch.shelly_extra_vvb       # <-- Din Shelly-brytare
mode: restart
```

#### 3. Dashboard-kort i Home Assistant (Exempel)
```yaml
type: entities
title: 🚿 Varmvattenoptimering
entities:
  - entity: binary_sensor.battery_optimizer_water_heater_boost
    name: VVB Boost Status
  - entity: sensor.battery_optimizer_water_heater_reason
    name: Orsak
  - entity: switch.extra_vvb
    name: Beredare / Plusvärme
```

---

## ℹ️ Sensorer & Övervakning

När systemet är igång skapas en mängd sensorer för att hjälpa dig övervaka optimeringen:

* ⚡ **`sensor.optimizer_light_action`**: Aktuellt molnbeslut (`CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`).
* 🎯 **`sensor.optimizer_light_charge_target`**: Önskad laddningseffekt i Watt (alltid ett positivt absolutbelopp).
* 🎯 **`sensor.optimizer_light_discharge_target`**: Önskad urladdningseffekt i Watt (alltid ett positivt absolutbelopp).
* 🛡️ **`sensor.optimizer_light_peakguard_status`**: Aktuell status för den lokala effektvakten (t.ex. `Monitoring`, `Triggered`, `Paused`, `Solar Override Active`).
* 🛑 **`sensor.optimizer_light_peak_limit`**: Den effektgräns (i Watt) som effektvakten just nu försvarar.
* 🏠 **`sensor.optimizer_light_virtual_load`**: Husets beräknade nettolast i realtid (W).
* 🏠 **`sensor.optimizer_light_house_consumption`**: Husets faktiska förbrukning (W) som skickas till molnet.
* 🚿 **`binary_sensor.battery_optimizer_water_heater_boost`**: Indikerar (`on`/`off`) om varmvattenberedare eller värmepumpens plusvärme ska aktiveras.
* ℹ️ **`sensor.battery_optimizer_water_heater_reason`**: Förklarande orsak till varför varmvattenberedaren körs eller pausas (t.ex. vid solöverskott eller billig el).
* 🔌 **`sensor.sonnen_grid_in_out`** *(Endast Sonnen)*: Visar det faktiska nätutbytet (Grid In/Out) i realtid (W). **Plus (+)** = Importerar (köper), **Minus (-)** = Exporterar (säljer).
* 🔋 **`sensor.*_battery_in_out`** *(Sonnen, Huawei & Homevolt)*: Batteriets effekt i realtid (W). Standard för Sonnen/Homevolt/Generic är att **Minus (-)** = Laddar. För Huawei är detta inverterat (se notis under Huawei-sektionen ovan).
* 📊 **`sensor.*_soc`** *(Sonnen, Huawei & Homevolt)*: Batteriets nuvarande laddningsnivå (%).
* 🛡️ **`sensor.*_sonnen_backup_reserv`** *(Endast Sonnen)*: Visar den inställda hårdvarureserven för strömavbrott (%). Sensorn är tillagd så du enkelt kan verifiera vilken reservnivå molnet och effektvakten tar hänsyn till i sina beräkningar.
* 💰 **`sensor.optimizer_light_daily_savings`**: Dagens totala besparing (SEK) beräknad utifrån batteriets historik.
* 🤖 **`sensor.optimizer_light_ai_summary`**: Daglig AI-genererad sammanfattning av batteriets prestanda. Hela texten sparas i sensorns attribut.
* 📉 **`sensor.battery_optimizer_graph_data`**: Innehåller all grafdata (historik och framtida prognos) dold i sina JSON-attribut (används för ApexCharts nedan).
* ⏭️ **`sensor.optimizer_light_next_action`**: Nästa kommande molnbeslut (t.ex. `CHARGE` eller `DISCHARGE`).
* 🕒 **`sensor.optimizer_light_next_action_time`**: Tiden då nästa beslut förväntas inträffa.
* 🚫 **`sensor.optimizer_light_dynamic_export_limit`**: Visar den dynamiska exportgränsen i kW (t.ex. `0.0` vid Zero Export, eller "Okänd"/"Unkown" om molnet inte begränsar). Statusen finns även tydligt utskriven i sensorns attribut.

---

## 🤖 Visa AI-Sammanfattningen i Dashboarden

Eftersom Home Assistant har en gräns på 255 tecken för vanliga sensorstatusar lagras den fullständiga AI-genererade texten säkert i sensorns *attribut*. För att läsa sammanfattningen bekvämt i din Dashboard rekommenderas att du använder ett inbyggt **Markdown-kort**.

Skapa ett nytt manuellt kort i din Dashboard och klistra in följande kod:

```yaml
type: markdown
title: 🤖 AI Sammanfattning
content: >
  {{ state_attr('sensor.optimizer_light_ai_summary', 'summary_text') }}
```

---

## 📅 Visa Nästa Planerade Åtgärd i Dashboarden

För att få en snygg textsträng som visar *nästa* planerade åtgärd (t.ex. "↳ Planerat: 🟢 CHARGE kl 14:00") kan du lägga till en egen mall-sensor (Template Sensor) i Home Assistant. 

Lägg till följande kod i din `configuration.yaml` (under `template:`):

```yaml
template:
  - sensor:
      - name: "Battery Optimizer Next Action"
        icon: mdi:calendar-arrow-right
        state: >
          {% set action = states('sensor.optimizer_light_plus_next_action') %}
          {% set time_str = states('sensor.optimizer_light_plus_next_action_time') %}
          
          {% if action and time_str and action not in ['None', 'unknown', 'unavailable', 'UNKNOWN'] and time_str not in ['None', 'unknown', 'unavailable'] %}
            {% set dt = time_str | as_datetime | as_local %}
            {% if dt %}
              {% set icon = '⚪' %}
              {% if action == 'CHARGE' %}{% set icon = '🟢' %}{% endif %}
              {% if action == 'DISCHARGE' %}{% set icon = '🔴' %}{% endif %}
              {% if action == 'HOLD' %}{% set icon = '🟠' %}{% endif %}
              
              {% set today = now().date() %}
              {% if dt.date() == today %}
                ↳ Planerat: {{ icon }} {{ action }} kl {{ dt.strftime('%H:%M') }}
              {% else %}
                ↳ Planerat: {{ icon }} {{ action }} kl {{ dt.strftime('%d/%m %H:%M') }}
              {% endif %}
            {% else %}
              ↳ Planerat: Avvaktar (Tidfel)
            {% endif %}
          {% else %}
            ↳ Planerat: Avvaktar
          {% endif %}
```

Gå sedan till **Utvecklarverktyg (Developer Tools)** -> **YAML** och klicka på **Ladda om Mallentiteter (Template Entities)**. Därefter har du en ny sensor `sensor.battery_optimizer_next_action` som du enkelt kan visa i ett standard entitetskort på din Dashboard!

---

## 📈 ApexCharts Exempel (Dashboard)

Med hjälp av komponenten ApexCharts Card (installeras via HACS) kan du bygga upp en komplett översikt för ditt batteri. Nedan finns tre exempel på grafer.

Skapa ett "Manuell" (Custom) kort för varje kodblock nedan i din Dashboard:

### 1. Pris & Beslut

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Pris & Beslut
graph_span: 3d    # Works well with history = 48h
span:
  start: day
  offset: "-24h"
now:
  show: true
  label: Nu
  color: white
stacked: false
apex_config:
  plotOptions:
    bar:
      columnWidth: 100%
  tooltip:
    x:
      format: dd MMM HH:mm
yaxis:
  - min: 0
    decimals: 2
    apex_config:
      title:
        text: SEK
series:
  - entity: sensor.battery_optimizer_graph_data
    name: CHARGE
    type: column
    unit: " SEK"
    color: "#4CAF50"
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hist = (api.history || []).filter(x => x.action === 'CHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        const fore = (api.forecast || []).filter(x => x.action === 'CHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        return hist.concat(fore);
      });
  - entity: sensor.battery_optimizer_graph_data
    name: DISCHARGE
    type: column
    unit: " SEK"
    color: "#F44336"
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hist = (api.history || []).filter(x => x.action === 'DISCHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        const fore = (api.forecast || []).filter(x => x.action === 'DISCHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        return hist.concat(fore);
      });
  - entity: sensor.battery_optimizer_graph_data
    name: HOLD
    type: column
    unit: " SEK"
    color: "#FF9800"
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hist = (api.history || []).filter(x => x.action === 'HOLD').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        const fore = (api.forecast || []).filter(x => x.action === 'HOLD').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        return hist.concat(fore);
      });
  - entity: sensor.battery_optimizer_graph_data
    name: IDLE
    type: column
    unit: " SEK"
    color: "#9E9E9E"
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hist = (api.history || []).filter(x => x.action === 'IDLE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        const fore = (api.forecast || []).filter(x => x.action === 'IDLE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);
        return hist.concat(fore);
      });

```

### 2. Batterinivå (SoC) & Effekt

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Batterinivå (SoC) & Effekt
graph_span: 3d    # Works well with history = 48h
span:
  start: day
  offset: "-24h"
now:
  show: true
  label: Nu
  color: white
yaxis:
  - id: soc
    min: 0
    max: 100
    decimals: 0
    apex_config:
      title:
        text: "%"
  - id: power
    opposite: true
    min: 0
    decimals: 1
    apex_config:
      title:
        text: kW
series:
  - entity: sensor.battery_optimizer_graph_data
    name: SoC (Historik)
    unit: " %"
    type: line
    yaxis_id: soc
    color: "#FFFFFF"
    stroke_width: 2
    extend_to: false
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const now = new Date().getTime();
        return (api.history || []).filter(x => new Date(x.timestamp).getTime() <= now).map(x => {
          let soc = x.reported_soc;
          if (soc > 90 && x.reason && x.reason.includes('Tomt')) soc = 0;
          return [new Date(x.timestamp).getTime(), soc];
        });
      });
  - entity: sensor.battery_optimizer_graph_data
    name: SoC (Prognos)
    unit: " %"
    type: line
    yaxis_id: soc
    color: "#00BCD4"
    stroke_width: 2
    extend_to: false
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const fore = (api.forecast || []).map(x => [new Date(x.timestamp).getTime(), x.simulated_soc]);
        const hist = api.history || [];
        if (hist.length > 0 && fore.length > 0) {
          fore.unshift([new Date(hist[hist.length - 1].timestamp).getTime(), hist[hist.length - 1].reported_soc]);
        }
        return fore;
      });
  - entity: sensor.battery_optimizer_graph_data
    name: Sol (Historik)
    unit: " kW"
    type: area
    yaxis_id: power
    color: "#FFD700"
    opacity: 0.2
    stroke_width: 1
    extend_to: false
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const now = new Date().getTime();
        return (api.history || []).filter(x => x.solar_kw !== undefined && new Date(x.timestamp).getTime() <= now).map(x => [new Date(x.timestamp).getTime(), x.solar_kw]);
      });
  - entity: sensor.battery_optimizer_graph_data
    name: Sol (Prognos)
    unit: " kW"
    type: area
    yaxis_id: power
    color: "#FFD700"
    opacity: 0.2
    stroke_width: 1
    extend_to: false
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const fore = (api.forecast || []).map(x => [new Date(x.timestamp).getTime(), x.solar_kw]);
        const hist = (api.history || []).filter(x => x.current_solar_kw !== undefined);
        if (hist.length > 0 && fore.length > 0) {
          fore.unshift([new Date(hist[hist.length - 1].timestamp).getTime(), hist[hist.length - 1].current_solar_kw]);
        }
        return fore;
      });
  - entity: sensor.battery_optimizer_graph_data
    name: Husförbrukning (Baslast)
    unit: " kW"
    type: line
    yaxis_id: power
    color: "#FF5722"
    stroke_width: 2
    extend_to: false
    show:
      legend_value: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hist = (api.history || []).filter(x => x.house_base_load_kw !== undefined).map(x => [new Date(x.timestamp).getTime(), x.house_base_load_kw]);
        const fore = (api.forecast || []).filter(x => x.base_load_kw !== undefined).map(x => [new Date(x.timestamp).getTime(), x.base_load_kw]);
        return hist.concat(fore);
      });
```

### 3. Besparingar senaste 24h

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Besparingar senaste 24h
graph_span: 2d    # Works well with history = 48h
span:
  start: day
  offset: "-24h"
yaxis:
  - id: bar
    decimals: 2
    apex_config:
      title:
        text: SEK
apex_config:
  plotOptions:
    bar:
      columnWidth: 100%
      colors:
        ranges:
          - from: -100000
            to: -0.001
            color: "#FFC107"
          - from: 0
            to: 100000
            color: "#4CAF50"
series:
  - entity: sensor.battery_optimizer_graph_data
    name: Besparing (1h)
    type: column
    unit: " SEK"
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        const hourly = {};
        const now = new Date().getTime();
        (api.history || []).forEach(x => {
          const ts = new Date(x.timestamp).getTime();
          if (ts > now || typeof x.savings_sek !== 'number') return;
          const dt = new Date(ts);
          dt.setMinutes(0, 0, 0);
          const key = dt.getTime();
          hourly[key] = (hourly[key] || 0) + x.savings_sek;
        });
        const expandedData = [];
        Object.entries(hourly).forEach(([ts, val]) => {
          if (Math.abs(val) > 0.01) {
            for (let i = 0; i < 11; i++) {
              expandedData.push([Number(ts) + i * 5 * 60 * 1000, val]);
            }
          }
        });
        return expandedData.sort((a, b) => a[0] - b[0]);
      });
  - entity: sensor.battery_optimizer_graph_data
    name: Ackumulerat Totalt
    unit: " SEK"
    type: line
    color: "#00BCD4"
    stroke_width: 3
    extend_to: false
    data_generator: >
      const ha = document.querySelector('home-assistant') || document.querySelector('hc-main');
      const hassObj = (typeof hass !== 'undefined' && hass) || (ha && ha.hass);
      const token = hassObj && hassObj.auth && hassObj.auth.data ? hassObj.auth.data.access_token : '';
      return fetch('/api/battery_optimizer_graph_data', { headers: token ? { 'Authorization': 'Bearer ' + token } : {} }).then(r => r.json()).then(d => {
        const api = Object.values(d)[0] || {};
        let sum = 0;
        const now = new Date().getTime();
        const start = new Date();
        start.setHours(0, 0, 0, 0);
        start.setDate(start.getDate() - 1);
        const startTime = start.getTime();
        const filtered = (api.history || []).filter(x => {
          const ts = new Date(x.timestamp).getTime();
          return ts >= startTime && ts <= now && typeof x.savings_sek === 'number';
        });
        const data = filtered.map(x => {
          sum += (x.savings_sek || 0);
          return [new Date(x.timestamp).getTime(), sum];
        });
        data.unshift([startTime, 0]); // Garanterar att linjen börjar exakt på 0 vid t=0
        return data;
      });
```

---

## 🐞 Felsökning (Debug)

Om du upplever problem eller vill se exakt vilken data som skickas till och från molnet, kan du aktivera detaljerad debug-loggning. Lägg till följande i din `configuration.yaml` och starta om Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.battery_optimizer_light_plus: debug
```

Gå sedan till **Inställningar** -> **System** -> **Loggar** i Home Assistant för att se detaljerade händelser, felmeddelanden och nätverkstrafik (sök t.ex. på `Light-Request` för att se payloaden som skickas).

## 🤖 Automationer för Generic / Övriga batterier

> [!TIP]
> Om du vill ha en mer detaljerad steg-för-steg-instruktion kring hur du förbereder sensorerna och bygger upp Generic-stödet, kika i den dedikerade guiden: **[`docs/GENERIC_BATTERY_SETUP.md`](docs/GENERIC_BATTERY_SETUP.md)**.

Om du har valt **Generic / Light** vid installationen styrs inte din växelriktare automatiskt av integrationen. Istället lyssnar integrationen på molnet och exponerar optimeringsbesluten via sensorer. 

För att faktiskt styra ditt batteri behöver du bygga en egen automation i Home Assistant (t.ex. i `automations.yaml`) som lyssnar på dessa sensorer och skickar rätt kommandon till just din växelriktare.

Kopiera nedanstående exempel och anpassa `action` (t.ex. `script.din_inverter_charge`) så att de matchar de tjänster och skript du använder för din specifika anläggning.

### Exempel: Huvudstyrenhet (Utför Beslut)
Lyssnar på ändringar från molnets besluts-sensor (`sensor.optimizer_light_action`) och styr batteriet. Notera att värdena för laddning och urladdning redan är konverterade till Watt (W) av integrationen och **alltid är positiva absolutbelopp** (du behöver alltså inte hantera minustecken i dina egna skript).

```yaml
alias: 🔋 Battery Optimizer Light - Manuell Styrning (Generic)
description: Styr batteriet via egna skript baserat på optimerarens beslut.
mode: single
triggers:
  - trigger: state
    entity_id: sensor.optimizer_light_action
conditions:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.optimizer_light_action
        state:
          - unknown
          - unavailable
actions:
  - variables:
      current_action: "{{ states('sensor.optimizer_light_action') }}"
      charge_target: "{{ states('sensor.optimizer_light_charge_target') | int(0) }}"
      discharge_target: "{{ states('sensor.optimizer_light_discharge_target') | int(0) }}"
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'CHARGE' }}"
        sequence:
          - action: script.din_inverter_charge # BYT UT MOT DITT EGET SKRIPT/TJÄNST
            data:
              power: "{{ charge_target }}"
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'DISCHARGE' }}"
        sequence:
          - action: script.din_inverter_discharge # BYT UT MOT DITT EGET SKRIPT/TJÄNST
            data:
              power: "{{ discharge_target }}"
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'HOLD' }}"
        sequence:
          - action: script.din_inverter_hold # BYT UT MOT DITT EGET SKRIPT/TJÄNST
            data: {}
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'IDLE' }}"
        sequence:
          - action: script.din_inverter_auto # BYT UT MOT DITT EGET SKRIPT/TJÄNST
            data: {}
    default:
      - action: script.din_inverter_auto # BYT UT MOT DITT EGET SKRIPT/TJÄNST
        data: {}
```

### Exempel: Tillhörande Skript (scripts.yaml)
Eftersom alla växelriktare styrs olika (Fronius, Sungrow, GoodWe etc.) måste du anpassa innehållet i dessa skript så att de gör exakt det som krävs för din anläggning. Ofta handlar det om att sätta ett `number`-värde för effekten och ändra ett driftläge via en `select`-entitet eller via ett Modbus-kommando. 

Se till att skript-ID:na (`din_inverter_auto` osv) matchar de du anropar i automationen ovan. Här är ett konkret exempel på hur skripten i din `scripts.yaml` kan se ut:

```yaml
din_inverter_auto:
  alias: "Batteri: Autoläge"
  sequence:
    # Exempel: Byt ut mot din egen entitet för att återgå till självkonsumtion (Auto)
    - action: select.select_option
      target:
        entity_id: select.inverter_mode
      data:
        option: "Auto"

din_inverter_charge:
  alias: "Batteri: Tvinga Laddning"
  fields:
    power:
      description: Effekt i Watt
      default: 0
  sequence:
    # Exempel: 1. Sätt växelriktaren i manuellt laddningsläge
    - action: select.select_option
      target:
        entity_id: select.inverter_mode
      data:
        option: "Manual Charge"
    # Exempel: 2. Bestäm effekten i Watt (skickas in automatiskt via automationen)
    - action: number.set_value
      target:
        entity_id: number.inverter_charge_power
      data:
        value: "{{ power }}"

din_inverter_discharge:
  alias: "Batteri: Tvinga Urladdning"
  fields:
    power:
      description: Effekt i Watt
      default: 0
  sequence:
    - action: select.select_option
      target:
        entity_id: select.inverter_mode
      data:
        option: "Manual Discharge"
    - action: number.set_value
      target:
        entity_id: number.inverter_discharge_power
      data:
        value: "{{ power }}"

din_inverter_hold:
  alias: "Batteri: Pausa (Hold)"
  sequence:
    # Ofta pausas ett batteri genom att man aktiverar ett manuellt läge, men sätter maxeffekten till 0 W
    - action: select.select_option
      target:
        entity_id: select.inverter_mode
      data:
        option: "Manual Discharge"
    - action: number.set_value
      target:
        entity_id: number.inverter_discharge_power
      data:
        value: 0

```

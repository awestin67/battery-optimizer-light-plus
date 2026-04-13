# 🔋 Battery Optimizer Light Plus

<img src="https://raw.githubusercontent.com/awestin67/battery-optimizer-light-plus/main/custom_components/battery_optimizer_light_plus/brand/logo.png" alt="Logo" width="200"/>

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate and Test](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml/badge.svg)](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**Battery Optimizer Light Plus** är en lättviktig hybridlösning som kopplar din Home Assistant till en smart molntjänst för hembatterier.

Systemet kombinerar **Molnintelligens** (för prisoptimering och arbitrage) med **Lokal Kraft** (för blixtsnabb effektvakt/peak shaving direkt i Home Assistant). Allt är nu samlat i **en enda integration** där du enkelt väljer din batterityp vid installationen.

---

## ✨ Funktioner

* **📈 Prisoptimering (Arbitrage):** Laddar när elen är billig och säljer/laddar ur när den är dyr baserat på spotpriser och prognoser.
* **🛡️ Smart Effektvakt (Peak Shaving):** Övervakar husets nettolast i realtid för att kapa effekttoppar lokalt.
    * *Molnstyrning:* Effektvakten kan dynamiskt pausas eller justeras från molnet.
    * *Hysteres:* Inbyggd smart logik förhindrar "fladder" när lasten pendlar runt gränsvärdet.
* **🤖 Zero-Config Automation:** Integrationen lyssnar automatiskt på beslut från molnet och styr ditt batteri. Inga krångliga YAML-skript krävs!
* **📊 Analys:** Följ dina besparingar och effekttoppar via vår snygga [Web Dashboard](https://battery-prod.awestinconsulting.se).

---

## 🔌 Stödda Batterier & Krav

### ☀️ Sonnen
Kräver ett Sonnen-batteri med **API v2** aktiverat.
*   **Auth-Token:** Du behöver ditt Auth-Token för lokal styrning. Logga in på ditt batteri (`http://<IP-ADRESS>/dash/login`) som *User*, välj **Software integration**, slå på **JSON API** (Read & Write) och kopiera ditt Auth-Token.

### 🌑 Huawei Luna2000
Styr Huawei-batterier via den officiella Home Assistant-integrationen.
*   **Krav:** En fungerande, förkonfigurerad installation av den officiella `Huawei Solar`-integrationen.
*   **Notera:** För Huawei inverteras batterisensorn automatiskt så att **Plus (+)** betyder att batteriet **laddar** och **Minus (-)** betyder att det **laddar ur**, vilket matchar standardbeteendet för Huawei Solar-integrationen.

### ⚡ Homevolt
Styr Homevolt-batterier lokalt via Home Assistant.
*   **Krav:** Integrationen Homevolt Local (finns att ladda ner via HACS) måste vara installerad och konfigurerad först.
*   **Notera:** Integrationen stöder *Auto-Discovery* och hittar automatiskt dina sensorer för SoC, Batteri, Nät och Huslast vid installationen!

### 🔌 Solis Modbus
Styr Solis-batterier lokalt via Pho3niX90's Solis Modbus-integration.
*   **Krav:** En fungerande, förkonfigurerad installation av Solis Modbus (HACS).
*   **Kompatibilitet:** Byggd och optimerad primärt för **Solis S6 Hybrid** (EH-modeller).
*   **Notera:** Integrationen stöder *Auto-Discovery* och letar automatiskt upp dina mät- och styrentiteter vid installationen. Den använder växelriktarens "Remote Control" (RC) register för tillförlitlig lokal styrning.

### ☁️ Generic / Light
För dig som bara vill hämta optimeringsbeslut och räkna ut last lokalt, men sedan styra ditt batteri manuellt via egna automationsflöden.

---

##  Installation

### Via HACS (Rekommenderas)
1. Se till att HACS är installerat.
2. Gå till **HACS** -> **Integrationer**.
3. Klicka på de tre prickarna uppe till höger och välj **Anpassade arkiv (Custom repositories)**.
4. Lägg till URL: `https://github.com/awestin67/battery-optimizer-light-plus` och välj kategori **Integration**.
5. Ladda ner "Battery Optimizer Light Plus" och starta om Home Assistant.

### Konfiguration
1. Gå till **Inställningar** -> **Enheter & Tjänster**.
2. Klicka på **Lägg till integration** och sök efter **Battery Optimizer Light Plus**.
3. Följ guiden:
    * **Steg 1:** Välj vilken typ av batteri du har (Sonnen, Huawei, Homevolt, Solis Modbus, Generic).
    * **Steg 2:** Fyll i batterispecifika uppgifter (t.ex. IP och API-token för Sonnen, eller enheter för Huawei).
    * **Steg 3:** Fyll i din API-nyckel från Dashboarden. Om du valt Sonnen, Huawei, Homevolt eller Solis hanteras de flesta mätvärden automatiskt, men för Generic (eller för anpassade behov) kan du behöva peka ut sensorer för nätutbyte och batteri manuellt.

---

## 🤖 Användning & Automation

### Automatisk Styrning (Zero-Config)
Integrationen är skapad för att fungera direkt ur lådan. Den lyssnar automatiskt på beslut från molnet och styr ditt batteri utan att du behöver bygga några egna skript eller automationer!

### Manuell Styrning (För avancerade användare)
Om du föredrar att bygga egna automationsflöden i Home Assistant eller Node-RED, kan du stänga av den automatiska styrningen via integrationens inställningar (Konfigurera -> Avmarkera *Enable automatic control*).

Följande tjänster finns då tillgängliga för dig att anropa (ersätter gamla `rest_commands`):

*   `battery_optimizer_light_plus.force_charge`: Tvingar batteriet att ladda med en specifik effekt (W).
*   `battery_optimizer_light_plus.force_discharge`: Tvingar batteriet att ladda ur med en specifik effekt (W).
*   `battery_optimizer_light_plus.hold`: Sätter batteriet i vänteläge/paus.
*   `battery_optimizer_light_plus.auto`: Återställer batteriet till automatiskt driftläge.

---

## ℹ️ Sensorer & Övervakning

När systemet är igång skapas en mängd sensorer för att hjälpa dig övervaka optimeringen:

* ⚡ **`sensor.optimizer_light_action`**: Aktuellt molnbeslut (`CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`).
* 🎯 **`sensor.optimizer_light_charge_target`**: Önskad laddningseffekt i Watt.
* 🎯 **`sensor.optimizer_light_discharge_target`**: Önskad urladdningseffekt i Watt.
* 🛡️ **`sensor.optimizer_light_peakguard_status`**: Aktuell status för den lokala effektvakten (t.ex. `Monitoring`, `Triggered`, `Paused`, `Solar Override Active`).
* 🛑 **`sensor.optimizer_light_peak_limit`**: Den effektgräns (i Watt) som effektvakten just nu försvarar.
* 🏠 **`sensor.optimizer_light_virtual_load`**: Husets beräknade nettolast i realtid (W).
* 🏠 **`sensor.optimizer_light_house_consumption`**: Husets faktiska förbrukning (W) som skickas till molnet.
* 🔌 **`sensor.sonnen_grid_in_out`** *(Endast Sonnen)*: Visar det faktiska nätutbytet (Grid In/Out) i realtid (W). **Plus (+)** = Importerar (köper), **Minus (-)** = Exporterar (säljer).
* 🔋 **`sensor.*_battery_in_out`** *(Sonnen, Huawei & Homevolt)*: Batteriets effekt i realtid (W). Standard för Sonnen/Homevolt/Generic är att **Minus (-)** = Laddar. För Huawei är detta inverterat (se notis under Huawei-sektionen ovan).
* 📊 **`sensor.*_soc`** *(Sonnen, Huawei & Homevolt)*: Batteriets nuvarande laddningsnivå (%).
* 💰 **`sensor.optimizer_light_daily_savings`**: Dagens totala besparing (SEK) beräknad utifrån batteriets historik.
* 📉 **`sensor.battery_optimizer_graph_data`**: Innehåller all grafdata (historik och framtida prognos) dold i sina JSON-attribut (används för ApexCharts nedan).

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
graph_span: 48h
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
series:
  - entity: sensor.battery_optimizer_graph_data
    name: CHARGE
    type: column
    color: "#4CAF50"
    data_generator: |
      const hist = entity.attributes.history.filter(x => x.action ===
      'CHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      const fore = entity.attributes.forecast.filter(x => x.action ===
      'CHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      return hist.concat(fore);
  - entity: sensor.battery_optimizer_graph_data
    name: DISCHARGE
    type: column
    color: "#F44336"
    data_generator: |
      const hist = entity.attributes.history.filter(x => x.action ===
      'DISCHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      const fore = entity.attributes.forecast.filter(x => x.action ===
      'DISCHARGE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      return hist.concat(fore);
  - entity: sensor.battery_optimizer_graph_data
    name: HOLD
    type: column
    color: "#FF9800"
    data_generator: |
      const hist = entity.attributes.history.filter(x => x.action ===
      'HOLD').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      const fore = entity.attributes.forecast.filter(x => x.action ===
      'HOLD').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      return hist.concat(fore);
  - entity: sensor.battery_optimizer_graph_data
    name: IDLE
    type: column
    color: "#9E9E9E"
    data_generator: |
      const hist = entity.attributes.history.filter(x => x.action ===
      'IDLE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      const fore = entity.attributes.forecast.filter(x => x.action ===
      'IDLE').map(x => [new Date(x.timestamp).getTime(), x.price_sek]);

      return hist.concat(fore);
```

### 2. Batterinivå (SoC) & Effekt

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Batterinivå (SoC) & Effekt
graph_span: 48h
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
  - id: power
    opposite: true
    min: 0
    decimals: 1
series:
  - entity: sensor.battery_optimizer_graph_data
    name: SoC (Historik)
    type: line
    yaxis_id: soc
    color: "#FFFFFF"
    stroke_width: 2
    data_generator: |
      return entity.attributes.history.map(x => [new
      Date(x.timestamp).getTime(), x.reported_soc]);
  - entity: sensor.battery_optimizer_graph_data
    name: SoC (Prognos)
    type: line
    yaxis_id: soc
    color: "#00BCD4"
    stroke_width: 2
    data_generator: |
      return entity.attributes.forecast.map(x => [new
      Date(x.timestamp).getTime(), x.simulated_soc]);
  - entity: sensor.battery_optimizer_graph_data
    name: Sol (Prognos)
    type: area
    yaxis_id: power
    color: "#FFD700"
    opacity: 0.2
    stroke_width: 1
    data_generator: |
      return entity.attributes.forecast.map(x => [new
      Date(x.timestamp).getTime(), x.solar_kw]);
  - entity: sensor.battery_optimizer_graph_data
    name: Husförbrukning (Baslast)
    type: line
    yaxis_id: power
    color: "#FF5722"
    stroke_width: 2
    data_generator: |
      const hist = entity.attributes.history.filter(x => x.house_base_load_kw
      !== undefined).map(x => [new Date(x.timestamp).getTime(),
      x.house_base_load_kw]);

      const fore = entity.attributes.forecast.filter(x => x.base_load_kw !==
      undefined).map(x => [new Date(x.timestamp).getTime(), x.base_load_kw]);

      return hist.concat(fore);
```

### 3. Besparingar senaste 24h

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Besparingar senaste 24h
graph_span: 48h
span:
  start: day
  offset: "-24h"
yaxis:
  - id: bar
    decimals: 2
  - id: line
    opposite: true
    decimals: 1
series:
  - entity: sensor.battery_optimizer_graph_data
    name: Händelse (5 min)
    type: column
    yaxis_id: bar
    color_threshold:
      - value: -100
        color: "#D32F2F"
      - value: 0
        color: "#4CAF50"
    data_generator: |
      return entity.attributes.history.filter(x => x.savings_sek !== 0).map(x =>
      [new Date(x.timestamp).getTime(), x.savings_sek]);
  - entity: sensor.battery_optimizer_graph_data
    name: Ackumulerat Totalt
    type: line
    yaxis_id: line
    color: "#00BCD4"
    stroke_width: 3
    data_generator: |
      let sum = 0;
      return entity.attributes.history.map(x => {
        sum += (x.savings_sek || 0);
        return [new Date(x.timestamp).getTime(), sum];
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

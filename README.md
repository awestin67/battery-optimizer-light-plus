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

## 📈 ApexCharts Exempel (Batteri- & Prisprognos)

Med hjälp av komponenten ApexCharts Card (installeras via HACS) kan du smidigt rita upp en graf som kombinerar både **historik** och **framtida prognos** för ditt batteri i samma vy.

Skapa ett "Manuell" (Custom) kort i din Dashboard och klistra in följande kod:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: 🔋 Batteri- & Prisprognos
  show_states: false
graph_span: 48h
update_interval: 5m
span:
  start: day
  offset: -12h # Justera hur långt bakåt grafen ska börja ritas från början av dagen
now:
  show: true
  label: Nu
  color: red
yaxis:
  - id: soc
    min: 0
    max: 100
    decimals: 0
    apex_config:
      title:
        text: SoC (%)
  - id: sek
    opposite: true
    decimals: 2
    apex_config:
      title:
        text: SEK (Pris & Besparing)
series:
  # 1. Historik SoC (Vänster axel)
  - entity: sensor.battery_optimizer_graph_data
    name: Historik SoC
    type: area
    curve: smooth
    color: "#03a9f4"
    opacity: 0.3
    yaxis_id: soc
    data_generator: |
      if (!entity.attributes.history) return [];
      return entity.attributes.history.map((entry) => {
        return [new Date(entry.timestamp).getTime(), entry.reported_soc];
      });
      
  # 2. Prognos SoC (Vänster axel)
  - entity: sensor.battery_optimizer_graph_data
    name: Prognos SoC
    type: line
    curve: smooth
    color: "#03a9f4"
    stroke_width: 2
    extend_to: false
    yaxis_id: soc
    data_generator: |
      if (!entity.attributes.forecast) return [];
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.timestamp).getTime(), entry.soc]; 
      });

  # 3. Elpris Prognos (Höger axel)
  - entity: sensor.battery_optimizer_graph_data
    name: Elpris Prognos
    type: line
    curve: stepline
    color: "#ff9800"
    yaxis_id: sek
    data_generator: |
      if (!entity.attributes.forecast) return [];
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.timestamp).getTime(), entry.price_sek];
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

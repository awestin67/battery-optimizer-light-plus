# 🔋 Battery Optimizer Light

<img src="https://raw.githubusercontent.com/awestin67/battery-optimizer-light-base/main/custom_components/battery_optimizer_light_base/logo.png" alt="Logo" width="200"/>

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate and Test](https://github.com/awestin67/battery-optimizer-light-base/actions/workflows/run_tests.yml/badge.svg)](https://github.com/awestin67/battery-optimizer-light-base/actions/workflows/run_tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**Battery Optimizer Light** är en lättviktig hybridlösning som kopplar din Home Assistant till en smart molntjänst för hembatterier.

Systemet kombinerar **Molnintelligens** (för prisoptimering och arbitrage) med **Lokal Kraft** (för blixtsnabb effektvakt/peak shaving direkt i Home Assistant). Allt är nu samlat i **en enda integration** där du enkelt väljer din batterityp vid installationen.

---

## ✨ Funktioner

* **📈 Prisoptimering (Arbitrage):** Laddar när elen är billig och säljer/laddar ur när den är dyr baserat på spotpriser och prognoser.
* **🛡️ Smart Effektvakt (Peak Shaving):** Övervakar husets nettolast i realtid för att kapa effekttoppar lokalt.
    * *Molnstyrning:* Effektvakten kan dynamiskt pausas eller justeras från molnet.
    * *Hysteres:* Inbyggd smart logik förhindrar "fladder" när lasten pendlar runt gränsvärdet.
* **⛄ Vinterbuffert:** Reserverar en anpassningsbar procentandel av ditt batteri som *aldrig* säljs, redo för nödbehov.
* **🤖 Zero-Config Automation:** Integrationen lyssnar automatiskt på beslut från molnet och styr ditt batteri. Inga krångliga YAML-skript krävs!
* **📊 Analys:** Följ dina besparingar och effekttoppar via vår snygga [Web Dashboard](https://battery-prod.awestinconsulting.se).

---

## 🔌 Stödda Batterier & Krav

### ☀️ Sonnen
Kräver ett Sonnen-batteri med **API v2** aktiverat.
*   **Auth-Token:** Du behöver ditt Auth-Token för lokal styrning. Logga in på ditt batteri (`http://<IP-ADRESS>/dash/login`) som *User*, välj **Software integration**, slå på **JSON API** (Read & Write) och kopiera ditt Auth-Token.

### 🌑 Huawei Luna2000
Styr Huawei-batterier via den officiella Home Assistant-integrationen.
*   **Krav:** En fungerande, förkonfigurerad installation av den officiella `Huawei Solar`-integrationen. Du behöver peka ut entiteten för *Working Mode* under konfigurationen.

### ☁️ Generic / Light
För dig som bara vill hämta optimeringsbeslut och räkna ut last lokalt, men sedan styra ditt batteri manuellt via egna automationsflöden.

---

##  Installation

### Via HACS (Rekommenderas)
1. Se till att HACS är installerat.
2. Gå till **HACS** -> **Integrationer**.
3. Klicka på de tre prickarna uppe till höger och välj **Anpassade arkiv (Custom repositories)**.
4. Lägg till URL: `https://github.com/awestin67/battery-optimizer-light-base` och välj kategori **Integration**.
5. Ladda ner "Battery Optimizer Light" och starta om Home Assistant.

### Konfiguration
1. Gå till **Inställningar** -> **Enheter & Tjänster**.
2. Klicka på **Lägg till integration** och sök efter **Battery Optimizer Light**.
3. Följ guiden:
    * **Steg 1:** Välj vilken typ av batteri du har (Sonnen, Huawei, Generic).
    * **Steg 2:** Fyll i batterispecifika uppgifter (t.ex. IP och API-token för Sonnen, eller enheter för Huawei).
    * **Steg 3:** Fyll i din API-nyckel från Dashboarden och peka ut dina huvudsakliga mät-sensorer (Grid, Batteri SoC, etc.).

---

## 🤖 Användning & Automation

### Automatisk Styrning (Zero-Config)
Integrationen är skapad för att fungera direkt ur lådan. Den sätter automatiskt upp en bakgrundslyssnare som agerar på besluten från molnet och styr ditt batteri – du behöver **inte** bygga några egna skript eller automationer!

### Manuell Styrning (För avancerade användare)
Om du föredrar att bygga egna automationsflöden i Home Assistant eller Node-RED, kan du stänga av den automatiska styrningen via integrationens inställningar (Konfigurera -> Avmarkera *Enable automatic control*).

Följande tjänster finns då tillgängliga för dig att anropa (ersätter gamla `rest_commands`):

*   `battery_optimizer_light_base.force_charge`: Tvingar batteriet att ladda med en specifik effekt (W).
*   `battery_optimizer_light_base.force_discharge`: Tvingar batteriet att ladda ur med en specifik effekt (W).
*   `battery_optimizer_light_base.hold`: Sätter batteriet i vänteläge/paus.
*   `battery_optimizer_light_base.auto`: Återställer batteriet till automatiskt driftläge.

---

## ℹ️ Sensorer & Övervakning

När systemet är igång skapas en mängd sensorer för att hjälpa dig övervaka optimeringen:

* ⚡ **`sensor.optimizer_light_action`**: Aktuellt molnbeslut (`CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`).
* 🎯 **`sensor.optimizer_light_charge_target`**: Önskad laddningseffekt i Watt.
* 🎯 **`sensor.optimizer_light_discharge_target`**: Önskad urladdningseffekt i Watt.
* 🛡️ **`sensor.optimizer_light_peakguard_status`**: Aktuell status för den lokala effektvakten (t.ex. `Monitoring`, `Triggered`, `Paused`, `Solar Override Active`).
* 🛑 **`sensor.optimizer_light_peak_limit`**: Den effektgräns (i Watt) som effektvakten just nu försvarar.
* 🏠 **`sensor.optimizer_light_virtual_load`**: Husets beräknade nettolast i realtid (W).

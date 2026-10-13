# 🔋 Battery Optimizer Light Plus

<img src="https://raw.githubusercontent.com/awestin67/battery-optimizer-light-plus/main/custom_components/battery_optimizer_light_plus/brand/logo.png" alt="Logo" width="200"/>

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate and Test](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml/badge.svg)](https://github.com/awestin67/battery-optimizer-light-plus/actions/workflows/run_tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=awestin67&repository=battery-optimizer-light-plus&category=integration)

**Battery Optimizer Light Plus** är en lättviktig hybridlösning som kopplar din Home Assistant till en smart molntjänst för hembatterier.

Systemet kombinerar **Molnintelligens** (prisoptimering och arbitrage) med **Lokal Kraft** (blixtsnabb effektvakt/peak shaving direkt i Home Assistant). Allt är samlat i **en enda integration** där du väljer din batterityp vid installationen.

**Innehåll:** [Funktioner](#funktioner) · [Stödda batterier](#stodda-batterier) · [Installation](#installation) · [Sensorer](#sensorer) · [Felsökning](#felsokning) · [Guider](#guider)

---

<a id="funktioner"></a>
## ✨ Funktioner

| Funktion | Beskrivning |
| :--- | :--- |
| 📈 **Prisoptimering (Arbitrage)** | Laddar när elen är billig och säljer/laddar ur när den är dyr, baserat på spotpriser och prognoser. |
| 🛡️ **Smart Effektvakt (Peak Shaving)** | Övervakar husets nettolast i realtid och kapar effekttoppar lokalt. Kan pausas eller justeras från molnet och har inbyggd hysteres mot "fladder". |
| 🤖 **Zero-Config Automation** | Integrationen lyssnar på molnets beslut och styr batteriet själv. Inga YAML-skript eller automationer krävs. |
| 📊 **Analys** | Följ besparingar och effekttoppar i [Web Dashboard](https://battery-prod.awestinconsulting.se). |
| 🚫 **Zero Export** | Tar emot en dynamisk exportgräns (kW) från molnet så att du inte förlorar pengar på att sälja solel vid negativa priser. För AC-kopplade solceller (t.ex. SolarEdge) finns [Blueprint och guide](docs/SOLAREDGE_ZERO_EXPORT_GUIDE.md). |
| 🚗 **Smart elbilsladdning** | Skyddar hembatteriet mot urladdning vid billaddning (`HOLD`/`IDLE`). Stödjer schemaläggning i webbapp med virtuell lastbalansering samt dynamisk laddoptimering i HA för 1–2 bilar. [Guide](docs/SMART_EV_CHARGING_GUIDE.md) |
| 🚿 **Smart Varmvattenoptimering (VVB)** | Värmer varmvattenberedare eller aktiverar plusvärme/SG Ready vid solöverskott och billig el. [Guide](docs/WATER_HEATER_GUIDE.md) |
| ⏸️ **Extern Paus (CheckWatt m.fl.)** | Peka ut en paus-sensor så släpper optimeraren kontrollen och batteriet sätts i `IDLE`. |
| 🔌 **Off-grid & Strömavbrott** | Optimeraren pausas automatiskt när huset är off-grid. För Sonnen detekteras det automatiskt via batteriets API. |

<details>
<summary>Vilka tillstånd känner integrationen igen på sensorerna?</summary>

* **Elbilsladdning:** `on`, `true`, `1`, `charging`, `på`, `charge`, `sant` samt numeriska effektvärden `> 0` W.
* **Extern paus:** `on`, `true`, `1`, `active`, `yes`, `på` eller `sant`.
</details>

---

<a id="stodda-batterier"></a>
## 🔌 Stödda batterier

| Batteri | Kräver | Styrning |
| :--- | :--- | :--- |
| ☀️ [Sonnen](#sonnen) | API v2 + Auth-Token | Lokalt API (EMS Site Limits på nyare firmware) |
| 🌑 [Huawei Luna2000](#huawei-luna2000) | Officiella `Huawei Solar`-integrationen | Via Home Assistant |
| ⚡ [Homevolt](#homevolt) | [Homevolt Local](https://github.com/JohNan/homeassistant-homevolt-local) (HACS) | Via Home Assistant |
| 🔌 [Solis Modbus](#solis-modbus) | [Solis Modbus](https://github.com/hultenvp/solis-sensor) (HACS) | Via Home Assistant |
| 🔋 [Sigenergy](#sigenergy) | [Sigenergy-Local-Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus) (HACS) | Via Home Assistant |
| 🔋 [Solinteg](#solinteg) | [SolaX Inverter Modbus](https://github.com/wills106/homeassistant-solax-modbus) (HACS) | Via Home Assistant |
| ☀️ [Kostal Plenticore](#kostal-plenticore) | Officiella `Kostal Plenticore`-integrationen + Modbus TCP | Modbus TCP |
| ☁️ [Generic / Light](#generic-light) | Egna sensorer och automationer | Du styr själv |

För alla märken utom Generic hittas de flesta mät- och styrentiteter automatiskt med **Auto-Discovery**.

<a id="sonnen"></a>
### ☀️ Sonnen
Stödjer alla vanliga generationer av SonnenBatterie (inklusive **eco 8**, **eco 9** och **eco 10**). Kräver att **API v2** är aktiverat i batteriet.

* **Auth-Token:** Logga in på ditt batteri (`http://<IP-ADRESS>/dash/login`) som *User*, välj **Software integration**, slå på **JSON API** (Read & Write) och kopiera ditt Auth-Token.
* **Äldre system (< 1.35.14, t.ex. eco 8):** Detekteras automatiskt och styrs via klassisk styrning (manuella setpoints och driftlägesväxling).
* **Backup Reserv (EM_USOC):** Om du använder Sonnens backup-funktion läser integrationen av din reserverade nivå (t.ex. 5 %). Reserven döljs lokalt så att molnet ser ditt tillgängliga fönster som 0–100 %.

  > [!IMPORTANT]
  > Dra av reserven från din *totala batterikapacitet* när du konfigurerar batteriet i molnportalen (t.ex. 22 kWh − 5 % = 20,9 kWh), annars räknar AI:n fel på tillgänglig energi.

<details>
<summary><b>Moderna system &amp; EMS Site Limits (firmware ≥ 1.35.14, t.ex. eco 10)</b></summary>

Integrationen identifierar firmwareversionen och styr batteriet via Sonnens inbyggda Energy Management System (`PUT /api/v2/site/limits`). Istället för manuella setpoints och slitande driftlägesväxlingar sätter optimeraren hårdvarugränser och låter batteriets egen elektronik sköta finregleringen.

* **⚡ Hårdvaru-PeakGuard:** Importtaket vid elmätaren (`p_gcp_max_import_limit`) sätts direkt i växelriktarens mätkrets och kapar spikar autonomt på millisekunder.
* **🔄 Asymmetrisk styrning i IDLE &amp; HOLD:**

  | Läge | Beteende |
  | :--- | :--- |
  | **Normal IDLE** | Standard egenförbrukning – batteriet absorberar solel och täcker huslaster fritt. |
  | **Skyddad Solladdning (IDLE)** | Batteriet laddas av sol men spärras från urladdning till huset (`p_bess_inv_max_export_limit: 0`), så att billig solel sparas till en planerad dyr kvällstopp. |
  | **Smart Sol-Export (HOLD)** | Vid höga elpriser spärras solladdning (`p_bess_inv_max_import_limit: 0`) för att sälja all solel till toppris, medan urladdning hålls öppen för att parera moln och matlagningsspikar. |
  | **Ren HOLD** | Både laddning och urladdning fryses (`0 W`) vid buffertskydd eller fryst batteri. |

* **🚫 Minuspriser (Zero Export):** Nätexporten spärras (`p_gcp_max_export_limit: 0`) och allt överskott styrs gratis in i batteriet.
* **🛡️ Failsafe Watchdog:** Gränserna ställs i RAM (sparar flashminnet) med en 10-minuters watchdog (`PT600S`) som återställer normalläge om nätverket går ner.
</details>

<a id="huawei-luna2000"></a>
### 🌑 Huawei Luna2000
Styr Huawei-batterier via den officiella Home Assistant-integrationen.

* **Krav:** En fungerande, förkonfigurerad installation av den officiella `Huawei Solar`-integrationen.
* **Notera:** Batterisensorn inverteras automatiskt så att **Plus (+)** betyder att batteriet **laddar** och **Minus (−)** att det **laddar ur**, vilket matchar Huawei Solar-integrationen.

<a id="homevolt"></a>
### ⚡ Homevolt
Styr Homevolt-batterier lokalt via Home Assistant.

* **Krav:** [Homevolt Local](https://github.com/JohNan/homeassistant-homevolt-local) (HACS) måste vara installerad och konfigurerad först.
* **Notera:** *Auto-Discovery* hittar dina sensorer för SoC, batteri, nät och huslast.

<a id="solis-modbus"></a>
### 🔌 Solis Modbus
Styr Solis-batterier lokalt via Pho3niX90:s Solis Modbus-integration.

* **Krav:** [Solis Modbus](https://github.com/hultenvp/solis-sensor) (HACS), förkonfigurerad.
* **Kompatibilitet:** Optimerad primärt för **Solis S6 Hybrid** (EH-modeller).
* **Notera:** *Auto-Discovery* letar upp mät- och styrentiteter och anpassar sig till olika språk och versioner av integrationen.

<a id="sigenergy"></a>
### 🔋 Sigenergy
Styr Sigenergy-växelriktare lokalt via Modbus.

* **Krav:** [Sigenergy-Local-Modbus](https://github.com/TypQxQ/Sigenergy-Local-Modbus) (HACS), förkonfigurerad.
* **Notera:** *Auto-Discovery* letar upp entiteterna och känner av om integrationen använder W eller kW och sköter omvandlingen.

<a id="solinteg"></a>
### 🔋 Solinteg
Styr Solinteg-växelriktare lokalt via Modbus.

* **Viktigt krav:** Du *måste* använda [SolaX Inverter Modbus](https://github.com/wills106/homeassistant-solax-modbus) (HACS). Trots namnet har den inbyggt stöd för Solinteg. Andra Solinteg-integrationer stöds inte eftersom de saknar standardiserade styrentiteter.
* **Notera:** *Auto-Discovery* letar upp mät- och styrentiteter från SolaX-integrationen.

<a id="kostal-plenticore"></a>
### ☀️ Kostal Plenticore
Styr Kostal Plenticore-växelriktare med hembatteri (t.ex. BYD Battery-Box) via Modbus TCP.

* **Krav:**
  1. Den officiella integrationen [Kostal Plenticore](https://www.home-assistant.io/integrations/kostal_plenticore/) måste vara installerad (läser SoC, husförbrukning, solproduktion och nätutbyte).
  2. **Aktivera extern Modbus-styrning:** Logga in i växelriktarens webbgränssnitt som *Installatör*, gå till **Inställningar → Batterihantering** och välj batteriläge **"Extern styrning via Modbus-protokoll (TCP)"**. Kontrollera att Modbus TCP är aktiverat (standardport `1502`, enhets-ID `71`).
* **Notera:** *Auto-Discovery* hittar växelriktaren, hämtar IP-adressen från Home Assistant och länkar samman sensorerna (`battery_soc`, `Home_P`, `Dc_P`, `Grid_P`, `Inverter:State`).

<a id="generic-light"></a>
### ☁️ Generic / Light
För dig som bara vill hämta optimeringsbeslut och räkna ut last lokalt, men styra batteriet via egna automationer. Se [installationsguiden för Generic](docs/GENERIC_BATTERY_SETUP.md), som även innehåller färdiga automations- och skriptexempel.

---

<a id="installation"></a>
## 📦 Installation

### Via HACS
**Snabbast:** klicka på knappen överst för att öppna integrationen direkt i HACS. Annars:

1. Öppna **HACS** → **Integrationer** och sök efter **Battery Optimizer Light Plus**.
2. Klicka på **Ladda ner** och starta om Home Assistant vid behov.

<details>
<summary><b>Installera som anpassat arkiv (om den inte syns i standardkatalogen)</b></summary>

1. Gå till **HACS** → **Integrationer**.
2. Klicka på de tre prickarna uppe till höger och välj **Anpassade arkiv (Custom repositories)**.
3. Lägg till URL `https://github.com/awestin67/battery-optimizer-light-plus` och kategori **Integration**.
4. Ladda ner "Battery Optimizer Light Plus" och starta om Home Assistant.
</details>

### Konfiguration
1. Gå till **Inställningar** → **Enheter & Tjänster** → **Lägg till integration** och sök efter **Battery Optimizer Light Plus**.
2. Följ guiden:

   | Steg | Innehåll |
   | :--- | :--- |
   | **1** | Välj batterityp (Sonnen, Huawei, Homevolt, Solis Modbus, Sigenergy, Solinteg, Kostal Plenticore, Generic). |
   | **2** | Fyll i batterispecifika uppgifter (t.ex. IP och API-token för Sonnen, eller enheter för Huawei). |
   | **3** | Fyll i din API-nyckel från Dashboarden. Utom för **Generic** hittas de flesta entiteter automatiskt; för Generic pekar du själv ut sensorerna. |
   | **4** *(valfritt)* | **Husets totala förbrukning.** Saknar du en pålitlig nätutbytes-sensor men har en sensor för husets totala last kan du välja den här. Lämna då Grid Sensor tomt. |
   | **5** *(valfritt)* | **Elbilsladdning-sensor** för smart elbilsstöd. |
   | **6** *(valfritt)* | **Pausa Battery Optimizer**-sensor om du använder externa stödtjänster (t.ex. CheckWatt). |
   | **7** *(valfritt)* | **Off-grid / Strömavbrott**-sensor för att pausa optimeraren vid nätbortfall. |

> [!TIP]
> Klicka på **"Konfigurera"** på integrationen när som helst för att ändra sensorer eller aktivera inställningar som **"Invertera Batteri Sensor"** (användbart om din växelriktare rapporterar Plus för laddning).

---

<a id="sensorer"></a>
## ℹ️ Sensorer

När systemet är igång skapas sensorer för att övervaka optimeringen.

### Beslut och styrning
| Sensor | Beskrivning |
| :--- | :--- |
| ⚡ `sensor.optimizer_light_action` | Aktuellt molnbeslut: `CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`. |
| 🎯 `sensor.optimizer_light_charge_target` | Önskad laddningseffekt (W, alltid positivt). |
| 🎯 `sensor.optimizer_light_discharge_target` | Önskad urladdningseffekt (W, alltid positivt). |
| ⏭️ `sensor.optimizer_light_next_action` | Nästa kommande molnbeslut. |
| 🕒 `sensor.optimizer_light_next_action_time` | Tidpunkt då nästa beslut förväntas. |
| 🚫 `sensor.optimizer_light_dynamic_export_limit` | Dynamisk exportgräns i kW (t.ex. `0.0` vid Zero Export, okänd om molnet inte begränsar). |

### Effektvakt och last
| Sensor | Beskrivning |
| :--- | :--- |
| 🛡️ `sensor.optimizer_light_peakguard_status` | Status för lokala effektvakten (t.ex. `Monitoring`, `Triggered`, `Paused`). |
| 🛑 `sensor.optimizer_light_peak_limit` | Effektgräns (W) som effektvakten försvarar. |
| 🏠 `sensor.optimizer_light_virtual_load` | Husets beräknade nettolast i realtid (W). |
| 🏠 `sensor.optimizer_light_house_consumption` | Husets faktiska förbrukning (W) som skickas till molnet. |

### Batteri
| Sensor | Beskrivning |
| :--- | :--- |
| 🔌 `sensor.sonnen_grid_in_out` *(Sonnen)* | Nätutbyte i realtid (W). **+** = importerar, **−** = exporterar. |
| 🔋 `sensor.*_battery_in_out` *(Sonnen, Huawei, Homevolt)* | Batteriets effekt (W). Standard är **−** = laddar; för Huawei är det inverterat. |
| 📊 `sensor.*_soc` *(Sonnen, Huawei, Homevolt)* | Laddningsnivå (%). |
| 🛡️ `sensor.*_sonnen_backup_reserv` *(Sonnen)* | Inställd hårdvarureserv för strömavbrott (%), så du kan verifiera vilken reserv molnet räknar med. |

### Analys, VVB och elbil
| Sensor | Beskrivning |
| :--- | :--- |
| 💰 `sensor.optimizer_light_daily_savings` | Dagens besparing (SEK). |
| 🤖 `sensor.optimizer_light_ai_summary` | Daglig AI-sammanfattning (hela texten i attributet `summary_text`). |
| 📉 `sensor.battery_optimizer_graph_data` | Graf-data (historik och prognos) i JSON-attribut, används av ApexCharts. |
| 🚿 `binary_sensor.optimizer_light_vvb_boost` | `on` när varmvatten/plusvärme ska aktiveras. |
| ℹ️ `sensor.optimizer_light_vvb_orsak` | Förklaring till varför VVB körs eller pausas. |
| 🚗 `sensor.optimizer_light_ev_schedule` | Laddschema för elbilar (JSON i attributet `schedules`). |

📊 Färdiga dashboard-kort för AI-sammanfattning, nästa planerade åtgärd och ApexCharts finns i [`docs/DASHBOARD_EXAMPLES.md`](docs/DASHBOARD_EXAMPLES.md).

---

<a id="felsokning"></a>
## 🐞 Felsökning

Aktivera debug-loggning om du vill verifiera styrningen eller se vilken data som skickas till och från molnet.

**Alternativ 1 – via Home Assistant (rekommenderas, ingen omstart):**
1. Gå till **Inställningar** → **Enheter och tjänster** och leta upp **Battery Optimizer Light Plus**.
2. Klicka på **⋮** och välj **"Aktivera felsökningsloggning"**.
3. Låt integrationen köra några minuter.
4. Välj **"Inaktivera felsökningsloggning"** – Home Assistant laddar då ner en färdig loggfil.

**Alternativ 2 – permanent via `configuration.yaml`** (kräver omstart):

```yaml
logger:
  default: warning
  logs:
    custom_components.battery_optimizer_light_plus: debug
```

Loggarna finns under **Inställningar** → **System** → **Loggar**.

**Nyckelord att söka efter:**

| Nyckelord | Visar |
| :--- | :--- |
| `Light-Request` | Payloaden som skickas till molnet (batterityp, version, SoC, förbrukning). |
| `Verkställer beslut via Sonnen Site Limits` | Att EMS Site Limits skickas lokalt till Sonnen. |
| `Sonnen är i driftläge` | Driftlägeskontroller och växlingar till Mode 2. |
| `PeakGuard` | När effektvakten aktiveras eller justerar effekten. |

---

<a id="guider"></a>
## 📚 Guider & dokumentation

| Guide | Innehåll |
| :--- | :--- |
| [Generic / övriga batterier](docs/GENERIC_BATTERY_SETUP.md) | Förberedelser, automation och skript för batterier utan inbyggt stöd. |
| [Smart elbilsladdning](docs/SMART_EV_CHARGING_GUIDE.md) | Schemaläggning i webbapp, realtidsskydd och dynamisk laddning för 1–2 bilar. |
| [Varmvattenoptimering (VVB)](docs/WATER_HEATER_GUIDE.md) | Koppla switch, värmepump eller Shelly-relä. |
| [Dashboard-exempel](docs/DASHBOARD_EXAMPLES.md) | AI-sammanfattning, nästa åtgärd och ApexCharts. |
| [SolarEdge Zero Export](docs/SOLAREDGE_ZERO_EXPORT_GUIDE.md) | Blueprint och guide för AC-kopplade solceller. |
| [Arkitektur](docs/ARCHITECTURE.md) | Hur molnet och den lokala integrationen samverkar. |

---

## 📄 Licens
Distribueras under GPL v3. Se [LICENSE](LICENSE).

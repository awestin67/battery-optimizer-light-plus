# 🚗 Smart Elbilsladdning (EV Planner & Integration)

[← Tillbaka till README](../README.md)

Battery Optimizer Light erbjuder tre nivåer av elbilsladdning för att optimera ekonomin och skydda din huvudsäkring och ditt hembatteri:

* [🚗 **Schemalagd elbilsladdning (Webbapp):**](#ev-planner-webbapp) Schemalägg fasta laddtider i webbappen med virtuell lastbalansering och 60-minuters skrotning. Noll YAML krävs!
* [🚗 **Elbilsskydd i realtid (Basic i HA):**](#realtidsskydd) Peka ut din laddbox i HA så hålls hembatteriet i HOLD vid laddning (eller IDLE vid solelöverskott).
* [🚗 **Dynamisk elbilsladdning (V2 i HA):**](#dynamisk-laddning-ha) Prisoptimerad laddning för upp till 2 bilar baserat på avresetid och önskad kWh när kabeln sätts i.

---

<a id="ev-planner-webbapp"></a>
## 🚗 Alternativ 1: Schemalagd elbilsladdning (Webbapp)

Om du laddar bilen på fasta tider är detta det absolut smidigaste alternativet. Allt ställs in grafiskt i webbappens dashboard med noll YAML-kod.

### Så här ställer du in det:
1. Logga in på [Web Dashboarden](https://battery-prod.awestinconsulting.se).
2. Gå till fliken **Inställningar → Elbil & Effektvakt**.
3. Under rubriken **🚗 Schemalagd Elbilsladdning** klickar du på bilens expander (eller *➕ Lägg till schema*):
   * **Aktivt Schema:** Kryssa i för att aktivera schemat.
   * **Namn:** Ge bilen eller schemat ett namn (t.ex. *Skoda*, *Tesla*).
   * **Veckodagar:** Välj vilka veckodagar laddningen ska ske (Måndag–Söndag, stödjer flerval).
   * **Tidsintervall (Klockslag):** Dra i tids-slidern (0–24) för att välja start- och sluttid (t.ex. `18:00 - 24:00` eller `22:00 - 06:00`). Algoritmen stöder automatiskt laddfönster som korsar midnatt!
   * **Max Ladd-effekt (kW):** Ange laddboxens/bilens maxeffekt i kW (t.ex. `11.0` kW).
   * **Återkommande varje vecka:** Kryssa i för fast veckoschema. Lämnar du den okryssad sparas det som en engångsladdning som automatiskt gallras bort när datumet har passerats.
   * **Pausa schema:** Schemat kan pausas tillfälligt utan att inställningarna försvinner (visas som ⏸️ *Schemat är pausat*).
   * *(Flera bilar stöds – du kan ha separata scheman för hushållets olika fordon).*

### Hur AI:n och optimeraren arbetar i bakgrunden:
* **Förköp av billig el:** AI:n bakar in den förväntade elbilslasten i sin framtidsprognos. Den ser till att förköpa el till hembatteriet under dygnets billigaste timmar inför laddfönstret, och undviker att tömma hembatteriet precis innan bilen kopplas in.
* **Virtuell Lastbalansering (Huvudsäkringsskydd):** Optimeraren drar automatiskt av husets övriga beräknade förbrukning från bilens inställda effekt baserat på din huvudsäkring (*Inställningar → Sol & Fastighet*, med 10 % säkerhetsmarginal). Bilens tilldelade effekt i simuleringen blir `min(max_kw, max(0, fuse_kw - huslast))`. På så vis planerar optimeringen aldrig för en högre totalförbrukning än din huvudsäkring klarar av.
* **Ingen fantomlast i realtid:** Om bilen vid den aktuella tidpunkten inte är inkopplad (`is_ev_charging: False` från Home Assistant) läggs det inte på någon fiktiv förbrukning i realtid. Därmed blockeras inte solöverskott eller batteriladdning felaktigt om du kommer hem sent.
* **Automatisk skrotning efter 60 minuter:** Om vi befinner oss inuti ett schemalagt fönster och 60 minuter har passerat sedan schemats starttid utan att bilen börjat ladda (`is_ev_charging: False`), avbryts schemat automatiskt för resten av natten. Detta frigör hembatteriet helt så att det inte hålls spärrat för en bil som inte är hemma eller som redan är fulladdad.
* **Batteriprioritering (HOLD vid laddning):** När bilen väl laddar sätts hembatteriet i `HOLD` så att batteriets cykler sparas till hushållet. Finns det ett direkt solelöverskott som räcker till både huset och bilen övergår optimeraren automatiskt till `IDLE` så att hembatteriet kan laddas med överskottet!

---

<a id="realtidsskydd"></a>
## 🚗 Alternativ 2: Elbilsskydd i realtid (Basic i HA)

Oavsett om du använder **Alternativ 1** (Webbapp-schema) eller **Alternativ 3** (Dynamiskt V2-schema) rekommenderas starkt att peka ut din laddbox i Home Assistant.

### Så här ställer du in det:
1. Gå till *Inställningar -> Enheter och tjänster -> Battery Optimizer Light Plus -> Konfigurera*.
2. Peka ut din laddbox sensor under **Elbilsladdning Sensor** (din laddbox effektmätare i Watt eller dess binära laddningsstatus).

### Hur det fungerar:
* När laddboxen drar ström (`> 0 W` eller status `charging`/`on`) känner integrationen av det i realtid och signalerar `is_ev_charging: True` till molnet.
* Detta sätter hembatteriet i `HOLD` så att batteriet aldrig laddas ur i elbilen.
* Om solcellerna producerar mer el än huset och bilen förbrukar tillsammans (`sol > hus + bil`) övergår systemet automatiskt till `IDLE` så att överskottet laddar hembatteriet istället för att gå ut på elnätet!

---

<a id="dynamisk-laddning-ha"></a>
## 🚗 Alternativ 3: Dynamisk elbilsladdning (V2 i HA)

För dig som har varierande körmönster och vill att molnet ska beräkna det billigaste möjliga laddschemat dynamiskt varje dygn så fort kabeln sätts i. Stöder upp till två bilar samtidigt.

### Steg-för-steg Guide (1 eller 2 bilar)

#### Steg 1: Skapa Hjälpare (Helpers)
Skapa följande Helpers i Home Assistant (*Inställningar -> Enheter och tjänster -> Hjälpare*) för att definiera dina laddbehov. För två bilar skapar du dubbla uppsättningar (t.ex. med ändelsen `_car1` och `_car2`):
- `input_number` för önskat mål i kWh (t.ex. `input_number.ev_target_kwh_car1`). Skala: 0–100.
- `input_number` för bilens maxeffekt i kW (t.ex. `input_number.ev_max_kw_car1`). Skala: 0–22.
- `input_datetime` för önskad avresetid (t.ex. `input_datetime.ev_depart_time_car1`). Ska endast visa Tid (Time).

#### Steg 2: Koppla i Integrationen
1. Gå till *Inställningar -> Enheter och tjänster*.
2. Klicka på **Konfigurera** på Battery Optimizer Light Plus.
3. Välj dina skapade Helpers från rullistorna för **Bil 1**. Ange även din `cable_connected`-sensor och din `is_charging`-sensor från din laddbox.
4. *(Har du en andra bil?)* Fyll i motsvarande rullistor för **Bil 2** längre ner på samma sida.

#### Steg 3: Så här fungerar det i praktiken
1. **Du pluggar i kabeln:** Din `cable_connected`-sensor slår om till `on`.
2. **Schemat skapas:** Integrationen läser av dina Helpers och beräknar den billigaste tidslinjen. Om du pluggar in båda bilarna skapas ett optimerat körschema för båda samtidigt!
3. **Data exponeras:** Schemat sparas i sensorn `sensor.optimizer_light_ev_schedule`. Attributet `schedules` innehåller start- och stopptider för dina bilar.

#### Steg 4: Din Automation (Exempel)
Skapa en automation i Home Assistant för respektive bil. Använd `Template` i din trigger för att trigga på starttiden, och passa även på att ställa in laddboxens effekt (`charge_kw`) till det värde som molnet har räknat ut är optimalt!

> **Tips:** Gå till *Automationer -> Skapa ny automation -> Klicka på de tre prickarna uppe till höger och välj "Redigera som YAML"*. Klistra sedan in koden nedan.

I templaten nedan anger du **samma namn för bilen** som du skrev in när du konfigurerade integrationen:

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

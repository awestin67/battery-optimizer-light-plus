# 📖 Installationsguide: Generic Battery Optimizer Light

Denna guide är skriven för dig som ska installera och konfigurera **Battery Optimizer Light**-integrationen i Home Assistant för en batterityp/växelriktare som saknar "native" stöd (t.ex. Sungrow, Fronius, GoodWe, m.fl). Du gör detta genom att välja plattformen **"Generic / Light"** under installationen.

När du väljer *Generic* agerar integrationen i **passivt läge (Read-Only)**. Den övervakar ditt batteris tillstånd och nätets energiflöde, kommunicerar med molnet (som bygger den optimala prisplanen baserad på Nordpool, solcellsprognoser och elbilsladdning) och exponerar sedan de smarta besluten tillbaka till Home Assistant i form av sensorer. 

Du måste själv bygga en mindre automation i Home Assistant för att "översätta" integrationens sensor-beslut (t.ex. `CHARGE`, `HOLD`, `DISCHARGE`) till de specifika register och anrop som just din växelriktare förstår.

---

## Steg 1: Förberedelser innan installation
För att molnet ska kunna göra korrekta ekonomiska beräkningar och veta hur mycket energi som finns i huset, **måste** du ha tre (3) specifika sensorer redo i Home Assistant innan du börjar:

1. **Batteriets Laddningsnivå (SoC):**
   - En sensor som visar procent (`%`), t.ex. `sensor.mitt_batteri_soc`. 
   - Ska vara ett heltal mellan 0 och 100.
2. **Batteriets Effekt (In/Ut):**
   - En sensor som visar realtidseffekten som strömmar till/från batteriet i **Watt (W)**.
   - **VIKTIGT (Tecken-regel):** Sensorn måste visa negativt värde (`-`) när batteriet *laddas upp*, och positivt värde (`+`) när batteriet *laddas ur*. Om din växelriktare har omvända tecken, måste du först skapa en egen template-sensor i Home Assistant som inverterar värdet (multiplicerar med -1).
3. **Husets Nätutbyte (Grid In/Out):**
   - En sensor som visar husets mätare (effekt mot elnätet) i **Watt (W)**.
   - **VIKTIGT (Tecken-regel):** Sensorn måste visa negativt värde (`-`) när huset *säljer/exporterar* ström, och positivt värde (`+`) när huset *köper/importerar* ström. 

När du har dessa tre sensorer klara, och de följer reglerna för negativa/positiva tecken, är du redo för nästa steg!

---

## Steg 2: Installera & Konfigurera i Home Assistant
1. Gå till **Inställningar -> Enheter och Tjänster -> Lägg till integration**.
2. Sök fram *Battery Optimizer Light Plus*.
3. Välj **Generic / Light** som din mjukvaruplattform.
4. Du får nu upp en meny där du klistrar in din **API-nyckel** (som du skapat i molnets webbgränssnitt).
5. Nu blir du ombedd att mappa de tre sensorerna du förberedde i Steg 1. Klicka på respektive rullista och sök fram dina sensorer.
6. Om du även använder Elbilsladdning (EV) eller Solcells-styrning, ställer du in detta på sista sidan.
7. Avsluta installationen. Integrationen skapar nu alla nödvändiga `sensor.optimizer_light_` entiteter i bakgrunden.

---

## Steg 3: Automatisera ditt batteri
Eftersom integrationen är *Generic* kommer den inte röra din växelriktare. Du behöver skapa en automation som lyssnar på sensorn `sensor.optimizer_light_action` och utför rätt åtgärd på din växelriktare.

### De 4 driftlägena
Sensorn `sensor.optimizer_light_action` kan anta ett av fyra lägen varje 5-minutersperiod:
- `CHARGE`: Batteriet bör laddas från elnätet (det är extremt billigt just nu).
- `DISCHARGE`: Batteriet bör tvingas laddas ur ut på nätet (prisspik/exportlönsamhet).
- `HOLD`: Batteriet bör pausas (varken laddas ur eller i, t.ex. under natten i väntan på morgonspiken).
- `IDLE`: Batteriet ska återgå till sitt standardläge (automatiskt maximera egenkonsumtion av solel).

För `CHARGE` och `DISCHARGE` ger integrationen även specifika målvärden för **hur snabbt** det ska gå. Dessa värden exponeras i sensorerna `sensor.optimizer_light_charge_target` respektive `sensor.optimizer_light_discharge_target` (alltid uttryckta i positiva absolutbelopp i **Watt**, t.ex. `3500`).

### Koden
Nedan är det absolut enklaste sättet att knyta ihop detta (via YAML). Kopiera in koden nedan i en ny automation och peka om `action:`-delarna till de tjänster eller skript som styr just din växelriktare.

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
          # BYT UT raderna under 'action' till det anrop din växelriktare kräver för att laddas
          - action: script.din_inverter_charge 
            data:
              power: "{{ charge_target }}" # Använd denna variabel för att få rätt W-effekt
              
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'DISCHARGE' }}"
        sequence:
          # BYT UT raderna under 'action' till det anrop din växelriktare kräver för att laddas ur
          - action: script.din_inverter_discharge 
            data:
              power: "{{ discharge_target }}"
              
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'HOLD' }}"
        sequence:
          # BYT UT: Anropet för att pausa batteriet (t.ex. ställa max effekt till 0W)
          - action: script.din_inverter_hold 
            data: {}
            
      - conditions:
          - condition: template
            value_template: "{{ current_action == 'IDLE' }}"
        sequence:
          # BYT UT: Anropet för att återställa växelriktaren till fabriks-beteende (Self-Consumption)
          - action: script.din_inverter_auto 
            data: {}
            
    default:
      - action: script.din_inverter_auto 
        data: {}
```

## Tips för framgång
* Integrationen uppdaterar besluten exakt var 5:e minut. Din automation triggas omedelbart så fort värdet ändras (t.ex. från `IDLE` till `CHARGE`).
* Effekten från `charge_target` och `discharge_target` har redan korrigerats i molnet så den överskrider aldrig batteriets inställda maxeffekt och skyddar även din huvudsäkring från att gå (om du angett säkringsstorlek i webbportalen). Du kan därmed lita blint på siffran i variablerna.
* Du behöver inte hantera minustecken. Siffran för urladdning (`discharge_target`) är alltid ett rent, positivt watt-tal (t.ex. `4200`). Hur din växelriktare sedan vill ta emot detta tal (som positivt eller negativt) hanterar du smidigast i dina egna anrop.

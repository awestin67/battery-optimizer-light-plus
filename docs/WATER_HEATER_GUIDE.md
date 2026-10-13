# 🚿 Smart Varmvattenoptimering (VVB Boost)

[← Tillbaka till README](../README.md)

När integrationen körs skapas automatiskt två entiteter för smart varmvattenstyrning:
* `binary_sensor.optimizer_light_vvb_boost`: Slår om till `on` när optimeraren beordrar extra varmvattenuppvärmning (t.ex. vid billiga eltimmar eller vid solöverskott när hembatteriet är fulladdat).
* `sensor.optimizer_light_vvb_orsak`: Visar den aktuella orsaken i klartext (t.ex. *"Solöverskott (1.4 kW) | Batteri 94%"*).

## Styra din VVB / Värmepump:

Det finns två sätt att koppla din hårdvara:

* **Alternativ 1 (Enklast – Direkt i inställningarna):**
  Gå till *Inställningar -> Enheter och tjänster -> Battery Optimizer Light Plus -> Konfigurera*:
  - Välj din switch under **Varmvattenberedare / Plusvärme (Switch)**. Integrationen slår då automatiskt på och av switchen åt dig i realtid!
  - *(Valfritt)* Välj din temperatursensor under **Varmvattentemperatur Sensor**. Temperaturen skickas då till molnet så att boost spärras automatiskt om tanken når inställd maxtemperatur (t.ex. 65 °C).

* **Alternativ 2 (Via Automation):**
  Om du har avancerade villkor eller vill styra via scripts/klimatenheter kan du lämna switch-fältet tomt och istället skapa en vanlig Home Assistant-automation mot signalen `binary_sensor.optimizer_light_vvb_boost`:

## 1. Automation: IVT / Värmepump (Plusvärme / SG Ready)
Koppla signalen till din värmepumps Plusvärme-switch eller SG Ready-ingång:

```yaml
alias: "🚿 IVT Plusvärme (Smart VVB)"
description: "Aktiverar Plusvärme på värmepumpen vid billig el eller solöverskott"
trigger:
  - platform: state
    entity_id: binary_sensor.optimizer_light_vvb_boost
condition: []
action:
  - if:
      - condition: state
        entity_id: binary_sensor.optimizer_light_vvb_boost
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

## 2. Automation: Extra VVB (Shelly-relä / Kontaktor)
Om du styr en elpatron eller extra beredare via ett Shelly-relä eller kontaktor:

```yaml
alias: "🚿 Extra VVB Kontaktor (Smart VVB)"
description: "Slår till elpatronen vid billig el eller solöverskott"
trigger:
  - platform: state
    entity_id: binary_sensor.optimizer_light_vvb_boost
condition: []
action:
  - if:
      - condition: state
        entity_id: binary_sensor.optimizer_light_vvb_boost
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

## 3. Dashboard-kort i Home Assistant (Exempel)
```yaml
type: entities
title: 🚿 Varmvattenoptimering
entities:
  - entity: binary_sensor.optimizer_light_vvb_boost
    name: VVB Boost Status
  - entity: sensor.optimizer_light_vvb_orsak
    name: Orsak
  - entity: switch.extra_vvb
    name: Beredare / Plusvärme
```

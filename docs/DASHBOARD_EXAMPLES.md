# 📊 Dashboard-exempel

[← Tillbaka till README](../README.md)

## 🤖 AI-Sammanfattning

Eftersom Home Assistant har en gräns på 255 tecken för vanliga sensorstatusar lagras den fullständiga AI-genererade texten säkert i sensorns *attribut*. För att läsa sammanfattningen bekvämt i din Dashboard rekommenderas att du använder ett inbyggt **Markdown-kort**.

Skapa ett nytt manuellt kort i din Dashboard och klistra in följande kod:

```yaml
type: markdown
title: 🤖 AI Sammanfattning
content: >
  {{ state_attr('sensor.optimizer_light_ai_summary', 'summary_text') }}
```

## 📅 Nästa planerade åtgärd

För att få en snygg textsträng som visar *nästa* planerade åtgärd (t.ex. "↳ Planerat: 🟢 CHARGE kl 14:00") kan du lägga till en egen mall-sensor (Template Sensor) i Home Assistant.

Lägg till följande kod i din `configuration.yaml` (under `template:`):

```yaml
template:
  - sensor:
      - name: "Battery Optimizer Next Action"
        icon: mdi:calendar-arrow-right
        state: >
          {% set action = states('sensor.optimizer_light_next_action') %}
          {% set time_str = states('sensor.optimizer_light_next_action_time') %}

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

## 📈 ApexCharts

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

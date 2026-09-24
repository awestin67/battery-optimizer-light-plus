# Implementationsplan: Sonnen EMS Site Power Limits (v1.35.14+) för Home Assistant (BOLP)

**Mål:** Automatiskt detektera och utnyttja Sonnens nya officiella EMS Site Limits API (`PUT /api/v2/site/limits`) i Home Assistant-integrationen (**Battery Optimizer Light Plus**, repot `battery-optimizer-light-base`). Detta eliminerar manuella driftlägesväxlingar (`operating_mode: 1/2`), ger hårdvarugaranterad PeakGuard vid elmätaren och möjliggör perfekt exportspärr vid negativa elpriser.

---

## 📌 Bakgrund & Arkitektur

### Problemet med Legacy-styrning (< 1.35.14)
1. **Manuellt läge (`operating_mode: 1`):** För att ladda eller hålla (`HOLD`) batteriet tvingas integrationen sätta batteriet i manuellt läge. Då stängs Sonnens interna självkonsumtionsloop av, vilket kan leda till att batteriet missar att absorbera överskottssol.
2. **Reaktiv PeakGuard:** När huset drar mycket ström måste HA upptäcka toppen och skicka ett urladdningskommando, vilket skapar en fördröjning på 5–15 sekunder.

### Lösningen i Sonnen 1.35.14+ (EMS Site Limits)
1. **Batteriet förblir permanent i `Self-consumption` (`operating_mode: 2`):** Inga manuella växlingar!
2. **Hårdvarugaranterad PeakGuard:** Vi sätter `p_gcp_max_import_limit` (W) vid elmätaren (GCP). Sonnens interna regulator parerar effekttoppar på millisekundnivå.
3. **Negativa elpriser:** Vi sätter `p_gcp_max_export_limit = 0` (W) vid minuspriser. Solenergi tillåts gå till hus och batteri, men inte en watt exporteras ut på nätet.
4. **Smart HOLD:** Vid `action == "HOLD"` sätter vi `p_bess_inv_max_export_limit = 0` (W). Batteriet kan inte ladda ur till huset, men solpanelerna kan fortsätta ladda batteriet fritt!
5. **Inbyggd Watchdog:** Parametern `duration: "PT10M"` (10 minuter) skickas så att gränserna hålls aktiva över molnets 5-minutersintervall (Sonnens API-default är annars `PT30S`). Alla gränser nollställs automatiskt om HA tappar kontakten i mer än 10 minuter.

---

## 🔌 Verifierade Sonnen API Endpoints

| Funktion | Metod | Endpoint | Headers | Beskrivning |
| :--- | :--- | :--- | :--- | :--- |
| **Hämta mjukvaruversion** | `GET` | `/api/v2/configurations/DE_Software` | `Auth-Token` | Returnerar `{"DE_Software": "1.35.14"}` |
| **Sätt Site Power Limits** | `PUT` | `/api/v2/site/limits` | `Auth-Token`, `Content-Type: application/json` | Sätter EMS-gränser med watchdog |
| **Läs aktiva gränser** | `GET` | `/api/v2/site/limits` | `Auth-Token` | Läser av batteriets aktiva hårdvarubegränsningar |
| **Systemstatus (öppen)** | `GET` | `/api/v2/status` | Inga (öppen) | Öppen status |

### Request Body för `PUT /api/v2/site/limits`
```json
{
  "duration": "PT10M",
  "p_gcp_max_import_limit": 4500,
  "p_gcp_max_export_limit": 0,
  "p_bess_inv_max_export_limit": 0,
  "p_bess_inv_max_import_limit": 3300
}
```

---

## 🛠️ Steg-för-steg Implementationsplan i `battery-optimizer-light-plus`

### Steg 1: Utöka `custom_components/battery_optimizer_light_plus/batteries/sonnen/api.py`
Lägg till dedikerade metoder för version, läsning och skrivning av Site Limits:

```python
API_SITE_LIMITS = "/api/v2/site/limits"
API_CONFIG_SOFTWARE = "/api/v2/configurations/DE_Software"

async def async_get_software_version(self) -> str | None:
    """Hämtar firmware-version från DE_Software."""
    url = f"{self._base_url}{API_CONFIG_SOFTWARE}"
    try:
        async with self._session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("DE_Software")
    except Exception as e:
        _LOGGER.debug("Kunde inte hämta DE_Software från Sonnen: %s", e)
    return None

async def async_set_site_limits(self, limits: dict) -> bool:
    """Sätter site power limits via PUT /api/v2/site/limits."""
    url = f"{self._base_url}{API_SITE_LIMITS}"
    try:
        # Rensa bort eventuella None-värden
        payload = {k: v for k, v in limits.items() if v is not None}
        if "duration" not in payload:
            payload["duration"] = "PT10M"
            
        async with self._session.put(url, json=payload, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status in (200, 204):
                return True
            _LOGGER.warning("Sonnen PutSiteLimits returnerade status %s: %s", resp.status, await resp.text())
            return False
    except Exception as e:
        _LOGGER.error("Fel vid anrop till Sonnen PutSiteLimits: %s", e)
        return False

async def async_get_site_limits(self) -> dict | None:
    """Hämtar aktiva site limits via GET /api/v2/site/limits."""
    url = f"{self._base_url}{API_SITE_LIMITS}"
    try:
        async with self._session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        _LOGGER.debug("Kunde inte hämta aktiva site limits från Sonnen: %s", e)
    return None
```

---

### Steg 2: Uppdatera `custom_components/battery_optimizer_light_plus/batteries/sonnen/sonnen.py`

1. **Identifiera mjukvaruversion vid uppstart:**
   ```python
   from awesomeversion import AwesomeVersion

   class SonnenBattery(BatteryApi):
       def __init__(self, hass: HomeAssistant, api: SonnenAPI, soc_entity: str | None = None):
           ...
           self._software_version: str | None = None
           self._is_modern_ems: bool = False

       @property
       def software_version(self) -> str | None:
           return self._software_version

       @property
       def is_modern_ems(self) -> bool:
           return self._is_modern_ems

       async def async_init_version(self):
           """Detekterar Sonnen firmware och aktiverar EMS om >= 1.35.14."""
           sw = await self._api.async_get_software_version()
           if sw:
               self._software_version = sw
               try:
                   self._is_modern_ems = AwesomeVersion(sw) >= AwesomeVersion("1.35.14")
                   if self._is_modern_ems:
                       _LOGGER.info("Sonnen kör mjukvara %s >= 1.35.14: Aktiverar modernt EMS Site Limits läge!", sw)
                   else:
                       _LOGGER.info("Sonnen kör äldre mjukvara %s (< 1.35.14): Använder legacy driftlägesstyrning.", sw)
               except Exception as err:
                   _LOGGER.warning("Kunde inte parsa Sonnen version '%s': %s", sw, err)
   ```

2. **Uppdatera `apply_action` med stöd för `sonnen_site_limits`:**
   ```python
   async def apply_action(self, action: str, target_kw: float = 0.0, sonnen_site_limits: dict | None = None):
       """Verkställer ett beslut från molnet eller lokalt."""
       # Om batteriet stödjer moderna Site Limits och molnet skickade med payload:
       if self._is_modern_ems and sonnen_site_limits:
           _LOGGER.debug("Verkställer beslut via Sonnen Site Limits: %s", sonnen_site_limits)
           
           # Säkerställ att batteriet ligger kvar i Self-consumption (Mode 2)
           await self._api.async_set_operating_mode(2)
           
           # Skicka gränserna direkt till PUT /api/v2/site/limits
           success = await self._api.async_set_site_limits(sonnen_site_limits)
           if success:
               return True
           _LOGGER.warning("Misslyckades att sätta Site Limits, provar fallback...")

       # --- LEGACY FALLBACK (< 1.35.14) ---
       power_w = int(target_kw * 1000)
       if action == "CHARGE":
           await self._api.async_set_operating_mode(1)
           await asyncio.sleep(0.5)
           await self.async_set_charge(power_w)
       elif action == "DISCHARGE":
           await self._api.async_set_operating_mode(1)
           await asyncio.sleep(0.5)
           await self.async_set_discharge(power_w)
       elif action == "HOLD":
           await self._api.async_set_operating_mode(1)
           await asyncio.sleep(0.5)
           await self.async_set_idle()
       elif action == "IDLE":
           await self._api.async_set_operating_mode(2)
   ```

---

### Steg 3: Uppdatera `custom_components/battery_optimizer_light_plus/coordinator.py`

1. **Skicka med `inverter_software_version` i `/api/signal`:**
   I metoden `_async_update_data()`:
   ```python
   sw_ver = getattr(self.battery_api, "software_version", None)
   payload = {
       "api_key": self.api_key,
       "soc": soc,
       "inverter_brand": "sonnen",
       "inverter_software_version": sw_ver,
       ...
   }
   ```

2. **Skicka med `sonnen_site_limits` till `apply_action`:**
   När molnets signal-svar tagits emot:
   ```python
   site_limits = response_data.get("sonnen_site_limits")
   await self.battery_api.apply_action(
       action=response_data.get("action", "IDLE"),
       target_kw=response_data.get("target_power_kw", 0.0),
       sonnen_site_limits=site_limits
   )
   ```

---

### Steg 4: Diagnostik & Sensor i `custom_components/battery_optimizer_light_plus/sensor.py`
Skapa en diagnostiksensor så användaren ser i HA-gränssnittet vilket läge som används:
* **Entitet:** `sensor.battery_optimizer_sonnen_control_mode`
* **Värde:** `"Site Power Limits (EMS v1.35+)"` eller `"Legacy (Manual Mode)"`
* **Attribut:**
  - `software_version`: t.ex. `"1.35.14"`
  - `active_gcp_import_limit`: Hämtas från `GET /api/v2/site/limits`
  - `active_gcp_export_limit`: Hämtas från `GET /api/v2/site/limits`
  - `active_bess_export_limit`: Hämtas från `GET /api/v2/site/limits`

---

## ✅ Verifierings- och Testlista

1. **Enhetstester (`pytest tests/` i battery-optimizer-light-base):**
   - Skapa mock-test i `tests/test_sonnen.py` som simulerar `async_get_software_version()` med `"1.35.14"` och `"1.30.0"`.
   - Verifiera att `is_modern_ems` sätts till `True` vid `>= 1.35.14` och `False` vid äldre versioner.
   - Verifiera att `apply_action` anropar `PUT /api/v2/site/limits` när `is_modern_ems=True`.
2. **Live-verifiering mot användarens batteri (`192.168.107.196`):**
   - Starta om integrationen i Home Assistant.
   - Kontrollera i loggen: `Sonnen kör mjukvara 1.35.14 >= 1.35.14: Aktiverar modernt EMS Site Limits läge!`.
   - Sätt `HOLD` och kontrollera via `GET /api/v2/site/limits` att `p_bess_inv_max_export_limit: 0` är aktivt.

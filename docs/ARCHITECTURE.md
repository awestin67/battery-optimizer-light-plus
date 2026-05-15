# Arkitektur - Home Assistant Integration

**Körtidsmodell och komponentinteraktioner för Battery Optimizer Light Plus.**
Detta dokument beskriver den övergripande arkitekturen för Home Assistant-integrationen, hur hybridmodellen (Moln + Edge) fungerar, och hur modulerna interagerar.

## 1. Systemöversikt (Huvudkomponenter)
Integrationen är byggd som en standard Home Assistant Custom Component men tillämpar en hybridarkitektur där tunga beräkningar görs i molnet medan kritisk säkerhet hanteras lokalt (Edge).

1.  **DataUpdateCoordinator (`coordinator.py`):** Hanterar all asynkron kommunikation med molnet (`aiohttp`). Pollar molnet var 5:e minut, skickar aktuella sensordata (SoC, last, EV-status) och tar emot optimeringsbeslut (`action`, `target_power_kw`).
2.  **PeakGuard (`__init__.py`):** Den lokala effektvakten och säkerhetsfiltret. Lyssnar i realtid på Home Assistants State Machine (via `async_track_state_change_event`) för att omedelbart kunna åsidosätta molnets beslut vid t.ex. effekttoppar eller extrem solexport.
3.  **Batteri-adaptrar (`batteries/`):** Implementerar ett gemensamt gränssnitt (Adapter Pattern) för olika batterityper (Sonnen, Huawei, Homevolt, Solis, Generic). Översätter systemets standardiserade kommandon (`CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`) till enhetsspecifika API-anrop eller HA Service Calls.
4.  **Entiteter (`sensor.py` m.fl.):** Exponerar molnets beslut, lokal status och historik (t.ex. grafdata och besparingar) som standard-entiteter i Home Assistant.

## 2. Exekveringsmodell: Hybrid (Moln + Lokal)
Eftersom Home Assistant fungerar som en "Edge"-klient, är exekveringen uppdelad i två parallella flöden:

### A. Den Långsamma Loopen (Molnet, var 5:e minut)
*   Koordinatorn anropar molnet via `POST /signal`.
*   Molnet räknar ut en 36-timmars MPC-prognos (Model Predictive Control) baserat på priser, väder och historik.
*   Molnet returnerar det optimala beslutet för *de nästkommande 5 minuterna*.
*   Beslutet utvärderas av `PeakGuard`, och om allt är säkert skickas kommandot till det lokala batteriet.

### B. Den Snabba Loopen (Lokalt, realtid)
*   Varje gång husets nätmätare eller batteri ändrar värde (i HA State Machine), triggas `PeakGuard.update()`.
*   Om husets totala last överskrider användarens inställda gräns (`LIMIT_ENTITY`), avbryts molnets plan omedelbart, och batteriet beordras tvingande till `DISCHARGE`.
*   När lasten sjunker under gränsen (`safe_limit`), släpper `PeakGuard` kontrollen och återgår till det senaste kommandot från molnet.

### C. Passivt Läge (Read-Only)
*   Om molnet returnerar `client_mode = "PASSIVE"` (exempelvis om användaren har valt Edge-donglen som sin primära styrenhet), upphör Home Assistant att skicka styrsignaler.
*   Lokal styrning och PeakGuard pausas, och inga Modbus-skrivningar görs. Home Assistant agerar enbart informationspanel (Read-Only) så att dashboards fortsätter visa aktuell status.
*   Vid ett eventuellt nätverksbortfall blockeras fallback-kommandot (`IDLE`) så att integrationen inte oavsiktligt nollställer ett batteri som för tillfället styrs av Edge-donglen.

## 3. Säkerhetsmekanismer & Filter
För att garantera fysisk säkerhet och förhindra slitage på reläer implementerar integrationen flera lokala skydd:

*   **Solar Override (Anti-fladder):** Om solelexporten är massiv (> 400W), tvingas batteriet till `IDLE` (Auto) så att det kan laddas upp av överskottet. För att undvika "fladder" när moln passerar, tillämpas en **3-minuters hysteres** innan denna spärr släpps, *såvida* inte batteriet tvingas ladda ur, varpå spärren släpps direkt för att skydda SoC.
*   **Maintenance Override:** Om batteriets status-sensor (t.ex. växelriktarens felkods-entitet) rapporterar ett ord som matchar `battery_status_keywords` (t.ex. "Service", "Calibrating"), släpper integrationen all kontroll.
*   **Lokal Throttling av Laddning:** Även om molnet ber om `CHARGE`, beräknar PeakGuard tillgängligt utrymme upp till gränsvärdet. Om marginalen är för liten stryps (throttlas) laddningseffekten lokalt innan den skickas till batteriet.
*   **Hardware Reserve (EM_USOC):** För Sonnen-batterier läser integrationen in hårdvarureserven. Om användaren har 5% reserverat för strömavbrott, skalar integrationen om SoC (så att molnet ser 0%) och lokalt nekar alla `DISCHARGE`-kommandon om den fysiska nivån går ner till 5%.

## 4. Batteriabstraktion (Adapter Pattern)
Alla integrationer av nya växelriktare måste följa standardmönstret i `batteries/`. En adapter måste:
1.  Kunna instansieras med `hass`, `device_id` och sensor-ID:n.
2.  Implementera asynkrona mätfunktioner (t.ex. `get_current_soc()`).
3.  Implementera kommandot `apply_action(action: str, target_kw: float)`.

Detta gör det extremt enkelt att lägga till stöd för nya märken, utan att kärnlogiken i `PeakGuard` eller `Coordinator` påverkas.

## 5. Nätverk & Resiliens
Eftersom integrationen styr fysisk utrustning via externa API:er finns strikta krav på nätverkssäkerhet:

*   **Non-blocking I/O:** All molnkommunikation använder `aiohttp` och `asyncio`. Inga blockerande `requests`-anrop förekommer, vilket skyddar Home Assistants Event Loop.
*   **Retries & Fallbacks:** Om molnet går ner eller ger timeout, gör koordinatorn 3 försök (med `asyncio.sleep` emellan). Misslyckas alla försök skickas systemet till `IDLE` (Auto) för att undvika att ett batteri fryser fast i ett `DISCHARGE`- eller `CHARGE`-kommando under ett ström/nätverksavbrott.
*   **Auth-skydd:** Om API-nyckeln ogiltigförklaras (HTTP 401) avbryts uppdateringen direkt utan retries, och kommandot `IDLE` skickas till batteriet, varpå användaren meddelas via loggarna.

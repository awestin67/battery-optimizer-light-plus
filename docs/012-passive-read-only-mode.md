# ADR 012: Passivt "Read-Only" läge för Home Assistant

**Date:** 2026-05-15
**Status:** Accepted

## Context
Enligt [ADR 007](007-dual-client-support-strategy.md) införde vi ett "Split-Brain"-skydd som helt blockerar Home Assistant (V1 `/signal`) om användaren har valt Edge-donglen som aktiv styrenhet. Just nu returnerar backend hårdkodade noll-värden och `action="IDLE"` till HA när detta sker.

Problemet är att många användare har byggt omfattande dashboards i Home Assistant och vill fortsätta se vad systemet gör (aktuell åtgärd, target power, nästa åtgärd, baslast etc.) även om det är Edge-donglen som utför den faktiska Modbus-styrningen. 

Dessutom har HA-integrationen idag en inbyggd säkerhetsmekanism som automatiskt skickar kommandot `IDLE` (Automatic Self-consumption) till växelriktaren om den tappar kontakten med molnet. Om Edge är den aktiva styrenheten får HA absolut inte gripa in och nollställa batteriet vid nätverksbortfall.

## Decision
Vi omvandlar Home Assistant-integrationens roll till att kunna agera "Read-Only" (Passiv) när Edge är vald som huvudklient.

### 1. Backend: Modifiering av Split-Brain skyddet i `/signal` (V1)
Istället för att stenhårt avvisa HA med nollade dummy-värden ska `/signal` returnera det verkliga tillståndet, men markera svaret som passivt och undvika att skriva historik till databasen.
*   **Nytt fält i API:** Vi lägger till `client_mode: str = "ACTIVE"` (standard) i `SignalResponse` (V1).
*   **Passiv logik:** Om `active_client_type == 'Edge'` när HA anropar `/signal`:
    *   Sätt `client_mode = "PASSIVE"`.
    *   Hämta det senaste optimeringsbeslutet från `LAST_OPTIMIZATION_RESULT_CACHE` (som Edge-donglen kontinuerligt uppdaterar) eller kör en "Dry-Run" av optimeraren om cachen är tom.
    *   **Viktigt:** Hoppa över anropet till `db.log_decision` för att undvika att HA skapar dubbla rader i `light_decision_logs`. Dubbla loggar skulle förstöra AI-inlärningen, effektivitetsberäkningen och besparingsstatistiken.

### 2. HA Integration: Passivt läge och Fallback-skydd
Home Assistant-integrationen (Python-koden i `battery-optimizer-light-plus` repot) uppdateras för att läsa och respektera det nya `client_mode`-fältet.
*   **Modbus-blockering:** Om integrationen tar emot `client_mode == "PASSIVE"`, ska den enbart uppdatera sina sensorer i HA (så att dashboards fungerar). Den ska *inte* utföra några Modbus-skrivningar (`CHARGE`, `DISCHARGE`, `HOLD`, `IDLE`).
*   **Deaktivering av Fallback:** Om integrationen befinner sig i passivt läge och förlorar anslutningen till molnet (t.ex. timeout), ska den **inte** skicka fallback-kommandot `IDLE` till växelriktaren. Den förblir tyst och låter Edge-donglen sköta all felhantering.

## Consequences
*   **Sömlös Dashboard-upplevelse:** Användare kan byta till Edge-donglen utan att deras befintliga HA-dashboards slutar fungera. Sensorerna fortsätter visa exakt vad optimeraren (via Edge) gör.
*   **Säkerhet mot krockar:** Den farliga krocken där HA tappar internet och tvingar växelriktaren till `IDLE` medan Edge försöker styra elimineras helt.
*   **Ren historik:** Genom att HA inte loggar sina "Read-Only" anrop till databasen bibehålls exaktheten i `light_decision_logs`.
*   **Krav på uppdatering:** För att krockskyddet vid offline-läget (Fallback) ska fungera måste användare uppdatera sin HA-integration till en version som stöder `client_mode`.
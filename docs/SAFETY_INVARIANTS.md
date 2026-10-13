# Safety Invariants

**Rules that must never be broken.**
This covers critical system invariants, physical safety constraints (e.g., hardware/battery limits), and non-negotiable code rules for the Home Assistant integration.

## 1. Effektvakt (PeakGuard) & Lokal Säkerhet
* **Molnets HOLD respekteras:** PeakGuard får inte lokalt ändra molnets `HOLD` till `IDLE` (t.ex. vid solelexport). En `HOLD` kan vara ekonomiskt motiverad (t.ex. morgonexport), så endast peak-skydd, throttling av laddning, underhållsläge eller extern paus får åsidosätta molnets beslut lokalt.
* **Maintenance Mode:** Systemet MÅSTE omedelbart släppa all styrning av batteriet om växelriktarstatusen (`battery_status_sensor`) matchar något av de konfigurerade nyckelorden för underhåll (t.ex. "Service", "Calibrating").
* **Lokal Throttling:** Om backend begär laddning (`CHARGE`), men lasten närmar sig PeakGuard-gränsen, MÅSTE systemet lokalt strypa (throttle) laddningseffekten för att förhindra att batteriet orsakar en effekttopp.

## 2. Home Assistant State Machine & Data
* **Inga Blinda Casts:** Tillstånd som hämtas via `hass.states.get()` MÅSTE alltid valideras. Om `state` är `STATE_UNKNOWN`, `STATE_UNAVAILABLE` eller `None`, får den under inga omständigheter konverteras med `float()` eller `int()` då detta kraschar event-loopen.
* **Non-Blocking I/O:** All nätverkstrafik MÅSTE gå via `aiohttp` och `asyncio`. Blockerande anrop (t.ex. `requests.get()`, `time.sleep()`) i Home Assistants huvudtråd är strikt förbjudna.

## 3. Moln-Synk & Resiliens (Coordinator)
* **Krasch-säkerhet (Fallback till IDLE):** Om uppkopplingen till molnet bryts (efter max 3 försök med 500-fel eller timeouts), eller om API-nyckeln avvisas (401 Unauthorized), MÅSTE koordinatorn kasta `UpdateFailed` och skicka kommandot `IDLE` (Auto) till batteriet. Batteriet får *aldrig* lämnas låst i ett tvingat `HOLD` eller `CHARGE` vid långvariga nätverksbortfall. **Undantag:** Om integrationen är i `PASSIVE`-läge (eftersom en Edge-klient sköter styrningen) får *inget* kommando skickas vid nätverksavbrott.
* **Hårdvarureserv (EM_USOC / Min SoC):** Integrationen måste strikt respektera den fysiska reservnivån (t.ex. Sonnens Backup-reserv). Den skickade SoC-nivån måste skalas lokalt så att molnet alltid ser 0% när batteriet fysiskt når användarens reservgräns. Urladdningar begärda av molnet ska avbrytas (översättas till `IDLE`) om denna reservnivå nås.

## 4. Säkerhet & Loggning
* **Inga hårdkodade hemligheter:** API-nycklar och lokala inloggningstokens får **aldrig** hårdkodas i källkoden. De hanteras exklusivt via Home Assistants inbyggda `ConfigEntry`-struktur (`.storage`).
* **Maskering i loggar:** Känslig information (Som API-nycklar och Sonnen Auth-Tokens) får aldrig loggas i klartext. Vid felsökningsloggning (Debug) ska sådana strängar alltid maskeras om de skrivs ut.

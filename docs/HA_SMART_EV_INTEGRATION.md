# Home Assistant: Smart EV Charging Integration

Den här guiden förklarar hur du integrerar den nya prissmarta elbilsladdningen ("Smart EV Charging") från molnet till din lokala Home Assistant.

## Två Samexisterande Laddmetoder
Batterioptimeraren har nu två olika sätt att styra elbilsladdningen. De fungerar utmärkt att använda separat eller till och med samtidigt (t.ex. för två olika bilar):

1. **Schemalagd Laddning (Den äldre metoden, ADR-014)**
   - Manuell styrning där du anger i molnets webbgränssnitt exakt vilka klockslag bilen ska ladda (t.ex. "Varje natt kl 01:00 till 05:00").
   - Styrs helt från molnet. Din Home Assistant behöver bara övervaka om `is_ev_charging_hour` är satt i svaret från hjärtslaget.

2. **Smart EV Charging (Den nya dynamiska metoden, ADR-020)**
   - **Prissmart laddning som ersätter behovet av tjänster som Tibber.**
   - Home Assistant anropar molnet exakt när du kopplar in bilen och ber om den *billigaste möjliga tidslinjen* för att nå ett visst antal kWh innan en viss avresetid.
   - Molnet returnerar exakta start- och stopptider. **Home Assistant tar hand om att faktiskt starta och stoppa laddboxen lokalt enligt denna plan.**

> [!NOTE]
> Båda metoderna samoptimeras automatiskt med ditt husbatteri. Om bilen planeras att ladda (oavsett metod) tas detta med i baslast-prognosen, och huvudsäkringen skyddas genom virtuell lastbalansering mot bilens förväntade förbrukning.

---

## Förberedelser: Nödvändiga Sensorer i Home Assistant
För att bygga en robust integration skapar du Helpers (variabler) i Home Assistant som representerar din bils laddbehov. Integrationen kommer sedan läsa av dessa och skicka in värdena till molnet.

### 1. Helpers (Konfiguration för API-anropet)
Home Assistant-integrationen behöver veta dina laddpreferenser. Det enklaste är att du skapar följande Helpers (Hjälpare) i Home Assistant för varje bil:
- `input_text.ev_name_car1`: Namnet på bilen (t.ex. "Volvon"). Detta används som ID i molnet så du kan skilja på bilarna i webbgränssnittet.
- `input_number.ev_target_kwh_car1`: Hur mycket energi som ska laddas (t.ex. 27.0). Skala: 0 till 100 med steg om 0.1.
- `input_datetime.ev_departure_time_car1`: När bilen ska vara färdigladdad (t.ex. 07:00). Ska endast visa tid (Time).
- `input_number.ev_max_charge_kw_car1`: Bilens maximala laddhastighet (t.ex. 11.0).

*(Och om du har en andra bil skapar du givetvis en till uppsättning, t.ex. `_car2`)*

**Hur kopplar jag dessa till integrationen?**
För att integrationen ska veta vilka Helpers den ska läsa av, går du in under Inställningar -> Enheter och Tjänster i Home Assistant. Klicka på "Konfigurera" på din Battery Optimizer Light Plus-integration, och välj de Helpers du precis skapat i dropdown-menyerna för elbilsladdning. 

Integrationen kan därefter samla in dessa värden och bygga det JSON-schema som skickas till molnet när du vill planera en laddning.

### 2. Sensorer (För Triggrar och Hjärtslag)
För att integrationen ska veta *när* den ska anropa API:t, och *när* bilen drar ström, behöver den följande sensorer:
- `binary_sensor.ev_cable_connected`: En sensor från din laddbox som blir `on` när kabeln ansluts. Detta är själva startskottet (triggern) för integrationen att bygga sin JSON och hämta en plan.
- `binary_sensor.ev_is_charging`: En sensor som är `on` *endast* när bilen faktiskt drar ström. Detta värde skickas med som `"is_ev_charging"` i det ordinarie 5-minuters hjärtslaget (`/v2/signal`).

---

## Steg 1: HA-integrationen begär en laddplan
Vår Home Assistant-integration hanterar kommunikationen med molnet automatiskt. Integrationen gör ett REST API-anrop till molnet för att generera den optimala laddplanen (till exempel när kabeln ansluts, eller via ett tjänsteanrop i integrationen).

När integrationen skickar anropet räknar molnet ut när det är billigast att ladda och skickar tillbaka en komplett tidslinje.

**Endpoint:** `POST https://din-moln-url.com/api/ev/plan`
**Headers:**
- `Content-Type: application/json`

**Payload (Exempel):**
```json
{
  "api_key": "DIN_API_NYCKEL",
  "cars": [
    {
      "id": "Bilen",
      "target_kwh": 27.0,
      "departure_time": "07:00",
      "max_charge_kw": 11.0
    }
  ]
}
```
*Tips: Integrationen bygger denna payload dynamiskt. Värden som `target_kwh` och `departure_time` hämtas från entiteter i HA innan anropet görs.*

### Hantering av Flera Bilar (Bil 1 vs Bil 2)
Molnet och integrationen har fullt stöd för att styra flera bilar oberoende av varandra. Det är värdet `"id"` i payloaden som skiljer dem åt.

Om hushållet har två bilar hanterar integrationen helt enkelt dubbla uppsättningar av variabler (t.ex. för Bil 1 och Bil 2).

**Du kan göra anropet på två olika sätt:**
1. **Separat (När de kopplas in vid olika tillfällen):** 
   Integrationen gör ett anrop för "Bil 1" när den kopplas in. Om "Bil 2" kopplas in senare på kvällen, gör integrationen ett separat anrop för den med `"id": "Bil 2"`. Molnet är smart och *lägger till* det nya schemat utan att radera schemat för "Bil 1".
2. **Samtidigt (Om de alltid kopplas in samtidigt):**
   Integrationen kan skicka in båda bilarna i samma anrop:
   ```json
   {
     "api_key": "DIN_API_NYCKEL",
     "cars": [
       { "id": "Bil 1", "target_kwh": 27.0, "departure_time": "07:00", "max_charge_kw": 11.0 },
       { "id": "Bil 2", "target_kwh": 15.0, "departure_time": "08:00", "max_charge_kw": 11.0 }
     ]
   }
   ```
   Då samoptimeras båda bilarna direkt för att minimera risken att de laddar exakt samtidigt och överbelastar huvudsäkringen!

---

## Steg 2: Ta emot och exekvera tidslinjen lokalt
Molnet kommer svara direkt med den billigaste och mest optimerade tidslinjen:
```json
{
  "schedules": {
    "Bilen": [
      {
        "start": "2026-07-19T02:00:00+02:00",
        "end": "2026-07-19T04:30:00+02:00",
        "charge_kw": 11.0
      }
    ]
  }
}
```
Denna tidslinje garanterar att din bil får önskad energi till lägsta möjliga pris, utan att överbelasta din huvudsäkring! 
*(Schemat sparas även automatiskt i molnets databas och visas read-only i webbgränssnittet under "Elbilsladdning och Effektvakt").*

**I Home Assistant:**
Integrationen tar emot detta svar och gör tidslinjen tillgänglig för dig i Home Assistant (exempelvis som ett attribut på en sensor). Eftersom det är du som har bäst koll på din specifika laddbox (eller bil), är det **du som användare som hanterar själva styrningen**. 

Du skapar en automation i Home Assistant som läser av tidslinjen och skickar "Start" eller "Stop" till din laddbox när klockan når de angivna tiderna i schemat.

### Best Practice: Hämta ett nytt schema när nya elpriser släpps
Vår molntjänst är "stateless", vilket betyder att det är **din Home Assistant** som äger informationen om bilens faktiska behov just nu.
Om du anslöt kabeln klockan 09:00, byggdes schemat ovan med uppskattade "dummy-priser" för natten, eftersom morgondagens sanna elpriser inte släpps från Nordpool förrän ca 13:00.

För att få det absolut sista, millimeterexakta schemat, rekommenderas du att skapa en enkel automation i Home Assistant som tvingar integrationen att be om en ny plan på eftermiddagen:

**Exempel på HA-automation (Re-optimering):**
- **Trigger:** Klockan blir 13:30 (eller när sensorn `nordpool_kwh_se3_sek` får attributet `tomorrow_valid: true`).
- **Condition:** Kabeln är fortfarande ansluten (`binary_sensor.ev_cable_connected` är `on`).
- **Action:** Anropa integrationens tjänst för att hämta ny laddplan. 
*(Eftersom det anropet läser bilens uppdaterade batterinivå, kommer `target_kwh` automatiskt vara lägre om bilen av misstag råkat ladda något under förmiddagen!)*

---

## Steg 3: Ordinarie Hjärtslag (VIKTIGT!)
Ditt existerande 5-minuters hjärtslag från integrationen mot molnet (`POST /v2/signal`) ska rulla på precis som vanligt.
När din lokala automation *väl* slår på laddboxen enligt tidslinjen under natten, måste hjärtslaget skicka med `"is_ev_charging": true` i payloaden.

Det är detta som informerar molnet i realtid att *"Nu drar bilen ström"*, varpå molnet automatiskt låser husbatteriet (`action = "HOLD"`) så att ditt dyra husbatteri inte oavsiktligt laddas ur rakt in i elbilen.

### Dynamisk Skrotning (Felsäkerhet)
Om molnet har skapat en tidslinje, men bilen av någon anledning inte drar någon ström (dvs. integrationen skickar fortfarande `"is_ev_charging": false` i hjärtslaget trots att klockan passerat `start`-tiden), så agerar molnet smart: 
Efter 60 minuter inser molnet att laddningen uteblivit, och den **"skrotar" automatiskt planen** för resten av natten. Detta görs för att frigöra ditt husbatteri så att huset kan dra nytta av batteriet istället för att hålla det låst helt i onödan.

This project was made by psimcak, moaks, dkolarov, msimek.

## ▶ Run locally (Kraków + Praha)

Everything runs on one laptop: no accounts, no cloud. The processed data in `data/processed/` is committed, so you don't need to rebuild it.

**Prerequisites:** [uv](https://docs.astral.sh/uv/) (`brew install uv` or `pip install uv`; uv installs Python 3.12 itself) and Node.js ≥ 20 with npm.

**1. Engine (API), terminal 1**
```bash
cd engine
uv sync
uv run uvicorn app.main:app --port 8000
```
The first start trains the neighbourhood-type model (about 10 s).
- Check http://localhost:8000/api/health: both cities should report `dataSource: real`.
- API docs: http://localhost:8000/docs

**2. Web app, terminal 2**
```bash
cd web
npm ci
npm run sync-data                      # copies grids, static exports and fixtures into web/public/data
printf 'VITE_API_URL=http://localhost:8000\nVITE_USE_FIXTURES=0\n' > .env.local
npm run dev
```
Open http://localhost:5173. Kraków is at `/krakow`, Praha at `/praha`.

**Demo on a phone on the same Wi-Fi**
1. Start the engine with `--host 0.0.0.0`.
2. Set `VITE_API_URL=http://<laptop-IP>:8000` in `web/.env.local`.
3. Run `npm run dev -- --host`.
4. Open `http://<laptop-IP>:5173` on the phone.

**Other modes**
- No engine: `VITE_STATIC_FALLBACK=1` (scores computed in the browser from `criteria_scores.json`; no commute, twins or live data).
- Contract fixtures only: `VITE_USE_FIXTURES=1`.
- Engine in Docker: `docker compose up --build`.

**Tests**
- Engine: `cd engine && uv run pytest -q`
- Web: `cd web && npm run build` (includes the locale check)
- Smoke test: `cd web && npx playwright test`

**Rebuild the data** (optional, ~45 min, needs Java 21): `cd pipeline && make data CITY=all`

More: `docs/ARCHITECTURE.md` · `docs/DATA_SOURCES.md` · `docs/ML.md` · `docs/DECISIONS.md` · `contracts/` (API + data contract).

---


# MASTER PROMPT: "Kompas" (working title) · Kraków + Praha
### HackYeah 2026 · Category: SMART CITY (sponsor: Bank Pekao) · 24-hour build · UI in Polish, Czech and English

> **How to use this file.** Paste the whole file into the orchestrator agent (e.g. Claude Code at the repo root). There are exactly **three workstreams: A, B and C** (§11). Each workstream agent gets the whole file, followed by one line: *"You are Workstream A / B / C."* Everyone integrates through the contracts in §7, so nobody waits for anybody.
>
> *"Kompas" is the same word in Polish and Czech. The team may rename it.*

---

## 0. Your role

You are the **lead engineer and orchestrator** of a hackathon team (up to 6 people plus AI agents) with **~24 hours** to ship a working, **deployed** product that wins the SMART CITY category. The product covers **two cities, Kraków and Praha**, with one engine, one UI and three languages.

You own: the repo skeleton, shared contracts (§7), city configs, integration, timeline (§9), scope cuts (§10), quality gate (§12) and the **pitch + submission package** (§13). You delegate exactly three workstreams (§11):

- **A**: data pipeline, both cities
- **B**: scoring engine + ML + API
- **C**: frontend + UX/design + content and translations (pl/cs/en)

Rules for you:
1. **Contracts first.** Within the first hour, commit `config/indicators.yaml`, `config/cities/krakow.yaml`, `config/cities/praha.yaml`, `contracts/openapi.yaml`, generated TS types and JSON fixtures for **both** cities. After M1, change contracts only additively.
2. **Never block.** Every workstream starts on fixtures/mocks and swaps in real data when it lands.
3. **Kraków first, Praha right behind.** Kraków is the event city and the reference implementation. Praha reuses the same city-agnostic core (OSM + GTFS) and adds its own adapters. Praha proves the product scales.
4. **Main is always deployable.** Integrate at every milestone. A working demo matters more than more features.
5. **Optimize for the judging criteria** (§1). Each feature must clearly serve one of them.
6. **Log decisions** in `docs/DECISIONS.md`, one line each: time, decision, reason, fallback used.

---

## 1. Hackathon facts (non-negotiable)

**Category brief (verbatim essence):** *"Solutions that help cities function better in everyday conditions: improving mobility, resource management, communication with citizens, and crisis response… mobility, energy, urban data, public services, quality of life… Build a tool, application, system, or prototype that addresses a real problem… Build something that makes everyday life in a city easier."*

**Time window (from T&C):** start no earlier than **Oct 3, 23:00**; submit no later than **Oct 4, 23:00**. This may be a typo, since HackYeah usually runs 11:00 → 11:00. **Confirm the window on Discord/HackTribe at H0.** All planning below uses relative hours H0–H24. The internal submit target is **H22**.

**Submission (HackTribe, English or Polish):** project title, team name, team members (1–6), project description, and a **PDF of at most 10 slides** (screenshots, repo link, demo link, graphics).

**Judging criteria → our optimization targets:**

| Criterion | Weight | How we win it |
|---|---|---|
| Idea & Innovation | 30% | Persona-driven livability matching with 5-emoji importance; commute heat map from *your own* places; neural "neighbourhood type" classifier; **"twin neighbourhoods" across Kraków ↔ Praha**; "your budget buys ~X m² here"; explainable scores; no login, shareable URL. |
| Relation to Category | 20% | Mobility (ZTP + PID GTFS, commute times), urban open data from both cities, public services (schools, clinics), quality of life, communication with citizens in their own language. Optional city view of service gaps (resource management). |
| Practical Applicability / Usability | 20% | Real data from two capitals of culture and study; answer in ≤3 clicks; mobile-first; Polish, Czech or English; for students, workers, parents, pregnant people and seniors; useful for anyone moving between the cities. |
| Design | 20% | Calm, friendly UI; clear map and legend; ranking cards with "why"; radar comparison; accessible (WCAG AA). |
| Completeness & Implementation Value | 10% | Deployed demo, public repo, README, documented data sources, tests, backup video; second city shows a reusable architecture. |

The project needs ≥50% of points in phase 1 to be eligible. Finalists then pitch live in phase 2. Both the PDF and the live demo must stand on their own.

---

## 2. Product vision

**One-liners:**
- **PL:** *"Znajdź miejsce w mieście, które pasuje do Twojego życia."* (…w Krakowie / …w Pradze)
- **CS:** *"Najděte místo ve městě, které sedí vašemu životu."* (…v Praze / …v Krakově)
- **EN:** *"Find the part of the city that fits your life."*

**Problem.** City information is scattered:
- **Kraków:** ZTP transit, MSIP noise maps, GIOŚ air, the MEN school register, RCN prices, Otwarte Dane parks.
- **Praha:** PID transit, IPR Geoportál, ČHMÚ air, the MŠMT school register, the NRPZS health register, the MF rent map, the Police crime map.

A young person moving to a city, a family looking for a flat, a pregnant woman or a senior has to assemble this by hand, often in a foreign language. Nobody tells them *which neighbourhoods fit their priorities* or *why*.

**Solution.** A **single web page with no account or login**:
1. Pick a city: Kraków or Praha.
2. Pick who you are (persona preset).
3. Rate the importance of each criterion with **5 emoji**.
4. Optionally add "my places" (work, university, a child's school) and hard limits (budget, max commute).
5. A separate **scoring engine** (Python service) computes a **match % for every ~100 m hexagon** of the city and ranks neighbourhoods and districts.
6. Results appear as a **heat map, ranked list, scales, radar comparison, commute heat map, AI neighbourhood-type label** and **twin neighbourhoods in the other city**, each with a plain-language "why".

**Product principles:**
- One page, three clicks to value.
- No login and privacy by design: all state lives in the URL and can be shared. No cookies, no tracking.
- Explainable: every score breaks down into real values ("tram 3 min walk", "noise ~62 dB").
- Honest data: every number has a visible source and date. Missing data is labelled, never invented.
- **Three languages: `pl`, `cs`, `en`.** Default language follows the city (Kraków → `pl`, Praha → `cs`). The user can switch any time, and any language works with any city.
- Built on OpenStreetMap plus each city's own open data and APIs.

---

## 3. User experience specification

### 3.1 Flow (step titles in PL / CS / EN)
0. **City.** "W którym mieście?" / "Které město?" / "Which city?" Two big cards: Kraków, Praha. The URL path sets it too (`/krakow`, `/praha`). The landing page language comes from the browser (pl/cs/en, else pl).
1. **Who you are.** "Kim jesteś?" / "Kdo jste?" / "Who are you?" Persona cards (§3.4).
2. **What matters.** "Co jest dla Ciebie ważne?" / "Co je pro vás důležité?" / "What matters to you?" 13 criteria rows, each with a 5-emoji picker plus "skip", pre-filled from the persona.
3. **Your places and limits.** "Twoje miejsca i granice" / "Vaše místa a limity" / "Your places and limits". Optional and skippable:
   - Up to 3 anchors with address search, a mode (🚋 transit / 🚲 bike / 🚶 walk) and an importance.
   - Hard limits: budget in local currency, max commute, must-have within N minutes' walk.
4. **Results.** Map plus ranking, with a detail drawer. The filter panel stays editable and results update live (250 ms debounce). A city switcher in the header keeps persona, levels and language.

### 3.2 Emoji importance scale (exactly 5 emoji + "skip")

| Level | Emoji | PL | CS | EN | Weight W |
|---|---|---|---|---|---|
| 0 | (greyed) | Pomiń | Přeskočit | Skip | 0 |
| 1 | 😐 | Mało ważne | Málo důležité | Barely matters | 1 |
| 2 | 🙂 | Miło by było | Bylo by fajn | Nice to have | 2 |
| 3 | 😊 | Ważne | Důležité | Important | 3 |
| 4 | 😍 | Bardzo ważne | Velmi důležité | Very important | 5 |
| 5 | 🤩 | Kluczowe | Zásadní | Essential | 8 |

The weights are deliberately non-linear and configurable. Each emoji button has an `aria-label` and a visible tooltip in the current language.

### 3.3 Criteria (13)

**Bold** = P0 indicator. Sources: **K** = Kraków, **P** = Praha, **OSM** = both.

| id | Emoji | PL | CS | EN |
|---|---|---|---|---|
| `commute` | 🧭 | Dojazd do moich miejsc | Dojezd do mých míst | Commute to my places |
| `transit` | 🚋 | Komunikacja miejska | Veřejná doprava (MHD) | Public transport |
| `active` | 🚲 | Rower i spacery | Kolo a chůze | Cycling & walking |
| `green` | 🌳 | Zieleń | Zeleň | Green space |
| `education` | 🎓 | Edukacja | Vzdělávání | Education |
| `family` | 🧸 | Rodzina i dzieci | Rodina a děti | Family & kids |
| `safety` | 🛡️ | Bezpieczeństwo | Bezpečnost | Safety |
| `price` | 💰 | Przystępne ceny | Dostupné bydlení | Affordability |
| `shops` | 🛒 | Zakupy i usługi | Nákupy a služby | Shops & services |
| `health` | 🏥 | Zdrowie | Zdraví | Health |
| `environment` | 🌬️ | Cisza i czyste powietrze | Klid a čisté ovzduší | Quiet & clean air |
| `leisure` | 🎭 | Kultura, sport i gastronomia | Kultura, sport a gastronomie | Culture, sport & food |
| `accessibility` | ♿ | Dostępność | Bezbariérovost | Accessibility |

| id | Indicators | Sources |
|---|---|---|
| `commute` | **door-to-door minutes from hex to each anchor** (transit+walk weekday 08:00; bike; walk) | OSM + GTFS (K: ZTP, P: PID) via r5py |
| `transit` | **walk min to nearest stop**, **departures/h within 500 m (Mon–Fri 7–9)**, distinct lines within 500 m, tram stop within 500 m, **rail/metro station walk min** (P: metro + S-trains; K: SKA/rail), night service (departures 23–05) | GTFS, OSM |
| `active` | **cycle-infrastructure km within 1 km**, intersection density (walkability), bike racks within 300 m, river embankments / pedestrian zones, bike-share stations (P2) | OSM; K: ZTP hub; P: bike-share GBFS (opt.) |
| `green` | **green-area share within 500 m**, **walk min to park ≥ 2 ha**, forest/meadow within 1 km | OSM; K: Otwarte Dane (parki); P: IPR zeleň, Golemio gardens |
| `education` | **walk min to nursery, kindergarten, primary school**, secondary school, university, library | K: MEN register XLSX + Otwarte Dane (żłobki); P: MŠMT register XML; OSM |
| `family` | **playgrounds within 500 m**, paediatrician walk min, pools/sports for kids | OSM; P: Golemio playgrounds, NRPZS |
| `safety` | **district crime rate per 1,000 residents**, street-lighting share (OSM `lit=yes`) | K: Bezpieczny Kraków; P: Police ČR crime map |
| `price` | **K: median transaction price zł/m² for apartments, last 24 months** · **P: median rent Kč/m²/month** (inverted percentile within city); discount-grocery access | K: RCN (GUGiK); P: MF rent price map |
| `shops` | **walk min to supermarket**, pharmacy, post office / parcel locker, bakery, marketplace, ATM, shop count within 10 min | OSM (P: pharmacies also NRPZS) |
| `health` | **walk min to GP/POZ clinic**, pharmacy, hospital with ER, maternity ward, dentist | K: OSM (+ NFZ opt.); P: **NRPZS** (CSV with GPS + specialties) |
| `environment` | **noise (road + tram + rail)**, **PM2.5/PM10**, distance to major roads, industrial land within 1 km | K: MSIP noise maps + GIOŚ (IDW); P: IPR noise maps + ČHMÚ (1×1 km 5-yr avg grid / stations) |
| `leisure` | restaurants/cafés within 10 min, culture venues, sports facilities/gyms, nightlife | OSM |
| `accessibility` | **share of nearby stops/trips wheelchair-accessible**, benches within 300 m, slope (P2) | GTFS, OSM, DEM (opt.) |

### 3.4 Persona presets (importance levels 0–5; identical in both cities)

Persona labels:

| Persona | PL | CS | EN |
|---|---|---|---|
| 🎒 | Student/ka | Student/ka | Student |
| 💼 | Pracuję | Pracuji | Working |
| 👨‍👩‍👧 | Rodzic | Rodič | Parent |
| 🤰 | W ciąży | Těhotná | Expecting |
| 🧓 | Senior/ka | Senior/ka | Senior |
| ✏️ | Własny profil | Vlastní profil | Custom |

| criterion | 🎒 | 💼 | 👨‍👩‍👧 | 🤰 | 🧓 | ✏️ |
|---|---|---|---|---|---|---|
| commute | 5 | 5 | 3 | 3 | 1 | 3 |
| transit | 5 | 4 | 3 | 4 | 4 | 3 |
| active | 3 | 4 | 2 | 2 | 3 | 3 |
| green | 2 | 3 | 5 | 4 | 4 | 3 |
| education | 1 | 0 | 5 | 3 | 0 | 3 |
| family | 0 | 0 | 5 | 4 | 0 | 3 |
| safety | 3 | 3 | 5 | 4 | 5 | 3 |
| price | 5 | 4 | 3 | 3 | 3 | 3 |
| shops | 3 | 4 | 4 | 4 | 5 | 3 |
| health | 1 | 2 | 4 | 5 | 5 | 3 |
| environment | 2 | 3 | 4 | 5 | 4 | 3 |
| leisure | 5 | 4 | 1 | 1 | 3 | 3 |
| accessibility | 0 | 0 | 2 | 4 | 5 | 3 |

**Persona-specific tweaks** (`indicatorWeights`, `walkFactor` in `indicators.yaml`):
- **Student:** education counts only university and library; night service gets double weight. Suggested anchor "My university", picked from OSM `amenity=university` in the selected city (never hardcode the list).
- **Working:** suggested anchor "Work".
- **Parent:** education counts nursery, kindergarten and primary school; family counts playgrounds; anchors "Work" and "Child's school".
- **Expecting:** health counts maternity ward, gynaecology and GP; education counts nursery; accessibility counts low-floor vehicles and benches. `walkFactor 1.3`.
- **Senior:** health counts GP, pharmacy and hospital; accessibility counts benches, low-floor vehicles and slope; leisure counts culture and parks, not nightlife. `walkFactor 1.35`.

### 3.5 Hard filters
- **Price limit in local currency.**
  - Kraków (buy): `maxPricePerM2` in zł/m². Budget helper: total budget ÷ m².
  - Praha (rent): `maxRentPerM2` in Kč/m²/month. Budget helper: monthly rent ÷ m².
  - The detail drawer shows the reverse: *"Za Twój budżet: ~48 m²"* / *"Za váš rozpočet: ~48 m²"*.
- `maxCommuteMinutes` per anchor.
- `mustHave[]`: POI category + max walk minutes.
- `maxNoiseDb` (optional).
- **Relax hint** when nothing passes: the engine reports which single filter, if removed, restores the most places, in the current language.

### 3.6 Result views
- **Map** (MapLibre, OSM vector basemap). H3 hex layer with three modes:
  - **Match %**: sequential, colour-blind-safe palette.
  - **Commute time**: bands ≤10/20/30/45/60 min from the selected anchor, per mode.
  - **Single criterion**: one chosen criterion.

  Non-passing cells are hatched grey. The map also shows top-10 numbered pins, anchor pins, district outlines and an always-visible legend.
- **Ranking panel**, tabs *Places* and *Districts* (Kraków: 18 dzielnic; Praha: 57 městských částí). Each card shows:
  - rank, name, district, match %
  - mini bars for top criteria
  - 2 highlights and 1 warning
  - commute minutes to anchors
  - local price indicator
  - "Compare" checkbox
- **Detail drawer:**
  - match %
  - **radar** vs the city median
  - indicator table with **scales**
  - nearest amenities with walk minutes
  - commute times
  - budget → m²
  - **neighbourhood-type badge** with probability
  - **live air quality** (K: GIOŚ, P: ČHMÚ/Golemio)
  - "Similar places" in the same city
  - **"Twin neighbourhoods"** in the other city: *Bliźniacze okolice / Dvojčata čtvrtí / Twin neighbourhoods*
- **Compare** (2–3 places, same city): overlaid radar plus table.
- **About the data** (*O danych / O datech / About the data*): sources per city, licences, fetch dates, methodology, limitations.
- **(Could) City view:** service gaps, i.e. population vs access.

### 3.7 State and sharing
URL = state: `/{city}?v=1&lang=…&p=persona&w=…&a=…&f=…&mode=…&sel=…`. The "Share" button copies the link. Nothing is persisted on the backend.

### 3.8 Design system, languages and accessibility
- **Layout.** Mobile-first. Desktop: filters left, map centre, results right. Mobile: full-screen map with a results bottom sheet and a filter sheet.
- **Tone and branding.** Warm, calm, trustworthy. One accent colour plus neutral greys. Don't put the sponsor's logo or branding inside the app, and don't imply endorsement.
- **Palettes.** Sequential colour-blind-safe palette for scores, categorical palette for archetypes. The legend is always visible.
- **Accessibility.** WCAG AA contrast, full keyboard navigation, visible focus, `aria-label` on emoji controls, `prefers-reduced-motion` respected. Lighthouse accessibility ≥ 90.
- **Locale formatting.** Use `Intl` with the UI locale and the **city currency**: `pl-PL` "12 450 zł/m²"; `cs-CZ` "385 Kč/m²/měs."; `en` "PLN 12,450/m²". Distances in minutes and metres.
- **Encoding.** UTF-8 everywhere. Test Polish "ąćęłńóśźż" and Czech "ěščřžýáíéůúťďň" in fonts, search and sorting (`Intl.Collator`).
- **States.** Every view needs empty, loading and error states in all three languages.

---

## 4. Data sources (research done 2026-10-03; **re-verify each with a real request at H0–H1**)

### 4a. Common (both cities)

| Key | What | URL | Notes |
|---|---|---|---|
| `osm_krakow` | OSM extract for Małopolskie (192 MB) | https://download.geofabrik.de/europe/poland/malopolskie-latest.osm.pbf | **P0.** Clip to the city + 5 km routing buffer. ODbL: show "© OpenStreetMap contributors". |
| `osm_praha` | OSM extract for Středočeský kraj **with Praha** (172 MB) | https://download.geofabrik.de/europe/czech-republic/stredocesky-latest.osm.pbf | **P0.** Same as above. |
| `overpass` | Ad-hoc OSM queries | https://overpass-api.de/api/interpreter | Quick checks only; prefer the PBFs. |
| `basemap` | Vector basemap, no key | https://tiles.openfreemap.org/styles/positron (also `liberty`, `bright`) | **P0.** Never hammer tile.openstreetmap.org. |
| `geocode` | Address search | Local index from city address points (K: MSIP EMUiA, P: RÚIAN). Fallback: https://photon.komoot.io/api/?q=…&bbox=… | **P0.** Nominatim only at ≤1 req/s with a User-Agent. |

### 4b. Kraków

| Key | What | Access / URL | Notes / priority |
|---|---|---|---|
| `gtfs_ztp` | Static timetables, bus + tram | https://gtfs.ztp.krakow.pl/GTFS_KRK_A.zip · https://gtfs.ztp.krakow.pl/GTFS_KRK_T.zip | **P0.** Merge both feeds for routing. |
| `gtfs_rt_ztp` | Live vehicles, delays, alerts | `https://gtfs.ztp.krakow.pl/VehiclePositions_{A,T}.pb`, `TripUpdates_{A,T}.pb`, `ServiceAlerts_{A,T}.pb` | P2: live departures. |
| `ztp_hub` | Bike racks, shelters, mobility points, paid parking, fare zones, pedestrian access to stops | https://ztpk-gmk-2.hub.arcgis.com/ (ArcGIS REST `/query?where=1=1&outFields=*&f=geojson`) | P1. |
| `krk_open` | Kraków Otwarte Dane (~140 datasets: parki miejskie, parki kieszonkowe, żłobki samorządowe, SIM…) | https://otwartedane.um.krakow.pl/ | **P0/P1.** Check format and licence per dataset. |
| `msip` | Districts (18 dzielnic), address points EMUiA, buildings, **noise maps**, fountains, registrations, zoning | SHP/GeoJSON/DXF + WFS: https://msip.krakow.pl/228340,artykul,katalog-danych.html | **P0.** Districts, addresses and noise. |
| `safety_krk` | "Bezpieczny Kraków" crime by district | https://bezpiecznykrakow-gmk.hub.arcgis.com/ | **P0** (district level). Look for Feature Services. Fallback: cited transcription. |
| `gios` | Air quality, REST v1 | https://api.gios.gov.pl/pjp-api/v1/rest/ (`/station/findAll`, `/station/sensors/{id}`, `/data/getData/{sensorId}`, `/aqindex/getIndex/{stationId}`); Swagger: https://api.gios.gov.pl/pjp-api/swagger-ui/index.html | **P0.** **2 req/min** on most endpoints, so cache. Cite "GIOŚ". |
| `men_schools` | All schools/kindergartens with type + address (SIO, as of 30.09.2025) | XLSX, CC BY 4.0: https://api.dane.gov.pl/resources/1254769,wykaz-szko-i-placowek-oswiatowych-wg-stanu-bazy-sio-na-30092025/file · dataset https://dane.gov.pl/pl/dataset/839 | **P0.** Filter to Kraków (powiat TERYT 1261; verify). Geocode via EMUiA. ⚠ The RSPO REST API (https://api.rspo.gov.pl/) now requires an access request; the old open API ended 2026-03-02. Don't use it. |
| `rcn` | Real-estate transaction prices | WMS/WFS https://mapy.geoportal.gov.pl/wss/service/rcn · info https://www.gov.pl/web/gugik/rcn-dla-362-powiatow-dostepny-w-serwisie-wwwgeoportalgovpl | **P0 for price.** Verify Kraków coverage. Use apartments from the last 24 months; median zł/m² over an H3 k-ring. |
| `nfz` | Waiting times | https://api.nfz.gov.pl/app-itl-api/ (`/queues?province=06`, małopolskie; verify) | P2. |
| `gus_bdl` | Demographics | https://api.stat.gov.pl/Home/BdlApi | P2 (pitch context). |
| `park_e_bike` | Free e-bikes at 7 P+R stations (seasonal) | https://ztp.krakow.pl/rower/park-e-bike | P2 POI. Kraków has no city-wide bike share now. |

### 4c. Praha

| Key | What | Access / URL | Notes / priority |
|---|---|---|---|
| `gtfs_pid` | PID static GTFS: metro, tram, bus, S-trains, ferries; Prague + region; 14 days ahead; daily | http://data.pid.cz/PID_GTFS.zip (try https first) · stops: http://data.pid.cz/stops/json/stops.json · info https://pid.cz/en/opendata/ | **P0.** CC-BY: credit "PID / ROPID". |
| `golemio` | Prague data platform API: PID departure boards, GTFS-RT vehicle positions, air-quality stations, playgrounds, gardens, medical institutions, city districts, libraries, shared bikes, parkings | https://api.golemio.cz · docs https://api.golemio.cz/docs/public-openapi/ · PID docs https://api.golemio.cz/pid/docs/openapi/ · **free API key**: https://api.golemio.cz/api-keys | P1 (live + POIs). **Register at H0** (needs email verification). Token header is probably `X-Access-Token`; verify. Read the key from env, never commit it. |
| `praha_open` | Local open-data catalogue (city, MČ, Golemio datasets) | https://opendata.praha.eu/ | P1. |
| `ipr` | IPR Praha / Geoportál: **městské části (57)**, **katastrální území (112)**, zeleň, buildings, demography, **noise** (Noise Map Prague 2025: LAeq day/night for road/tram/rail; Strategic Noise Map 2022: Ldvn/Ln) | https://geoportalpraha.cz/data-a-sluzby · downloads (E-výdej): https://evydej.iprpraha.cz · WMS/WFS/ArcGIS REST · Atlas ŽP: https://app.iprpraha.cz/apl/app/atlas-zp/ | **P0:** districts, k.ú., noise. Check the licence per dataset. If noise isn't downloadable, use the WMS fallback (§15). |
| `ruian` | RÚIAN address points per municipality (Praha obec code 554782; verify) | ATOM: https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-OB/RUIAN-CSV-ADR-OB.xml · CSV in ZIP, monthly, CC BY 4.0 | **P0:** habitable mask, population proxy, geocoder, school geocoding. ⚠ Coordinates are S-JTSK **EPSG:5514**. The CSV stores positive Y/X, but EPSG:5514 expects `x = −Y, y = −X`. The encoding is likely cp1250 with `;` delimiter; verify. |
| `msmt_schools` | MŠMT school register for Hl. m. Praha (types, addresses), updated ~3×/week | XML: https://rejstriky.msmt.cz/opendata/vrejcz010.xml | **P0.** Map school types to indicators. Geocode via RÚIAN. |
| `nrpzs` | All health-care providers with GPS and specialties (`ZZ_GPS`, `ZZ_obor_pece`, `ZZ_druh_pece`, `poskytovatel_druh`), monthly | CSV, CC BY 4.0: https://datanzis.uzis.gov.cz/data/NR-01-NRPZS/NR-01-06/Otevrena-data-NR-01-06-nrpzs-mista-poskytovani-zdravotnich-sluzeb.csv | **P0.** Derive GP, paediatrics, gynaecology, **maternity (inpatient gynaecology & obstetrics)**, pharmacies, ER from fields. Don't hardcode hospitals. |
| `chmi_air` | ČHMÚ air quality: `now/` (hourly, station metadata with coordinates), `historical/`, `products/` (**5-year average concentrations on a 1×1 km grid**) | https://opendata.chmi.cz/air_quality/ · metadata https://opendata.chmi.cz/air_quality/now/metadata/ · docs https://opendata.chmi.cz/air_quality/description_air_quality_opendata.pdf | **P0.** Prefer the 1×1 km grid for the indicator and stations for the live badge. |
| `police_cz` | Police ČR crime map: CSV/GeoJSON downloads + API; locations anonymized into Voronoi polygons; WGS84 | https://kriminalita.policie.gov.cz/ | **P0** (aggregate to MČ). ⚠ **Non-commercial licence.** Fine for a prototype; flag it in the roadmap. Fallback: cited MČ-level statistics. |
| `mf_rent` | MF ČR rent price map: Praha by katastrální území, min/median/max Kč/m² by flat size (1+kk … 4+kk); XLSX, quarterly (latest 2026-08-15) | https://mf.gov.cz/cenova-mapa-najemneho | **P0 for price** (`price.rent_per_m2`, use median over all sizes or for 2+kk). |
| `bikeshare_praha` | City-supported bike share (Rekola, Nextbike); shared e-scooters end in 2026 | https://praha.eu/bikesharing | P2. Use GBFS only if the operators publish it; verify. |

**Data rules (both cities):**
- Don't scrape portals whose terms forbid it (Otodom, OLX, Sreality, Bezrealitky). Kraków has no official rent source and Praha has no official purchase-price source. State this in "About the data".
- Every source writes an entry to `data/processed/{city}/manifest.json`: `{key, url, fetchedAt, licence, rows, status: ok|fallback|missing, note}`. The "About the data" page renders the manifest.
- Show safety only at **district level** (K: dzielnica, P: městská část), with neutral wording and a caveat (registered incidents ≠ perceived safety; busy centres have more incidents). Use no stigmatizing labels.
- Credit every source in the UI footer and on the About page: OSM, ZTP, MSIP/UM Kraków, GIOŚ, MEN, GUGiK, PID/ROPID, Golemio/OICT, IPR Praha, ČÚZK, MŠMT, ÚZIS, ČHMÚ, Policie ČR, MF ČR.

---

## 5. Spatial model and feature engineering (city-agnostic core + city adapters)

**Principle.** One pipeline, two configs. About 60% of the indicators come from the **city-agnostic core**: OSM + GTFS + r5py. Those work for any city automatically. The rest comes from **city adapters** that write the *same indicator columns*. A missing adapter means an OSM proxy or NaN, never a different schema.

| | Kraków | Praha |
|---|---|---|
| Area / H3 res-9 cells | ~327 km² / **~3,100** | ~496 km² / **~4,700** |
| Res-8 destinations (commute) | ~450 | ~670 |
| Metric CRS for buffers | EPSG:2180 (check each source's CRS; MSIP may use PL-2000 zone 7, EPSG:2178) | EPSG:5514 (S-JTSK Křovák) |
| Boundary | union of MSIP districts | union of IPR městské části (or RÚIAN/OSM) |
| `district` level | 18 dzielnic (MSIP) | 57 městských částí (IPR) |
| `neighborhood` level | nearest OSM `place=suburb\|quarter\|neighbourhood` | 112 katastrálních území (IPR); also the rent-map unit |
| Habitable mask / population proxy | MSIP EMUiA address points | RÚIAN address points |
| Price indicator | `price.buy_per_m2` (RCN), zł | `price.rent_per_m2` (MF map), Kč/month |
| Air | GIOŚ stations → IDW to centroids | ČHMÚ 1×1 km 5-yr grid → cell (stations for live) |
| Noise | MSIP noise polygons (Lden) | IPR noise maps (LAeq/Ldvn) |
| Rail/metro indicator | SKA/rail stations | metro + S-train stations |

**Steps (both cities):**
- **Grid.** H3 **res 9** (~0.1 km²), H3 v4 API. Store everything in EPSG:4326 and compute buffers in the metric CRS.
- **Habitable mask.** Rank a cell only if it has ≥ N address points (N in the city config). Otherwise rivers, forests, rail yards and industrial zones would "win". Non-habitable cells are still drawn (muted) and still serve as destinations.
- **Labels.** Each cell gets `district_id/name` and `neighborhood`.
- **Population proxy.** Address-point count per cell, used for district aggregation and the city view.
- **Walk times.** Centroid snapped to the network, then minutes to the nearest POI per category. Default speed 4.8 km/h. Store **raw minutes**.
- **Travel-time matrices (commute).**
  - Origins: habitable res-9 centroids. Destinations: all res-8 centroids.
  - Modes: transit (+walk) at **weekday 08:00** (median over a 30-min window), bike, walk.
  - **r5py** (Java 21) with OSM clipped to city + 5 km and the city GTFS (K: both ZTP feeds; P: PID). Pick a service date that exists in each feed; PID is only 14 days ahead.
  - Store `uint8` minutes (255 = unreachable/>120).
- **Environment.**
  - Noise: area-weighted mean of the max of the road/tram/rail layers.
  - Air: see the table.
  - Distance to motorway/trunk/primary roads; industrial landuse within 1 km.
- **Price.**
  - Kraków: RCN apartments from the last 24 months, IQR outlier filter, median per cell with k-ring smoothing (k=1..3 until n ≥ 5) and an `n_transactions` confidence.
  - Praha: join the MF median rent per katastrální území to cells by majority overlap.
- **Normalization is always *within the city*.** Percentiles and medians are per city, so "match %" means "how well this place fits you *in this city*".
- **Cross-city features (for twins and archetypes).** Use only **absolute, comparable** values: minutes, departures/h, green share, dB, µg/m³, counts within radius. Don't use price, since currencies differ. Alternatively, use price relative to the city median.

**Sanity checks** (soft; investigate when they fail):
- **Kraków:**
  - Stare Miasto is top for transit and leisure but low for quiet and price.
  - Cells near the Nowa Huta steelworks are worse for air.
  - Las Wolski / Bielany / Wola Justowska are top for green.
- **Praha:**
  - Praha 1 / Staré Město is top for transit and leisure but low for quiet.
  - Cells next to metro stations are top for the rail indicator.
  - Cells by the Ruzyně airport zone are worse for noise.
  - Areas near Stromovka, Divoká Šárka and Hostivař are top for green.

**Output artifacts** (`data/processed/{city}/`; small enough to ship in the engine image):

| File | Content |
|---|---|
| `grid.geojson` | `h3, district_id, district_name, neighborhood, habitable, population_est` (also copied to `web/public/data/{city}/`) |
| `features.parquet` | one row per res-9 cell. Raw indicator columns are named `<criterion>.<indicator>` exactly as in `indicators.yaml`. NaN = missing. |
| `pois.parquet` | `category, name, lat, lon, h3_9, source, extra_json` (common category vocabulary for both cities) |
| `travel_times.npz` | `origins[]`, `dests[]`, `transit`, `bike`, `walk` (uint8) |
| `districts.geojson`, `neighborhoods.geojson` | admin units with ids/names |
| `manifest.json` | §4 data rules |

The pooled ML artifacts live in `data/processed/_shared/models/`.

---

## 6. Scoring engine and ML (the separate Python service)

### 6.1 Normalization (runtime, driven by `indicators.yaml`, per city)
Each indicator becomes a 0–100 sub-score `s_i`:
- `decay` (times/distances): 100 at ≤ `good`, 0 at ≥ `bad`, linear in between. Thresholds are multiplied by the persona `walkFactor`.
- `percentile`: rank among the city's habitable cells.
- `inverse_percentile`: price, noise, PM.
- `threshold`: boolean-like.
- Missing values get the city median and the flag `imputed: true`. The UI shows "brak danych / chybí data / no data".

If an indicator is entirely missing in a city, drop it from that city's criterion average and report it in `/meta` (`coverage`).

### 6.2 Aggregation
- **Criterion score:** `S_c = Σ v_i·s_i / Σ v_i`, with indicator weights from the yaml plus persona overrides.
- **Commute:** `S_commute = Σ_a W(a)·decay(t_a; 15, 60) / Σ W(a)`. Ignored when there are no anchors.
- **Total match %:** `M = Σ_c W(level_c)·S_c / Σ_c W(level_c)`, rounded 0–100. Criteria with zero coverage in the city are excluded and flagged.
- **Hard filters** form a boolean mask. Ranking uses only cells that are habitable and pass.
- **District/neighbourhood aggregation:** population-weighted mean of the top 50% of passing cells, plus `share_passing`.
- **Implementation:** vectorized NumPy over a precomputed `(cells × indicators)` matrix per city. **Target p95 < 150 ms.**

### 6.3 Explanations (pl/cs/en)
For each top place, compute `k_c = W_c·(S_c − median_c)/ΣW`. Report the best 2 as highlights and the worst 1 as a warning. Templates are filled with **raw values**:

| Template | PL | CS | EN |
|---|---|---|---|
| Stop + frequency | "Tramwaj 3 min pieszo, 38 odjazdów/h" | "Tramvaj 3 min pěšky, 38 odjezdů/h" | "Tram 3 min walk, 38 departures/h" |
| Metro | "Metro 6 min pieszo" | "Metro 6 min pěšky" | "Metro 6 min walk" |
| Noise | "Hałas ok. 62 dB" | "Hluk cca 62 dB" | "Noise ~62 dB" |
| Budget | "Za Twój budżet ~48 m²" | "Za váš rozpočet ~48 m²" | "Your budget ≈ 48 m²" |

Never output an explanation without a real number behind it.

### 6.4 ML layer (honest, useful, demo-able)
1. **Neighbourhood archetypes (P1), pooled across both cities.**
   - Standardize the cross-city feature vector (§5) of habitable cells from Kraków and Praha together.
   - Run KMeans with k=6–8 (choose by silhouette).
   - **Train a small neural classifier** (`sklearn.MLPClassifier`, hidden (32,16)) on the cluster labels. It gives soft membership for any cell, district or anchor, e.g. "78% Studencki puls / Studentský puls / Student buzz".
   - The same archetypes exist in both cities, which makes cross-city comparison natural.
   - Report holdout accuracy in `docs/ML.md`. In the pitch, say plainly that the labels come from unsupervised clustering.
2. **Similar places (P1):** cosine similarity within a city.
3. **Twin neighbourhoods (P1, strong innovation):** cosine similarity on the cross-city vector from a cell or district in city X to the top-N in city Y. Example: *"Lubisz Kazimierz? W Pradze sprawdź Karlín."* It also works in reverse.
4. **Preference learning (P2):**
   - Prompt: *"Nie wiesz, co jest ważne? / Nevíte, co je důležité?"*
   - Show 6 pairwise choices between place profiles.
   - Fit Bradley–Terry logistic regression on criterion-difference vectors.
   - Map the result to suggested emoji levels.

---

## 7. Architecture and contracts

```
kompas/
├─ README.md                    # pitch summary, demo URL, run locally, architecture diagram, data & licences
├─ docs/  ARCHITECTURE.md · DATA_SOURCES.md · DECISIONS.md · ML.md · DEMO_SCRIPT.md
├─ config/
│   ├─ indicators.yaml          # SINGLE SOURCE OF TRUTH: levels, criteria, indicators, norms, personas, labels pl/cs/en
│   └─ cities/ krakow.yaml · praha.yaml
├─ contracts/ openapi.yaml · types.ts (generated) · fixtures/{krakow,praha}/*.json
├─ pipeline/                    # Workstream A — `make data CITY=krakow|praha|all`
│   core/ (grid, osm, gtfs, travel) · adapters/krakow/ · adapters/praha/ · ml_features.py · run.py
├─ engine/                      # Workstream B — FastAPI ("the separate program")
│   app/ main.py · scoring.py · explain.py · ml.py · live.py · twins.py · tests/
├─ web/                         # Workstream C — Vite + React + TS
│   src/ · src/locales/{pl,cs,en}.json · public/data/{city}/grid.geojson
├─ data/raw (gitignored) · data/processed/{krakow,praha,_shared}
├─ deck/                        # orchestrator + C → deck.pdf (≤10 slides)
└─ docker-compose.yml
```

**Data flow:** `pipeline` writes `data/processed/{city}/*`. The `engine` loads both cities at startup and normalizes and scores per request. The `web` app talks only to the engine. The exceptions are the basemap tiles and the geocoder fallback. Live data (GIOŚ, ČHMÚ/Golemio, GTFS-RT) is proxied and cached by `/api/{city}/live/*`.

### 7.1 Config shapes (complete them at H0–H1)

`config/cities/praha.yaml`:
```yaml
id: praha
name: {pl: "Praga", cs: "Praha", en: "Prague"}
country: CZ
defaultLang: cs
currency: CZK
center: [50.0755, 14.4378]
zoom: 11
metricCrs: "EPSG:5514"
osmPbf: https://download.geofabrik.de/europe/czech-republic/stredocesky-latest.osm.pbf
routingBufferKm: 5
gtfs: [http://data.pid.cz/PID_GTFS.zip]
habitableMinAddresses: 3
levels:
  district:     {source: ipr_mestske_casti,     label: {pl: "Dzielnica", cs: "Městská část", en: "District"}}
  neighborhood: {source: ipr_katastralni_uzemi, label: {pl: "Okolica",   cs: "Katastrální území", en: "Area"}}
price: {indicator: rent_per_m2, mode: rent, unit: {pl: "Kč/m²/mies.", cs: "Kč/m²/měs.", en: "CZK/m²/month"}}
adapters: [ruian_addresses, ipr_admin, msmt_schools, nrpzs_health, chmi_air, ipr_noise, police_cz, mf_rent, golemio_pois]
live: {air: chmi_or_golemio, departures: golemio_pid}
```
`config/cities/krakow.yaml` has the same shape. Kraków values:

| Key | Value |
|---|---|
| `defaultLang` | `pl` |
| `currency` | `PLN` |
| `center` | `[50.0614, 19.9366]` |
| `metricCrs` | `EPSG:2180` |
| OSM | `osm_krakow` |
| GTFS | both ZTP zips |
| `district` | MSIP dzielnice |
| `neighborhood` | OSM place names |
| `price` | `{indicator: buy_per_m2, mode: buy, unit: "zł/m²"}` |
| `adapters` | `[msip_addresses, msip_admin, men_schools, krk_open, gios_air, msip_noise, safety_krk, rcn_prices, ztp_hub]` |

`config/indicators.yaml` (excerpt; every label is in **pl, cs, en**):
```yaml
version: 1
levels: {0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 8}
levelEmoji: {1: "😐", 2: "🙂", 3: "😊", 4: "😍", 5: "🤩"}
levelLabel:
  1: {pl: "Mało ważne", cs: "Málo důležité", en: "Barely matters"}
  5: {pl: "Kluczowe",   cs: "Zásadní",       en: "Essential"}
criteria:
  - id: transit
    emoji: "🚋"
    label: {pl: "Komunikacja miejska", cs: "Veřejná doprava (MHD)", en: "Public transport"}
    indicators:
      - id: stop_walk_min
        label: {pl: "Najbliższy przystanek", cs: "Nejbližší zastávka", en: "Nearest stop"}
        unit: min
        norm: {type: decay, good: 3, bad: 12}
        weight: 3
        crossCity: true          # usable for twins/archetypes
        explain: {pl: "Przystanek {{value}} min pieszo", cs: "Zastávka {{value}} min pěšky", en: "Stop {{value}} min walk"}
      - id: rail_station_walk_min   # K: SKA/rail · P: metro + S-trains
        norm: {type: decay, good: 5, bad: 20}
        weight: 2
        crossCity: true
  - id: price
    indicators:
      - id: buy_per_m2     # Kraków only
        norm: {type: inverse_percentile}
        cities: [krakow]
      - id: rent_per_m2    # Praha only
        norm: {type: inverse_percentile}
        cities: [praha]
personas:
  - id: student
    emoji: "🎒"
    label: {pl: "Student/ka", cs: "Student/ka", en: "Student"}
    weights: {commute: 5, transit: 5, active: 3, green: 2, education: 1, family: 0, safety: 3,
              price: 5, shops: 3, health: 1, environment: 2, leisure: 5, accessibility: 0}
    indicatorWeights: {"education.university_walk_min": 3, "education.kindergarten_walk_min": 0}
    walkFactor: 1.0
    suggestedAnchors: [{label: {pl: "Moja uczelnia", cs: "Moje škola/univerzita", en: "My university"}, mode: transit}]
mustHaveCategories: [nursery, kindergarten, primary_school, tram_stop, metro_station, park, pharmacy, gp_clinic, supermarket, maternity_ward]
```

### 7.2 Engine API (FastAPI; OpenAPI at `/docs`; CORS for the web origin)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{status, dataVersion: {krakow, praha}, builtAt}` |
| GET | `/api/cities` | `[{id, name{pl,cs,en}, defaultLang, currency, center, zoom, coverage}]` |
| GET | `/api/{city}/meta?lang=` | levels, criteria + indicators (labels, units, sources, **coverage per city**), personas, mustHave categories, manifest |
| POST | `/api/{city}/score` | main call (below) |
| GET | `/api/{city}/place/{h3}?lang=&state=` | detail drawer |
| GET | `/api/{city}/commute?lat=&lon=&mode=` | `{anchorCell, cells: [[h3, minutes], …]}` |
| GET | `/api/{city}/similar/{h3}?limit=5` | same-city similar places |
| GET | `/api/twins?from=krakow&h3=…&to=praha&limit=5&lang=` | twin neighbourhoods across cities |
| GET | `/api/{city}/districts?…` | district ranking (or `aggregate=district` in `/score`) |
| GET | `/api/{city}/geocode?q=` | local address/POI search, accent-insensitive, Photon fallback |
| GET | `/api/{city}/live/air?lat=&lon=` | nearest station index (cache ≥10 min) |
| GET | `/api/{city}/live/departures?stopId=` | (P2) K: GTFS-RT; P: Golemio departure boards |
| POST | `/api/prefs/fit` | (P2) pairwise choices → suggested levels |

**`POST /api/praha/score` request:**
```json
{
  "v": 1, "lang": "cs", "persona": "working",
  "weights": {"commute":5,"transit":4,"active":4,"green":3,"education":0,"family":0,"safety":3,
              "price":4,"shops":4,"health":2,"environment":3,"leisure":4,"accessibility":0},
  "anchors": [{"id":"a1","label":"Práce – Karlín","lat":50.0925,"lon":14.4520,"mode":"transit","level":5,"maxMinutes":30}],
  "filters": {"maxRentPerM2": 420, "mustHave":[{"category":"metro_station","maxWalkMin":10}], "maxNoiseDb": null},
  "budget": {"monthlyRent": 22000},
  "aggregate": "hex", "limit": 20
}
```
**Response** (same shape for both cities):
```json
{
  "city": "praha", "currency": "CZK", "computeMs": 48,
  "count": {"cells": 4700, "habitable": 3100, "passing": 820},
  "cells": [["<h3-res9>", 87, 1], ["<h3-res9>", 54, 0]],
  "top": [{
    "id": "<h3-res9>", "kind": "hex", "rank": 1, "score": 91,
    "name": "Libeň", "district": {"id": "<mc-id>", "name": "Praha 8"},
    "centroid": {"lat": 50.10, "lon": 14.47},
    "criteria": {"transit": 94, "price": 58, "green": 61},
    "highlights": [{"criterion": "transit", "text": "Metro 6 min pěšky, 52 odjezdů/h"}],
    "warnings": [{"criterion": "environment", "text": "Hluk cca 64 dB"}],
    "anchors": [{"id": "a1", "minutes": 11, "mode": "transit"}],
    "price": {"indicator": "rent_per_m2", "value": 398, "unit": "Kč/m²/měs."},
    "budgetM2": 55,
    "archetype": {"id": "urban_mix", "label": "Městský mix", "p": 0.71},
    "imputed": []
  }],
  "relaxHint": null
}
```
`cells` uses compact tuples `[h3, score, passes]`. Geometry is static (`grid.geojson`), coloured via MapLibre `feature-state`.

### 7.3 Fixtures
By **H1**, `contracts/fixtures/krakow/` and `contracts/fixtures/praha/` each contain:
- `meta.json`
- `score_student.json`, `score_parent.json`
- `place.json`
- `commute.json`
- `grid.sample.geojson` (~200 cells, plausible fake values)

Also `twins.json` and `cities.json`. The web app runs on them with `VITE_USE_FIXTURES=1`.

---

## 8. Tech stack (decided; deviations go to DECISIONS.md)

- **Pipeline** (Python 3.11+, `uv`):
  - Geo: geopandas, shapely, pyproj, h3 (v4)
  - OSM and transit: pyrosm or quackosm, gtfs-kit/partridge, **r5py** (Java 21); osmnx/pandana as fallback
  - I/O: httpx + requests-cache, openpyxl (MEN/MF XLSX), lxml (MŠMT XML), pyarrow, polars/pandas
- **Engine:** FastAPI, uvicorn, pydantic v2, numpy, scikit-learn, joblib, cachetools; pytest.
- **Web:**
  - Vite + React + TypeScript
  - **MapLibre GL JS** (+ `react-map-gl/maplibre`), **OpenFreeMap** basemap, h3-js
  - Recharts, TanStack Query, Zustand with URL sync
  - Tailwind + shadcn/ui (Radix)
  - **react-i18next** with `pl`, `cs`, `en` (plurals!)
  - Playwright smoke test
- **Deploy:** web on Vercel/Netlify/Cloudflare Pages. Engine as Docker on Render/Railway/Fly.io, with both cities' processed data baked in. `docker-compose up` for local runs and as the venue fallback.
- **Static fallback mode** (`VITE_STATIC_FALLBACK=1`): ships `criteria_scores.json` per city and computes the weighted sum in TS. Commute, twins and live data are disabled. This saves the demo if the backend dies.

---

## 9. Plan and timeline (H0 = official start, H24 = hard deadline)

| Window | Orchestrator (+ pitch) | A · Data (both cities) | B · Engine + ML + API | C · Frontend, UX, content (pl/cs/en) |
|---|---|---|---|---|
| **H0–H1** | Repo skeleton, `indicators.yaml` v1, both city configs, OpenAPI, fixtures, CI lint. **Register Golemio API key.** Confirm deadline. Assign people. | Hit every §4 source once and save the responses to `data/raw/`. Download both PBFs and all GTFS. Mark status in the manifests. | FastAPI skeleton serving fixtures for both cities; scoring module on a synthetic matrix | Vite app, MapLibre + OpenFreeMap, i18n scaffold (pl/cs/en), layout shell, design tokens, wireframes of the steps (city → persona → emoji → places) |
| **H1–H6** | Unblock, review PRs, set up deploy targets with a "hello" build by H3 | **City-agnostic core for both cities:** boundary, grid, habitable mask, OSM POIs, GTFS transit indicators, green, shops, leisure. Then Kraków adapters: districts, MEN schools, Otwarte Dane. → **features v1 (K + P core)** | `/cities`, `/meta`, `/score` with filters, explanations (3 languages) and relax hint; `/place`; tests | Onboarding with city picker, persona cards, emoji rows, anchors and limits; hex layer from fixtures; ranking list; legend; persona and criteria copy in pl/cs/en |
| **M1 @ H6** | **Walking skeleton:** Kraków real features (≥6 criteria) → engine → UI, end to end. Praha core features computed. | | | |
| **H6–H12** | Deploy staging; integration tests; **deck v1**; demo story | **r5py matrices (K, then P).** Kraków: MSIP noise, GIOŚ air, safety, RCN. Praha: RÚIAN, IPR admin + noise, MŠMT schools, NRPZS health, ČHMÚ air, police, MF rent. | `/commute`, district aggregation, **pooled archetypes + MLP**, `/similar`, **`/twins`**, `/live/air` (GIOŚ, ČHMÚ/Golemio); perf < 150 ms | Detail drawer (radar, scales, nearest, budget → m², archetype, live air), **commute heat map**, compare, share URL, **city switcher**, twins panel, mobile bottom sheet |
| **M2 @ H12** | **All P0 for both cities on the staging URL.** Go/no-go on P2. | | | |
| **H12–H16** | Choose ≤2 stretch items; data QA review; deck v2 | Sanity checks for both cities, manifest completeness, `DATA_SOURCES.md`; city-view data (if chosen) | Preference learning (P2), static-fallback export, edge cases, live departures (P2) | Visual polish; empty/error states; full **cs + en** proofreading; a11y fixes; About-the-data page |
| **M3 @ H16** | **FEATURE FREEZE.** Only fixes after this point. | | | |
| **H16–H20** | Bug bash on phone + laptop; final deploy; README; **deck final (≤10 slides, PDF)** | Data docs, attribution list | Tests green; load test `/score` for both cities | Lighthouse a11y ≥ 90; screenshots for the deck; final copy in 3 languages |
| **M4 @ H20** | Record a **≤3 min backup demo video**; tag `v1.0` | | | |
| **H20–H22** | Fill in the HackTribe form; **SUBMIT at H22** | | | |
| **H22–H24** | Buffer only. No new features. Rehearse the pitch (3 min + Q&A). | | | |

**Humans:** rotate 3–4 h sleep blocks between H10 and H18. At least one person from {A, B} and one from {C, orchestrator} is awake at all times. **Agents:** queue the next tasks before their human sleeps.

---

## 10. Scope priorities (cut from the bottom)

- **MUST (P0):**
  - City picker and switcher, Kraków + Praha.
  - Personas and 5-emoji weighting.
  - **Kraków:** ≥10/13 criteria on real data. **Praha:** ≥8/13. The rest are marked "beta" or hidden via `coverage`.
  - Hex match map + legend, ranking, detail drawer with explanations.
  - Commute heat map for ≥1 anchor (transit) in both cities.
  - **UI in pl, cs, en.**
  - Deployed demo URL, public repo, README, ≤10-slide PDF.
- **SHOULD (P1):** hard filters + relax hint, district ranking, compare, archetype MLP badge, similar places, **twin neighbourhoods K ↔ P**, live air quality, share URL, About-the-data page, budget → m², static fallback.
- **COULD (P2):** preference learning, live departures (ZTP GTFS-RT / Golemio PID), city view of service gaps, NFZ waiting times, Prague bike-share GBFS, slope, Kraków P+R live occupancy.
- **WON'T:** accounts/login, user-generated content, scraping listing portals, native apps, payments, more cities during the hackathon. The pipeline is ready for them, and that goes in the pitch.

---

## 11. Workstream briefs (exactly three; each agent reads §0–§10 first)

### Workstream A: Data pipeline (Python/geo), Kraków + Praha
**Mission:** turn both cities' open data and OSM into `data/processed/{city}/*` (§5), reproducibly (`make data CITY=all`). **Kraków first** at every step, Praha right after with the same code.

1. **H0–H1.**
   - Verify every §4 source with a real request and write the manifest status. Download both PBFs and GTFS (ZTP A+T, PID).
   - Check PID GTFS service dates and pick a weekday inside the feed for routing.
   - Build both city boundaries.
2. **City-agnostic core** (`pipeline/core/`):
   - grid, habitable mask, labels, population proxy
   - POI extraction to `pois.parquet` with **one shared category vocabulary**: `supermarket`, `pharmacy`, `parcel_locker`, `playground`, `park`, `gp_clinic`, `hospital_er`, `maternity_ward`, `metro_station`, `tram_stop`, …
   - GTFS transit indicators, green, shops, leisure, accessibility
3. **Adapters** (`pipeline/adapters/{city}/`). Each one writes the same `<criterion>.<indicator>` columns:
   - **Kraków:** MSIP (districts, EMUiA, noise), MEN schools XLSX, Otwarte Dane (żłobki, parks), ZTP hub, Bezpieczny Kraków, GIOŚ IDW, RCN.
   - **Praha:**
     - RÚIAN (mind the EPSG:5514 sign flip and encoding)
     - IPR (MČ, k.ú., noise, zeleň)
     - MŠMT XML (geocode via RÚIAN)
     - NRPZS (GP, paediatrics, gynaecology, maternity, pharmacy, ER from specialty fields)
     - ČHMÚ (1×1 km grid)
     - Police ČR (aggregate to MČ)
     - MF rent XLSX (k.ú. → cells)
     - Golemio POIs (playgrounds, gardens) if the key works
4. **Travel-time matrices** with r5py, Kraków then Praha (§5). If r5py doesn't work by **H9**, switch to the §15 fallback.
5. **Cross-city feature table** for B (`ml_features.parquet`, only `crossCity: true` indicators) with a column-name validation script. The engine must fail loudly on any mismatch.
6. **QA and docs:** sanity checks for both cities (§5), NaN report per column, `docs/DATA_SOURCES.md` (source, licence, date, transformations, limitations, per city), attribution list for the UI.

**DoD:**
- `make data CITY=all` runs from scratch in < 45 min (r5py may be cached).
- Artifacts validate against the yaml.
- Both manifests are complete.
- Coverage per criterion per city is reported.

### Workstream B: Scoring engine, ML and API (FastAPI)
**Mission:** the separate program that turns weights into rankings for both cities, fast and explainably.

1. **H0–H1:** serve fixtures on every endpoint in §7.2 for both cities, so C is never blocked.
2. Load both cities at startup: `features.parquet` + yaml + city config. Build the normalized matrices per city and per `walkFactor` variant, and cache them.
3. `/score`:
   - weights and anchors (`travel_times.npz`)
   - filters with the city-specific price field
   - relax hint
   - top-N
   - **explanations in pl/cs/en with real values**
   - district aggregation
   - `coverage` handling
4. `/place`, `/commute`, `/similar`, `/geocode` (EMUiA/RÚIAN index, accent-insensitive: "zizkov" matches "Žižkov", "rakowicka" matches "Rakowicka"), `/live/air` with cache (GIOŚ 2 req/min!), `/cities`.
5. **ML** (§6.4):
   - Pooled KMeans → MLP, saved to `_shared/models/`, metrics in `docs/ML.md`.
   - Archetype names come from C in 3 languages.
   - Then `/twins` and `/similar`. Then preference learning (P2).
6. Export `criteria_scores.json` per city for the static fallback.
7. **Tests:**
   - Monotonicity: raising a criterion's level never lowers the relative rank of the cell that is best in that criterion.
   - Filters exclude correctly.
   - Determinism.
   - Explanation values match raw features.
   - Both cities load.
   - p95 latency < 150 ms on ~4.7k cells.

**DoD:**
- OpenAPI matches `contracts/openapi.yaml`.
- `pytest` is green.
- The Docker image runs with both cities baked in.
- `/api/health` shows both data versions.

### Workstream C: Frontend, UX/design and content in pl/cs/en
**Mission:** a beautiful, obvious single page (§3) that feels native in Polish and Czech. C also owns all copy and the visual material for the deck.

1. **H0–H1:**
   - Layout shell; MapLibre + OpenFreeMap positron.
   - City centres: Kraków ≈ 50.06, 19.94, z 11.5; Praha ≈ 50.08, 14.44, z 11.
   - i18n (`pl`, `cs`, `en`; language default from city, `lang` URL override); fixtures mode; design tokens; colour-blind-safe palettes.
2. **Onboarding:** city cards → persona cards → 13 emoji rows (keyboard-accessible radio groups, tooltips) → anchors (geocoder autocomplete per city, mode, level) and limits (currency-aware). The "Show results" button (*Pokaż wyniki / Zobrazit výsledky / Show results*) is always reachable.
3. **Map:**
   - `grid.geojson` per city, coloured via `feature-state` (match / commute / per criterion)
   - hatched non-passing cells, top-10 markers, anchor pins
   - district outlines, legend, mode switcher
   - smooth fly-to on city switch
4. **Ranking panel** (places | districts) with cards per §3.6. Hovering links the card and the cell.
5. **Detail drawer:**
   - radar vs city median, indicator scales, nearest amenities, commute times
   - budget → m², in local currency and mode (buy in Kraków, rent in Praha)
   - archetype badge with %
   - live air badge
   - similar places
   - **twin neighbourhoods**: click one to switch city and fly to it, keeping persona and levels
6. Compare view, share button, language toggle, **About-the-data page per city** (from `/meta` + manifest), footer attributions.
7. **Content:**
   - every string in `pl.json`, `cs.json`, `en.json`, with correct plurals (pl: "1 odjazd / 2 odjazdy / 5 odjazdów"; cs: "1 odjezd / 2 odjezdy / 5 odjezdů")
   - persona descriptions, archetype names (warm, non-stigmatizing, 3 languages), explanation templates
   - safety caveat, methodology text
   - Polish and Czech proofreading by a native speaker on the team if possible
8. **Mobile:** bottom sheet, filter sheet, 44 px touch targets. Empty/loading/error states. Static fallback mode.
9. **Deck support:** screenshots (both cities, both languages), app visuals and diagram styling for the orchestrator's deck.

**DoD:**
- Works at 375 px and 1440 px.
- No console errors.
- Lighthouse a11y ≥ 90.
- No hardcoded strings; all three locales complete (a CI check compares keys).
- Playwright smoke passes on staging for both cities (city → persona → results → detail → twins).

---

## 12. Quality gates and Definition of Done (product)

- The public demo URL works on phone and laptop for **both cities**. First meaningful ranking within **≤3 clicks** from landing.
- Every criterion has ≥1 real-data indicator per city or is visibly labelled beta/hidden. No silent fake data.
- Map + ranking + detail with explanations + commute heat map work on **real data in Kraków and Praha**.
- **pl, cs and en** are complete; currency and number formats are correct per city and locale.
- Every number shown traces to a source in About the data.
- `/score` p95 < 150 ms server-side; perceived UI update ≤ 500 ms.
- **README:**
  - what and why, screenshots, demo URL
  - architecture diagram, `docker-compose up`
  - data sources and licences per city
  - "how to add a city" (config + adapters)
  - team
- All tests green: engine pytest, data validation, i18n key check, Playwright smoke.
- Attributions visible in the UI and README.

---

## 13. Pitch and submission package (owner: orchestrator; visuals from C)

**Deck (≤10 slides, PDF, English, or Polish if the jury prefers):**
1. **Title + hook.** "Kompas: find the part of the city that fits your life." Kraków + Praha. QR to the demo.
2. **Problem.** Scattered data, foreign languages, 5 persona pain points.
3. **Solution.** City → who you are → 5 emoji → your places → ranked map.
4. **Demo screenshots.** Heat map, ranking "why", radar, commute heat map, twins.
5. **How it works.** Open data → H3 features → scoring engine → explanations → ML (diagram).
6. **Open data in two countries.** Kraków and Praha sources plus OSM; no login, no tracking.
7. **Innovation.** Emoji weighting, anchor commute heat map, neural neighbourhood types, **twin neighbourhoods across borders**, budget → m².
8. **Impact and scale.**
   - Citizens, students, families, seniors, people moving between cities.
   - City use: service-gap view, communication with citizens.
   - "Second city added with configs + adapters, so any city with OSM + GTFS can be next."
   - Verified numbers only.
9. **Roadmap and value.** More cities, live data, partner integrations (real-estate/finance, city portals), licence clean-up for commercial use.
10. **Team and links.** Repo, demo, video.

**Live demo story (3 min):**
1. **Ania, 24, works in Kraków.** She picks 💼, sets 🤩 for commute and price, adds the work anchor (Zabłocie) and her budget. The top 3 appear. She opens #1 to see the "why" and the budget in m², then turns on the commute heat map.
2. **She gets a job offer in Praha (Karlín).** She switches the city and the UI stays in Polish. **Twin neighbourhoods** shows "places in Praha like your favourite spot in Kraków". Then the commute heat map to Karlín.
3. **Switch to Czech** with one click to show the localization. **Switch persona to 🤰** and the map visibly reorganizes towards green, quiet areas near a maternity ward.
4. Show the archetype badge, the share link, and About the data (real sources from both cities).

**HackTribe form:** title, team name, members, description (≤ ~1,500 characters, EN or PL), PDF, repo + demo + video links. Draft it by H20 and submit at H22.

---

## 14. Engineering rules for all agents

1. **Verify before you build.** Hit every external endpoint for real and save the response before writing code that depends on it. Never invent endpoints, fields or dataset names. When docs and reality differ, reality wins; log it.
2. **Cache everything.** Pipeline steps are idempotent. Raw downloads go to `data/raw/{city}/` with timestamps.
3. **Respect usage policies:**
   - OpenFreeMap instead of the OSM tile servers.
   - Nominatim ≤1 req/s with a User-Agent.
   - Overpass sparingly.
   - GIOŚ 2 req/min.
   - Golemio key from env.
   - Police ČR data is non-commercial only.
4. **Time-box.** Anything stuck > 45 min: apply the §15 fallback, write one line in `DECISIONS.md`, move on.
5. **Contracts are law.** After M1, changes are additive only. Bump `contracts/` and fixtures in the same PR.
6. **City-agnostic by default.** No `if city == "praha"` in the core or engine. City differences live in `config/cities/*.yaml` and `pipeline/adapters/{city}/`.
7. **No hardcoded UI strings.** All three locales are updated together. UTF-8 everywhere. Locale-aware sorting and search.
8. **No secrets in git.** Use `.env.example` (`GOLEMIO_API_KEY`, optional `AIRLY_API_KEY`). Features disable themselves without keys.
9. **Small commits, conventional messages.** `main` is always deployable; the orchestrator merges after checks.
10. **Honesty in UI and pitch.** Label estimates, imputed values, licence limits and model limitations.

---

## 15. Risks and fallbacks

| Risk | Fallback |
|---|---|
| r5py/Java fails or is too slow (PID GTFS is large) | Walk/bike via OSMnx/pandana. Transit approximation: walk to stop + headway/2 + in-vehicle time on a GTFS stop graph (Dijkstra, weekday 07–09). Only for res-8 destinations. Praha last. |
| Praha falls behind | Ship Praha with core (OSM + GTFS) criteria plus whatever adapters are done. Mark the rest "beta" via `coverage`. Kraków stays complete. |
| RCN not downloadable for Kraków | Query the WFS in tiles. Otherwise use a cited district-level zł/m² table labelled "szacunek", or mark price beta. |
| MF rent XLSX can't be joined | Use the MČ-level median from the same XLSX, or k.ú. names matched to the IPR layer by normalized name. |
| Safety data not machine-readable (K or P) | Transcribe district totals with a citation. Add lighting share as a secondary indicator. |
| Noise maps only as WMS (K or P) | Sample WMS `GetMap` PNG colours at cell centroids and map the legend colours to dB bands. Document the method. |
| Golemio key not approved in time | Skip Golemio. Use PID GTFS + NRPZS + OSM; live air from ČHMÚ `now/`. |
| RÚIAN coordinates look wrong | Check the EPSG:5514 sign flip (`x = −Y, y = −X`) and the encoding. Validate against 3 known addresses. |
| GIOŚ/ČHMÚ outage or rate limits | Use cached values with timestamps. |
| Backend hosting fails | Static fallback mode + local `docker-compose` + backup video. |
| Venue Wi-Fi fails during the pitch | Run locally from a laptop, with the video ready. |
| Scope creep | §10 cut lines, freeze at H16, orchestrator veto. |

---

## 16. First actions (orchestrator, now)

1. Confirm the deadline with the organizers. **Register the Golemio API key.** Create a public repo with a README stub, the §7 structure, `uv` + `pnpm` workspaces and CI (lint + i18n key check).
2. Write `config/indicators.yaml` in full: 13 criteria, all indicators with norms and `crossCity` flags, 6 personas, levels/emoji, mustHave categories, **all labels and explanation templates in pl/cs/en**.
3. Write `config/cities/krakow.yaml` and `config/cities/praha.yaml` (§7.1).
4. Write `contracts/openapi.yaml`, generate `types.ts`, and create fixtures for both cities (§7.3).
5. Start the three workstreams with: *"Read MASTER_PROMPT §0–§10, then execute Workstream A/B/C. Report at M1 (H6)."*
6. Create `docs/DECISIONS.md` and log the first entries: stack, H3 res 9, Kraków-first, deadline confirmation.
7. Deploy a "hello" build of web + engine before H3.
8. At each milestone, post a 5-line status: done / next / blocked / cuts / demo-readiness (0–100%) per city.

**Build something that makes everyday life in Kraków and Praha easier, and make sure the judges can see it in 3 minutes.**

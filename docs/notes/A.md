# Workstream A: data pipeline notes (Kraków + Praha)

Branch `a-data`. The pipeline lives in `pipeline/`: its own uv project, Python 3.12, and Java 21 for r5py (`brew install openjdk@21`; the Makefile sets `JAVA_HOME`).
To run it: `cd pipeline && make data CITY=krakow|praha|all` (fetch → build → travel → ml → validate).
Data documentation: [`docs/DATA_SOURCES.md`](../DATA_SOURCES.md).

## Status

### 2026-10-03 18:00 (≈H2.5): M1 + M2 + M3 done
**Done**
- Every §4 source was hit with a real request. Raw files are in `data/raw/{city}/` (gitignored). The manifests list every key with its status, rows and note.
- Both cities are built to **contracts-v1**. `contracts/tools/validate_data.py --city all` reports **0 errors**.
  - **Kraków:** 3,217 cells, 2,162 habitable.
  - **Praha:** 4,976 cells, 2,967 habitable.
- `travel_times.npz` for **both** cities (r5py; transit, bike and walk; Tue 2026-10-06 08:00 with a 30-min window):
  - Kraków: 2,162 × 506.
  - Praha: 2,967 × 775, 97% of transit pairs reachable.
- `_shared/ml_features.parquet`: 49 crossCity columns, 8,193 rows.
- **New:** `addresses.parquet` per city, exactly as in contracts-v2 §3b (K 70,217 EMUiA, P 134,670 RÚIAN). It replaces my earlier ad-hoc `geocode.parquet`.
- **New:**
  - `accessibility.slope_pct` from the Copernicus DEM (both cities).
  - Nurseries from official registers: K = UM Kraków żłobki layer (263); P = MPSV dětské skupiny (417).
- `pipeline/validate.py` and `make qa` run the contract check, the README §5 sanity checks and the coverage tables in `docs/DATA_SOURCES.md` §5.
  - Kraków passes 6 of 6 checks.
  - Praha passes 5 of 6. The failure is "Praha 1 loud": modelled road noise is low in the pedestrian Old Town. It is reported, not tuned away.
- `docs/DATA_SOURCES.md` covers sources, URLs, licences, methods, coverage, attribution and limitations.

**Coverage (weighted share of habitable cells with data)**

| criterion | Kraków | Praha |
|---|---|---|
| transit, active, green, education, family, safety, shops, health, environment, leisure | 100% | 100% |
| price | 87% weighted; 18% of cells NaN (fewer than 5 qualifying RCN sales within k ≤ 3) | 100% |
| accessibility | 33% (benches + slope; ZTP GTFS has no wheelchair data) | 97% |
| commute | ✓ transit/bike/walk | ✓ transit/bike/walk |

- **DoD:** `make data CITY=all` ran end-to-end in **35 min** (downloads cached, r5py recomputed) with 0 contract errors. The r5py outputs are deterministic (identical reachability across runs).
- **Integration check (17:20):** I ran B's engine (`origin/b-engine`) on this data. `/api/health` reports `ok`, `dataSource: real` for both cities; `/score` takes ~1 ms.
  - Explanations carry real values, e.g. "Mieszkania ok. 11 600 zł/m²", "Zastávka 3 min pěšky".
  - Twins: Kraków Piasek → Vinohrady, Nové Město, Staré Město.
  - Local geocode works on `addresses.parquet`.
- **QA fix (17:55):** Kraków RCN is now limited to arm's-length household purchases (full ownership, one flat per transaction, individual buyer). A 9 M zł bulk deal for 24 flats had dragged a Stare Miasto cell to 11.6k zł/m²; it is now 19.4k.

**Next**
- Kraków GP clinics from NFZ POZ contracts (the `app-umw-api` returned 503 "Maintenance" at 17:15 and 17:40; retry later).
- On request from B or C: extra columns, re-runs after feed updates (PID GTFS only covers 10-03…10-16).

**Blocked**: nothing.

## Decisions (A-local; B may copy them into docs/DECISIONS.md)
- 16:00 The MŠMT XML `rejstriky.msmt.cz/opendata/vrejcz010.xml` returns **404** (site moved to isv.gov.cz). We use the MŠMT LKOD JSON-LD for Hl. m. Praha, found via NKOD SPARQL.
- 16:00 Kraków RCN: we use the city's own WFS `geodezja.eco.um.krakow.pl/cgi-bin/krakow-rcn` (layer `ms:lokale`, one point per transaction with price and area). The server caps pages at 1,000 rows, so the fetcher follows the WFS `next` link.
- 16:00 Kraków safety: GMK ArcGIS layer "Przestępstwa w przestrzeni publicznej 2023" (141 polygons) → dzielnice. The denominator is the GUS BDL population split by EMUiA address share.
- 16:00 Otwarte Dane Kraków has no parks or żłobki dataset, so we use OSM for those.
- 16:20 Kraków maternity and gynaecology come from the NFZ API (benefits "ODDZIAŁ POŁOŻNICZO-GINEKOLOGICZNY" and "PORADNIA POŁOŻNICZO-GINEKOLOGICZNA", with lat/lon). Kraków paediatrician = paediatric POIs ∪ POZ (GP) clinics, because POZ covers children in PL.
- 16:20 Kraków air: GIOŚ `statistics/getStatisticsForPollutants` gives annual means per station. We average the last 3 years and interpolate with IDW. The API allows 2 req/min, so the fetcher waits 31 s between calls.
- 16:45 Praha noise: the IPR road-traffic map (`HM_CUR_HM_EKOLA_ADP_PASMA_DEN_P`). The generic "Hluková mapa – den" layer gave 20–25 dB on the Magistrála. IPR has no tram or rail noise layer.
- 16:00 Police ČR: national monthly zips `kriminalita.policie.gov.cz/api/v2/downloads/{YYYYMM}.zip`, last 12 months, criminal offences only (no přestupky, accidents or fires). **Non-commercial licence.**
- 16:50 Praha nurseries: the MPSV register of dětské skupiny (417 of 433 geocoded via RÚIAN) plus OSM jesle. OSM alone had only 13.
- 16:00 Walk network built directly from OSM highway geometry, plus a scipy multi-source Dijkstra. No osmnx or Overpass is needed (Overpass is unreachable from this network).
- 16:50 r5py caches input files **by basename**, so the two cities' `clip.osm.pbf` collided and Praha routed on Kraków's network (0% reachable). Fixed with `{city}_clip.osm.pbf`. PID GTFS is sanitised for R5: empty `stop_name` on 629 pathway nodes, and `pathways.txt` dropped.
- Walk minutes are capped at 60. Counts use euclidean radii (800 m ≈ 10 min). Shares are in %, areas in ha (contract units).

## For B (engine)
- `poi.metro_station_walk_min` exists for Praha only. Kraków has no metro, so the column is absent there.
- `price.buy_n_transactions` (Kraków) is the RCN sample size behind the cell median, usable as a confidence flag.
- Extra QA columns are written as `aux.*` (`aux.environment_no2` in Praha; `aux.active_bikeshare_walk_min` in Kraków), which the engine ignores.
- `grid.geojson` also carries `neighborhood_id`, which is handy for neighbourhood aggregation.
- `travel_times.npz` has `meta_json` = `{"date":"2026-10-06","departure":"08:00","windowMinutes":30,"method":"r5py",…}`.

- `addresses.parquet` (contracts-v2): Praha `housenumber` is "č.p./č.o." (e.g. `1448/20`; `ev. 12` for registration numbers), and `street` falls back to the place name when an address has no street. `source` = manifest key (`msip_addresses`, `ruian`). Postcodes: K `31-045`, P `193 00`.

## For C (web)
- `grid.geojson` per city is ready to copy to `web/public/data/{city}/` (README §5). The numeric feature `id` is the row index.
- The About page can render `manifest.json` and the attribution list in `docs/DATA_SOURCES.md` §6.

## Requests to other workstreams
- (B, optional, additive) Consider adding `environment.no2` (µg/m³; Praha ČHMÚ grid, available now as `aux.environment_no2`; Kraków GIOŚ could follow).

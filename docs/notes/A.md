# Workstream A: data pipeline notes (Kraków + Praha)

Branch `a-data`. The pipeline lives in `pipeline/`: its own uv project, Python 3.12, and Java 21 for r5py (`brew install openjdk@21`; the Makefile sets `JAVA_HOME`).
To run it: `cd pipeline && make data CITY=krakow|praha|all` (fetch → build → travel → ml → validate).
Data documentation: [`docs/DATA_SOURCES.md`](../DATA_SOURCES.md).

## Status

### 2026-10-03 17:00 (≈H1.7): M1 done, M2 mostly done
**Done**
- Every §4 source was hit with a real request. Raw files are in `data/raw/{city}/` (gitignored). The manifests list every key with its status and notes.
- Both cities are built to **contracts-v1** (merged from main): `contracts/tools/validate_data.py` reports **0 errors** for each.
  - **Kraków:** 3,217 cells, 2,162 habitable. Coverage is 100% for 10 of 12 criteria; price 88%; accessibility 17% (beta).
  - **Praha:** 4,976 cells, 2,967 habitable. Coverage is 100% for 11 of 12 criteria; accessibility 80%.
- `travel_times.npz` (r5py, transit/bike/walk, Tue 2026-10-06 08:00):
  - Kraków: done (2,162 × 506).
  - Praha: transit done (97% reachable); bike and walk are running.
- `_shared/ml_features.parquet`: 49 crossCity columns, both cities.
- `pipeline/validate.py` runs the contract check, the README §5 sanity checks and the coverage report in `docs/DATA_SOURCES.md` §5.
  - Kraków passes all 6 checks.
  - Praha passes 5 of 6. The failure is "Praha 1 loud": the modelled road noise is low in the pedestrian Old Town. See DATA_SOURCES §7.

**Coverage (weighted share of habitable cells with data)**

| criterion | Kraków | Praha |
|---|---|---|
| transit, active, green, education, family, safety, shops, health, environment, leisure | 100% | 100% |
| price | 88% (RCN: n<5 → NaN) | 100% |
| accessibility | 17% (no GTFS wheelchair data) | 80% |
| commute | travel_times.npz ✓ | transit ✓, bike/walk running |

**Next**
- Praha bike/walk matrices → commit `travel_times.npz` → refresh `ml_features.parquet`.
- P2: `accessibility.slope_pct` from a DEM.
- QA pass on outliers.

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

- **New optional file `geocode.parquet`** (per city; K 73k rows, P 142k rows) for `/api/{city}/geocode`. Columns:
  `label, sublabel (district name), kind (address|street|place|district), lat, lon, h3, search`. `search` is
  lower-case and diacritics-free (ł→l): "zizkov" → "Žižkov", "rakowicka 27" → "Rakowicka 27". Praha address
  labels use `street cp/co`, and the search key also contains the orientation number on its own. Please match by tokens, not by raw
  substring ("vinohradska 12" also hits 1200/…), and rank place/district before street before address. POIs stay in `pois.parquet`.

## For C (web)
- `grid.geojson` per city is ready to copy to `web/public/data/{city}/` (README §5). The numeric feature `id` is the row index.
- The About page can render `manifest.json` and the attribution list in `docs/DATA_SOURCES.md` §6.

## Requests to other workstreams
- (B, additive) Add `geocode.parquet` (above) to DATA_CONTRACT §5 as an optional file, or tell me another shape you prefer.
- (B, optional, additive) Consider adding `environment.no2` (µg/m³; Praha ČHMÚ grid, available now as `aux.environment_no2`; Kraków GIOŚ could follow).

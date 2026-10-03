# Data contract: `data/processed/{city}/` (v1)

**Producer:** Workstream A (`pipeline/`). **Consumer:** Workstream B (`engine/`), which loads it at startup and **fails loudly** on any mismatch.
**Source of truth for column names:** `config/indicators.yaml`. **City settings:** `config/cities/{city}.yaml`.
**Validate before you push:** `uv run contracts/tools/validate_data.py --city krakow` (or `--city all`).

Changes after `contracts-v1` are additive only, and B lists them in `docs/notes/B.md`.

---

## 0. Rules that apply to every file

| Rule | Value |
|---|---|
| Directory | `data/processed/{city}/`, where `city` ∈ `krakow`, `praha` (the city yaml `id`) |
| CRS | **EPSG:4326** (WGS84 lon/lat) for everything stored. Use the city `metricCrs` only for computing buffers. |
| Coordinates | GeoJSON order `[lon, lat]`, 6 decimals. Parquet stores `lat` and `lon` as separate float64 columns. |
| H3 | **v4**, lower-case 15-char hex strings. Grid res **9**; commute destinations res **8**. |
| Encoding | UTF-8. Keep Polish/Czech diacritics; never transliterate names. |
| Parquet | pyarrow, snappy compression, no pandas index column (`index=False`). |
| Size | **≤ 50 MB per file.** Everything ships inside the engine Docker image. |
| Missing data | **NaN** means unknown. **Never write 0 for missing**, because 0 is a real value ("0 playgrounds"). Never invent values. |
| Walk minutes | Network walk at 4.8 km/h from the cell centroid snapped to the network. **Cap at 60.0** when no POI is reachable within 60 min (that means "none nearby", not missing). Store raw minutes as float; don't round to integers. |
| Shares | Percent **0–100**, not 0–1. |
| Counts | Integer-valued floats (NaN is allowed, so the dtype is float). |
| Admin ids | Strings, stable across runs. K: dzielnica number `"1"`…`"18"`. P: RÚIAN kód MOMC (e.g. `"500054"` = Praha 1). |

## 1. `grid.geojson`

A `FeatureCollection` of H3 res-9 **Polygon** features: every cell whose centroid lies inside the city boundary (habitable or not).

| Field | Type | Notes |
|---|---|---|
| `feature.id` | int | Row index 0…n-1, **same order as `features.parquet`**. MapLibre `feature-state` needs a numeric id. |
| `properties.h3` | str | res-9 cell |
| `properties.district_id` | str | district (K: dzielnica, P: městská část). Cells on a boundary go to the district holding the majority of the cell's area, or else the one containing the centroid. |
| `properties.district_name` | str | e.g. `"Stare Miasto"`, `"Praha 8"` |
| `properties.neighborhood` | str \| null | K: nearest OSM `place=suburb\|quarter\|neighbourhood` name. P: katastrální území name. |
| `properties.habitable` | bool | `address_count >= habitableMinAddresses` from the city yaml |
| `properties.population_est` | int | address-point count used as a population proxy (0 when none) |

Expected size: K ≈ 3,100 cells, P ≈ 4,700 cells, about 3–5 MB each.

## 2. `features.parquet`

One row per grid cell, **same cells and order as `grid.geojson`**.

**Identity columns (required):**

| column | dtype | notes |
|---|---|---|
| `h3` | string | res-9 |
| `lat`, `lon` | float64 | cell centroid |
| `habitable` | bool | same as grid |
| `district_id`, `district_name` | string | same as grid |
| `neighborhood` | string (nullable) | same as grid |
| `population_est` | int32 | same as grid |

**Indicator columns (required):** every indicator in `indicators.yaml` that applies to the city, named `<criterion>.<indicator>`, dtype **float32 or float64**. If you have no data for one yet, **write the column anyway, all-NaN**. The engine reports it as 0% coverage and drops it from the average. Leave out indicators restricted to the other city (`cities:`). Leave out alias indicators (those with `column:` in the yaml; the engine reads the referenced column) and the runtime criterion `commute`.

| column | unit | expected range | cities | P | notes |
|---|---|---|---|---|---|
| `transit.stop_walk_min` | min | 0–60 (cap 60 = none within 60 min) | krakow, praha | P0 | Nearest stop (any GTFS stop); crossCity |
| `transit.tram_stop_walk_min` | min | 0–60 | krakow, praha | P1 | Nearest tram stop (GTFS `route_type` 0); crossCity |
| `transit.departures_per_h_500m` | dep_h | 0–600 | krakow, praha | P0 | Departures/h at stops within 500 m, Mon–Fri 07–09 (mean per hour); crossCity |
| `transit.lines_500m` | count | ≥ 0 | krakow, praha | P1 | Distinct `route_id`s serving stops within 500 m; crossCity |
| `transit.rail_station_walk_min` | min | 0–60 | krakow, praha | P0 | K: rail/SKA stations. P: metro + S-train stations; crossCity |
| `transit.night_departures_500m` | count | ≥ 0 | krakow, praha | P1 | Departures 23:00–05:00 within 500 m on one weeknight; crossCity |
| `active.cycleway_km_1km` | km | 0–100 | krakow, praha | P0 | Cycle-infrastructure length within 1 km; crossCity |
| `active.intersection_density` | per_km2 | 0–1000 | krakow, praha | P1 | Walkable-network intersections (degree ≥ 3) per km² within 500 m; crossCity |
| `active.bike_racks_300m` | count | ≥ 0 | krakow, praha | P1 | crossCity |
| `active.car_free_walk_min` | min | 0–60 | krakow, praha | P1 | River embankment / pedestrian zone; crossCity |
| `active.bikeshare_walk_min` | min | 0–60 | praha | P2 | |
| `green.green_share_500m` | pct | 0–100 | krakow, praha | P0 | Share of the 500 m buffer that is park/forest/meadow/garden; crossCity |
| `green.park_walk_min` | min | 0–60 | krakow, praha | P0 | Park ≥ 2 ha; crossCity |
| `green.forest_meadow_ha_1km` | ha | 0–315 | krakow, praha | P1 | crossCity |
| `education.nursery_walk_min` | min | 0–60 | krakow, praha | P0 | żłobek / jesle; crossCity |
| `education.kindergarten_walk_min` | min | 0–60 | krakow, praha | P0 | przedszkole / MŠ; crossCity |
| `education.primary_school_walk_min` | min | 0–60 | krakow, praha | P0 | crossCity |
| `education.secondary_school_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `education.university_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `education.library_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `family.playgrounds_500m` | count | ≥ 0 | krakow, praha | P0 | crossCity |
| `family.paediatrician_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `family.kids_sports_walk_min` | min | 0–60 | krakow, praha | P1 | Pool or kids' sports; crossCity |
| `safety.crime_per_1000` | per_1000 | 0–1000 | krakow, praha | P0 | **District level**: every cell of a district gets the district value |
| `safety.lit_share` | pct | 0–100 | krakow, praha | P1 | Share of street length with `lit=yes` within 500 m; crossCity |
| `price.buy_per_m2` | pln_m2 | 2000–60000 | krakow | P0 | RCN flats, last 24 months, IQR-filtered median with k-ring smoothing |
| `price.rent_per_m2` | czk_m2_month | 100–1500 | praha | P0 | MF rent map median per k.ú., joined to cells by majority overlap |
| `price.discount_grocery_walk_min` | min | 0–60 | krakow, praha | P1 | Biedronka, Lidl, Aldi, Netto, Penny…; crossCity |
| `shops.supermarket_walk_min` | min | 0–60 | krakow, praha | P0 | crossCity |
| `shops.post_parcel_walk_min` | min | 0–60 | krakow, praha | P1 | Post office or parcel locker; crossCity |
| `shops.bakery_walk_min` | min | 0–60 | krakow, praha | P2 | crossCity |
| `shops.marketplace_walk_min` | min | 0–60 | krakow, praha | P2 | crossCity |
| `shops.atm_walk_min` | min | 0–60 | krakow, praha | P2 | crossCity |
| `shops.shops_10min` | count | ≥ 0 | krakow, praha | P1 | All `shop=*` within a 10-min walk; crossCity |
| `health.gp_walk_min` | min | 0–60 | krakow, praha | P0 | crossCity |
| `health.pharmacy_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity (also read by `shops.pharmacy_walk_min` and must-have `pharmacy`) |
| `health.hospital_er_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `health.maternity_walk_min` | min | 0–60 | krakow, praha | P1 | P: NRPZS inpatient gynaecology & obstetrics; crossCity |
| `health.gynaecology_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `health.dentist_walk_min` | min | 0–60 | krakow, praha | P2 | crossCity |
| `environment.noise_db` | db | 30–90 | krakow, praha | P0 | Area-weighted mean of max(road, tram, rail). K: Lden, P: LAeq day / Ldvn. Record which one in the manifest note. Not crossCity (since 10-03 18:00) |
| `environment.pm25` | ugm3 | 0–150 | krakow, praha | P0 | Annual mean. K: GIOŚ IDW, P: ČHMÚ 5-yr 1×1 km grid. Not crossCity |
| `environment.pm10` | ugm3 | 0–150 | krakow, praha | P0 | Not crossCity |
| `environment.major_road_m` | m | 0–20000 | krakow, praha | P1 | Distance to motorway/trunk/primary; crossCity |
| `environment.industrial_ha_1km` | ha | 0–315 | krakow, praha | P1 | `landuse=industrial` within 1 km; crossCity |
| `leisure.food_10min` | count | ≥ 0 | krakow, praha | P1 | Restaurants + cafés; crossCity |
| `leisure.culture_walk_min` | min | 0–60 | krakow, praha | P1 | Theatre, cinema, museum, gallery, arts centre; crossCity |
| `leisure.sports_walk_min` | min | 0–60 | krakow, praha | P1 | crossCity |
| `leisure.nightlife_10min` | count | ≥ 0 | krakow, praha | P1 | Bars, pubs, nightclubs; crossCity |
| `accessibility.accessible_stop_share` | pct | 0–100 | krakow, praha | P0 | Share of stops within 500 m with GTFS `wheelchair_boarding=1`; crossCity |
| `accessibility.lowfloor_trip_share` | pct | 0–100 | krakow, praha | P0 | Share of trips at stops within 500 m with `wheelchair_accessible=1`; crossCity |
| `accessibility.benches_300m` | count | ≥ 0 | krakow, praha | P1 | crossCity |
| `accessibility.slope_pct` | pct | 0–100 | krakow, praha | P2 | Mean slope from a DEM; crossCity |

**Auxiliary columns.** These are read by filters and the UI, but they are not scored:

| column | dtype | cities | notes |
|---|---|---|---|
| `poi.metro_station_walk_min` | float | praha (required) | walk minutes to a metro station only (must-have filter `metro_station`) |
| `price.buy_n_transactions` | float | krakow (optional) | RCN transactions behind the cell median (confidence) |
| `aux.*` | any | optional | free for A's own QA; the engine ignores them |

The engine **rejects** any other column not listed here (to catch typos).

## 3. `pois.parquet`

| column | dtype | notes |
|---|---|---|
| `category` | string | from the vocabulary below |
| `name` | string (nullable) | original-language name |
| `lat`, `lon` | float64 | WGS84 |
| `h3_9` | string | res-9 cell containing the POI |
| `source` | string | manifest key, e.g. `osm_krakow`, `nrpzs`, `msmt_schools` |
| `extra_json` | string (nullable) | JSON object, e.g. `{"wheelchair":"yes","specialty":"gynekologie"}` |

**Category vocabulary (shared by both cities, snake_case):**
`supermarket, discount_grocery, pharmacy, post_office, parcel_locker, bakery, marketplace, atm, playground, park, nursery, kindergarten, primary_school, secondary_school, university, library, gp_clinic, paediatrician, gynaecology, dentist, hospital_er, maternity_ward, bus_stop, tram_stop, metro_station, rail_station, bike_rack, bikeshare_station, culture, sports, kids_sports, restaurant, cafe, bar, nightclub, bench`

Extend it only additively and tell B. The engine uses it for the "nearest amenities" list, the geocoder (`university` drives the student's suggested anchor) and mustHave categories. Keep it under 50 MB: drop benches and bike racks outside the routing area if needed.

## 3b. `addresses.parquet` (optional, added in contracts-v2)

The address points behind the local geocoder (K: MSIP EMUiA, P: RÚIAN). If this file is missing, the geocoder searches only places and POIs and falls back to Photon for addresses.

| column | dtype | notes |
|---|---|---|
| `street` | string | street name with diacritics (`"Rakowicka"`, `"Vinohradská"`). P: use the place name (`nazev_casti_obce`) when an address has no street. |
| `housenumber` | string | as displayed: `"27"`, `"12a"`, `"1234/5"` (P: číslo popisné/orientační) |
| `postcode` | string (nullable) | |
| `lat`, `lon` | float64 | WGS84 (P: mind the EPSG:5514 sign flip) |
| `h3_9` | string | res-9 cell |
| `source` | string | manifest key (`msip`, `ruian`) |

Keep it under 50 MB. If needed, drop the extra columns or keep only addresses inside the city boundary.

## 4. `travel_times.npz`

Written with `numpy.savez_compressed`.

| array | dtype | shape | notes |
|---|---|---|---|
| `origins` | `<U15` | (n_o,) | res-9 h3 of **habitable** cells |
| `dests` | `<U15` | (n_d,) | res-8 h3 of **all** res-8 cells covering the city |
| `transit` | uint8 | (n_o, n_d) | minutes, transit + walk, weekday 08:00, median over a 30-min window |
| `bike` | uint8 | (n_o, n_d) | minutes |
| `walk` | uint8 | (n_o, n_d) | minutes |
| `meta_json` | `<U…` | () | optional JSON: `{"date":"2026-10-07","departure":"08:00","method":"r5py"\|"fallback"}` |

**255 = unreachable or > 120 min.** Missing mode: omit the array. The engine then disables that mode for the city and says so in `/meta`.

## 5. `districts.geojson` and `neighborhoods.geojson`

`FeatureCollection` of Polygon/MultiPolygon in EPSG:4326, simplified to about 10 m tolerance.

| property | type | notes |
|---|---|---|
| `id` | str | same ids as `grid.district_id` (districts) |
| `name` | str | |
| `district_id` | str \| null | neighborhoods only: the parent district, if known |
| `population_est` | int \| null | |

## 6. `manifest.json`

```json
{
  "city": "krakow",
  "dataVersion": "2026-10-03T18:00:00Z",
  "builtAt": "2026-10-03T18:00:00Z",
  "sources": [
    {"key": "osm_krakow", "url": "https://download.geofabrik.de/…", "fetchedAt": "2026-10-03T12:01:00Z",
     "licence": "ODbL 1.0", "rows": 48211, "status": "ok", "note": null}
  ]
}
```

- `status` ∈ `ok | fallback | missing`.
- Use the source keys from README §4, which the `sources:` lists in `indicators.yaml` reference.
- `dataVersion` is any string that changes whenever the data changes (ISO timestamp recommended). `/api/health` shows it.

## 7. `_shared/` (pooled across cities)

- `data/processed/_shared/ml_features.parquet` (**optional**): `city, h3, habitable` + all `crossCity: true` indicator columns for both cities. If it is absent, the engine derives the same table from each `features.parquet`.
- **ML models are not written into `data/`.** B trains them and keeps them in `engine/models/` (see `docs/DECISIONS.md`).

## 8. Validation (run before every push to `a-data`)

```bash
uv run contracts/tools/validate_data.py --city all        # errors → exit 1, warnings printed
uv run contracts/tools/validate_data.py --city krakow --data-dir data/processed
```

**Required files:** `grid.geojson`, `features.parquet`, `manifest.json`. Without them the engine won't load the city.
**Optional files:** `pois.parquet`, `addresses.parquet`, `travel_times.npz`, `districts.geojson`, `neighborhoods.geojson`. Without them the engine runs degraded (no nearest list / commute / outlines) and says so.

**Errors:** missing required file, missing or unknown column, wrong dtype, invalid h3, grid/features mismatch, shape mismatch in npz, file > 50 MB, bad manifest.
**Warnings:** values outside the expected range, NaN share > 20% per column, coverage per criterion. Paste the NaN report into `docs/DATA_SOURCES.md`.

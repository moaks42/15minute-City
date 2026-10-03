# Data sources, methods and coverage

**Owner:** Workstream A (`pipeline/`). Rebuild everything with `cd pipeline && make data CITY=all`.
The handoff is `data/processed/{krakow,praha,_shared}/`, in the layout of [`contracts/DATA_CONTRACT.md`](../contracts/DATA_CONTRACT.md).
Every source also has an entry (URL, fetch time, licence, rows used, status, note) in `data/processed/{city}/manifest.json`. The "About the data" page renders that file.

All sources below were checked with a real request on **2026-10-03**. Where the README's URL had moved, the table gives the URL that works and says so.

---

## 1. How the pipeline works

| Step | Command | What it does |
|---|---|---|
| fetch | `python fetch.py --city X` | Downloads every source listed in `pipeline/settings/X.yaml` into `data/raw/X/` (gitignored), with paging for ArcGIS, Golemio and Police ČR. It is idempotent and records each source in the manifest. |
| build | `python run.py --city X` | Builds the H3 grid, habitable mask, labels, POIs, walk network and indicators, then writes `grid.geojson`, `features.parquet`, `pois.parquet`, `districts.geojson` and `neighborhoods.geojson`. Takes about 70 s per city. |
| travel | `python travel.py --city X` | r5py commute matrices → `travel_times.npz`. Takes about 12 min (K) and 20 min (P). |
| ml | `python ml_features.py` | Writes `_shared/ml_features.parquet`, which pools the `crossCity` indicators of both cities. |
| (build) | also writes `geocode.parquet` | Local geocoder index (EMUiA / RÚIAN addresses, streets, neighbourhoods, districts) with an accent-free search key. |
| validate | `python validate.py --city all [--write-docs]` | Runs B's contract validator (`contracts/tools/validate_data.py`), then the README §5 sanity checks, then refreshes §5 of this file. |

**City-agnostic core** (`pipeline/core/`), identical for both cities:
- **Grid:** H3 v4 res 9 over the city boundary (centroid rule).
- **Labels:** majority-area overlap.
- **Habitable mask:** at least `habitableMinAddresses` (3) address points per cell.
- **Population proxy:** address points per cell.
- **OSM:** the regional PBF is clipped with osmium to the city plus a 5 km buffer.
- **POIs:** one shared category vocabulary (`core/pois.py`).
- **Walk network:** built straight from OSM highway geometry. Shared vertices become nodes, and walk minutes come from a multi-source Dijkstra at 4.8 km/h, snapped at both ends and capped at 60.
- **GTFS stop statistics:** taken on one weekday.
- **Land-use shares:** 20 m raster with disk convolution.
- **Street indicators:** cycleways, lit streets, intersections, major roads.

**City adapters** (`pipeline/adapters/{krakow,praha}/`) write the *same* `<criterion>.<indicator>` columns from local sources (registers, noise maps, air, crime, prices).

Fixed parameters:
- **Service date:** Tuesday **2026-10-06**. It is the first common weekday in both cities' feeds; the PID feed only covers 10-03…10-16.
- **Peak window:** 07:00–09:00, reported as departures per hour.
- **Night window:** 23:00–05:00.
- **Commute:** departure 08:00 with a 30-minute window (median), at most 120 min, where 255 means unreachable.
- **CRS:** everything is stored in EPSG:4326. Buffers use EPSG:2180 (K) and EPSG:5514 (P).

---

## 2. Kraków

| key | source | URL (verified 2026-10-03) | licence | used for |
|---|---|---|---|---|
| `osm_krakow` | OpenStreetMap, Małopolskie extract | https://download.geofabrik.de/europe/poland/malopolskie-latest.osm.pbf | ODbL 1.0 | POIs, walk network, green/forest/industrial land use, cycleways, lit streets, intersections, major roads, neighbourhood names (`place=*`) |
| `gtfs_ztp_a`, `gtfs_ztp_t` | ZTP Kraków GTFS, bus (A) and tram (T) | https://gtfs.ztp.krakow.pl/GTFS_KRK_A.zip, `…_T.zip` | ZTP open data | transit indicators, r5py routing |
| `gtfs_rt_ztp` | ZTP GTFS-RT | https://gtfs.ztp.krakow.pl/VehiclePositions_A.pb (+ TripUpdates, ServiceAlerts) | ZTP open data | live departures (P2, engine) |
| `msip_districts` | MSIP: 18 dzielnic | https://msip.um.krakow.pl/Dane/Dzielnice_JSON.zip | UM Kraków open data | boundary, `district_id` "1"…"18" |
| `msip_addresses` | MSIP: EMUiA address points (70,217) | https://msip.um.krakow.pl/Dane/Adresy_JSON.zip | UM Kraków open data | habitable mask, population proxy, school geocoding |
| `msip_noise` | MSIP strategic noise map 2022 ("Mapa imisyjna", Lden/LDWN) | https://msip.um.krakow.pl/Dane/Mapa_Halasu_2022_JSON.zip | UM Kraków open data | `environment.noise_db` |
| `men_schools` | MEN SIO register of schools (as of 30.09.2025), powiat 1261 | https://api.dane.gov.pl/resources/1254769,…/file | CC BY 4.0 | kindergartens, primary and secondary schools |
| `nfz` | NFZ "Informator o terminach leczenia" API | https://api.nfz.gov.pl/app-itl-api/queues | NFZ open API | maternity wards, gynaecology clinics |
| `rcn` | Kraków Real-Estate Price Register (WFS, layer `ms:lokale`) | https://geodezja.eco.um.krakow.pl/cgi-bin/krakow-rcn | public register (UM Kraków, Wydział Geodezji) | `price.buy_per_m2`, `price.buy_n_transactions` |
| `rcn_gugik` | GUGiK national RCN WFS | https://mapy.geoportal.gov.pl/wss/service/rcn | GUGiK | reference only |
| `safety_krk` | "Przestępstwa w przestrzeni publicznej 2023" (141 units), GMK ArcGIS | https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Przestepstwa_ogolem_msc_pub_2022_mapa/FeatureServer/0 | UM Kraków / Bezpieczny Kraków | `safety.crime_per_1000` |
| `gus_bdl` | GUS BDL population of powiat m. Kraków (var 72305) | https://bdl.stat.gov.pl/api/v1/data/by-unit/011212161000?var-id=72305 | CC BY 4.0 | denominator of the crime rate |
| `gios` | GIOŚ stations + annual PM statistics (Małopolska) | https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll, `…/statistics/getStatisticsForPollutants` | GIOŚ (cite "GIOŚ") | `environment.pm10`, `environment.pm25`; live air in the engine |
| `ztp_hub_bike_racks` | ZTP bike racks (stojaki), ArcGIS Hub | `…/Stojaki_ZTP_wyświetlenie/FeatureServer/1` | ZTP Kraków | POI `bike_rack` → `active.bike_racks_300m` |
| `ztp_hub_*` | ZTP cycle lines, mobility points, P+R | ArcGIS org `svTzSt3AvH7sK6q9` | ZTP Kraków | reference / P2 |
| `krk_open`, `park_e_bike`, `basemap`, `geocode`, `overpass` | portals and services | see manifest | — | checked for reachability. `overpass` was unreachable from the venue network, so we use the PBF instead |

**Kraków transformations and caveats**
- **Schools (MEN):** we kept `Przedszkole`, `Punkt przedszkolny` and `Zespół wychowania przedszkolnego` (kindergarten), `Szkoła podstawowa` (primary), and liceum, technikum and branżowa I st. for children and youth (secondary). We geocoded them with EMUiA: 819 exact matches on street + number, and 11 placed at the street centroid. Żłobki are not in SIO, so nurseries come from OSM (`amenity=childcare|kindergarten` with the name "żłobek").
- **Price (RCN):** 24 months of `DOK_DATA` (30,581 records). We kept residential units sold on the free market with 15–250 m² of usable area, then applied an IQR filter, leaving 23,022 sales. The cell value is the median zł/m² over an H3 k-ring, growing k = 0…3 until n ≥ 5; otherwise it is NaN (12% of habitable cells). Multi-unit transactions without a unit price are dropped.
- **Safety:** each unit's offences are split across dzielnice by area. Residents are the latest GUS total (816,614 in 2025) split by each district's share of EMUiA addresses. The data covers **public-space offences only** (715 in 2023), so absolute rates are *not* comparable with Praha. The engine normalises within the city.
- **Noise:** we rasterised the 5-dB bands at 10 m and took the maximum of the road layer and the rail + tram layer. The cell value is the mean within 180 m of the centroid. The open band "<55" counts as 50 dB. The industrial layer has no dB attribute, so it is not used.
- **Air:** each GIOŚ station gets the mean of its annual means for the last 3 years (completeness ≥ 75%, daily series preferred). We interpolate with IDW (p = 2) from stations within 25 km: 10 for PM10 and 4 for PM2.5.
- **Paediatrics:** in Poland, children's primary care is delivered by POZ (GP) clinics. So `family.paediatrician_walk_min` measures the walk to the nearest paediatric clinic or GP clinic.
- **Accessibility:** the ZTP GTFS has no `wheelchair_boarding` or `wheelchair_accessible` values, so `accessible_stop_share` and `lowfloor_trip_share` are NaN in Kraków (beta). OSM stop tags cover only 18% of stops, too few to use.

## 3. Praha

| key | source | URL (verified 2026-10-03) | licence | used for |
|---|---|---|---|---|
| `osm_praha` | OpenStreetMap, Středočeský kraj extract (includes Praha) | https://download.geofabrik.de/europe/czech-republic/stredocesky-latest.osm.pbf | ODbL 1.0 | as for Kraków |
| `gtfs_pid` | PID GTFS (metro, tram, bus, S-trains, ferries) | https://data.pid.cz/PID_GTFS.zip | CC BY 4.0 (PID / ROPID) | transit indicators, r5py routing |
| `gtfs_pid_stops` | PID stops JSON | https://data.pid.cz/stops/json/stops.json | CC BY 4.0 | reference (live departures) |
| `ipr_mestske_casti` | IPR: 57 městských částí | https://mp.iprpraha.cz/arcgis/rest/services/Hosted/MAP_CUR_MAP_MESTSKECASTI_P/FeatureServer/0 | CC BY 4.0 (IPR Praha) | boundary, `district_id` = RÚIAN kód MOMC |
| `ipr_katastralni_uzemi` | IPR: 112 katastrálních území | https://services5.arcgis.com/SBTXIEUGWbqzUecw/arcgis/rest/services/katastry/FeatureServer/0 | CC BY 4.0 (IPR / ČÚZK) | `neighborhood`, rent-map join |
| `ipr_noise_day` | IPR road-traffic noise map, day ("Hluková mapa automobilové dopravy – den") | https://lkod-iprpraha.hub.arcgis.com/api/download/v1/items/6ea612215c8646dab1ea975aa64276b5/geojson?layers=0 | CC BY 4.0 | `environment.noise_db` |
| `ipr_parks` | IPR "Parky (ÚAP)" | https://mp.iprpraha.cz/arcgis/rest/services/Hosted/URK_CUR_URK_PARKY_P/FeatureServer/0 | CC BY 4.0 | parks ≥ 2 ha (together with OSM) |
| `ruian` | ČÚZK RÚIAN address points, obec 554782 (134,670) | https://vdp.cuzk.gov.cz/vymenny_format/csv/20260930_OB_554782_ADR.csv.zip (via ATOM `RUIAN-CSV-ADR-OB`) | CC BY 4.0 | habitable mask, population proxy, school and nursery geocoding |
| `msmt_schools` | MŠMT Register of schools, Hl. m. Praha (JSON-LD) | https://lkod-ftp.msmt.gov.cz/00022985/21e5fd4a-5378-4d64-90e9-759b15d01f28/RSSZ-Hl-m-Praha.jsonld | CC BY 4.0 | kindergartens (A00), primary (B00), secondary (C00) |
| `mpsv_detske_skupiny` | MPSV register of dětské skupiny | https://data.mpsv.cz/portal/api/reports/by-table/detske_skupiny_evid_poskyt_seznam_akt_odata/data/csv | MPSV open data | nurseries |
| `nrpzs` | ÚZIS NRPZS places of care (GPS + specialties) | https://datanzis.uzis.gov.cz/data/NR-01-NRPZS/NR-01-06/Otevrena-data-NR-01-06-nrpzs-mista-poskytovani-zdravotnich-sluzeb.csv | CC BY 4.0 | GP, paediatrics, gynaecology, maternity, ER, dentists, pharmacies |
| `chmi_air` | ČHMÚ 5-year average 2020–2024 on a 1×1 km grid (S-JTSK) | https://opendata.chmi.cz/air_quality/products/5year_avg/sit1000_5lprum_20_24_CR_JTSK.zip | ČHMÚ open data | `environment.pm10`, `environment.pm25` (+ `aux.environment_no2`) |
| `police_cz` | Police ČR crime map, last 12 complete months (2025-10…2026-09) | https://kriminalita.policie.gov.cz/api/v2/downloads/{YYYYMM}.zip (+ `voronoi.geojson.zip`, `types.json`) | **Policie ČR: non-commercial use only** | `safety.crime_per_1000` |
| `csu_population` | ČSÚ OBY01B01 municipal population | https://data.csu.gov.cz/opendata/sady/OBY01B01/distribuce/csv | CC BY 4.0 | denominator of the crime rate |
| `mf_rent` | MF ČR rent price map (cenová mapa nájemného), 2026-08-15 | https://mf.gov.cz/assets/attachments/2026-08-15_Cenova-mapa.xlsx | MF ČR | `price.rent_per_m2` |
| `golemio_*` | Golemio API: playgrounds, gardens, libraries, air stations, districts, medical | https://api.golemio.cz/v2/… (key in `.env`, header `X-Access-Token`) | CC BY 4.0 (Golemio / OICT) | playground, park and library POIs; live air |
| `basemap`, `geocode`, `praha_open`, `chmi_air_now_meta`, `bikeshare_praha` | services and portals | see manifest | — | reachability checks. `bikeshare_praha` failed on TLS and no GBFS was found (P2) |

**URLs that differ from the README:**
- The MŠMT XML (`rejstriky.msmt.cz/opendata/vrejcz010.xml`) returns **404** because the site moved to isv.gov.cz. We use the MŠMT LKOD JSON-LD, which we found through the NKOD SPARQL endpoint.
- The IPR "Hluková mapa – den" (all sources) layer gives 20–25 dB beside the Magistrála. The road-traffic layer gives 70–75 dB there, so we use the road-traffic layer.

**Praha transformations and caveats**
- **RÚIAN:** the CSV is cp1250 with `;` separators. Its coordinates are positive Y/X, so EPSG:5514 uses **x = −Y, y = −X**. We checked this against Pražský hrad (Hrad I. nádvoří 1 ≈ 50.0905 N, 14.4005 E).
- **Schools (MŠMT):** each *místo výuky* (teaching location) is geocoded through its RÚIAN address code, which matches exactly. 70 codes are unmatched (locations outside Praha or without a code).
- **Nurseries (MPSV):** 433 active dětské skupiny. 417 are geocoded by street + house number in RÚIAN, and 16 are unmatched. OSM `jesle` are added on top.
- **Health (NRPZS)**, region CZ010:

  | Category | Rule |
  |---|---|
  | GP | type "Samost. ordinace všeob. prakt. lékaře" or specialty "všeobecné praktické lékařství" |
  | Paediatrics | "… pro děti a dorost" |
  | Gynaecology | "… gynekologa", or outpatient "gynekologie a porodnictví" |
  | **Maternity** | hospital types (fakultní / nemocnice / specializovaná) with *inpatient* "gynekologie a porodnictví" or neonatology: 14 sites |
  | **ER** | fakultní nemocnice or nemocnice with "urgentní medicína" or anaesthesiology: 16 sites |

  Pharmacies are type "Lékárna". Hospitals are never hard-coded.
- **Air:** the ČHMÚ annual mean of the grid square that contains the cell centroid.
- **Crime:** we keep criminal offences only and drop přestupky (misdemeanours), traffic accidents and fires. Locations are anonymised by the police into Voronoi cells, then joined to městská část. Residents are the ČSÚ total (1,398,674 on 1 July 2025) split by each MČ's share of RÚIAN addresses. Praha 1 shows about 95 offences per 1,000 residents, because it has few residents and many visitors. **The licence is non-commercial**, which is fine for a prototype; commercial use needs a different source (see the roadmap).
- **Rent (MF):** the median Kč/m²/month of each k.ú., taken as the median across flat-size categories. It is joined on k.ú. code, with name matching as a fallback, and cells take the value of their majority k.ú.
- **Noise:** **road traffic only**, LAeq day, 5-dB bands. IPR publishes no tram or rail layer, so Kraków (max of road and rail + tram, Lden) and Praha are not on an identical basis. That is fine within a city, but treat it with care in cross-city twins.

---

## 4. Indicator methods (both cities)

| column(s) | method |
|---|---|
| `*_walk_min` | Network walk from the cell centroid (snapped) to the nearest POI of the category (snapped), at 4.8 km/h. **60 means none within 60 min.** |
| `transit.stop_walk_min`, `transit.tram_stop_walk_min`, `transit.rail_station_walk_min` | GTFS stops with weekday service. Rail = GTFS rail/metro stops ∪ OSM `railway=station\|halt` (K: SKA/PKP; P: metro + S-trains). |
| `transit.departures_per_h_500m` | Sum over stops within 500 m (euclidean) of departures 07–09 ÷ 2. Counts every platform, so a trip that stops at two nearby platforms counts twice. |
| `transit.lines_500m`, `transit.night_departures_500m` | Distinct `route_id`s, and departures 23:00–05:00, at stops within 500 m |
| `active.cycleway_km_1km` | OSM `highway=cycleway`, `cycleway*=lane\|track`, and paths with `bicycle=designated`: length within 1 km |
| `active.intersection_density` | Street-network nodes of degree ≥ 3 within 500 m, per km² |
| `active.car_free_walk_min` | Walk to the nearest pedestrian zone (`highway=pedestrian`) or riverside path (footway/path/cycleway ≤ 60 m from river water) |
| `green.green_share_500m` | % of a 500 m disk covered by parks, gardens, forest, meadow, grass, allotments, cemeteries and nature reserves (OSM) |
| `green.forest_meadow_ha_1km`, `environment.industrial_ha_1km` | Hectares of forest/meadow/wood/scrub/grassland, or of `landuse=industrial`, within 1 km |
| `green.park_walk_min` | Walk to the edge of a park ≥ 2 ha (OSM `leisure=park\|nature_reserve\|recreation_ground`; P: + IPR parks) |
| counts `*_500m`, `*_300m`, `*_10min` | POIs within a euclidean radius. "10 min" = 800 m, which is about a 10-minute walk on the network. |
| `safety.lit_share` | % of street length (residential and up) within 500 m tagged `lit=yes\|24/7\|automatic\|limited` in OSM |
| `environment.major_road_m` | Euclidean distance to motorway, trunk or primary roads |
| `accessibility.accessible_stop_share`, `accessibility.lowfloor_trip_share` | GTFS `wheelchair_boarding=1` share of stops, and `wheelchair_accessible=1` share of 07–09 departures, within 500 m (P only) |
| `accessibility.slope_pct` | Copernicus GLO-30 DEM: reprojected at 30 m, Gaussian-smoothed (σ = 60 m, because the source is a surface model), slope %, mean within 180 m. Letná hillside 15%, Petřín 8%, flat areas about 3% (residual). |
| `travel_times.npz` | r5py 1.1.7 (R5 7.5): transit + walk (median over 08:00–08:30), bike, walk. Origins are habitable res-9 cells, destinations are all res-8 cells. PID GTFS: R5 rejects empty `stop_name` on the 629 `location_type=3` nodes, so we fill those from the parent station and drop `pathways.txt`. Bike uses R5 defaults (12 km/h, level of traffic stress ≤ 3), so bike times are conservative. Spot checks: K Rynek→Zabłocie 22 min transit / 18 min bike; P Karlín→Václavské nám. 16 / 19; P Zličín→Černý Most 53 min transit. |

---

## 5. Coverage, NaN report and sanity checks (generated)

Generated by `python validate.py --city all --write-docs`. Coverage is the weight-averaged share of habitable cells with data for each criterion, which is how the engine computes it. `commute` is computed at runtime from `travel_times.npz`.

<!-- coverage:krakow:start -->
#### krakow — built 2026-10-03T15:03:47+00:00

| criterion | coverage (weighted) | indicators with data / total |
|---|---|---|
| transit | 100% | 6/6 |
| active | 100% | 4/4 |
| green | 100% | 3/3 |
| education | 100% | 6/6 |
| family | 100% | 3/3 |
| safety | 100% | 2/2 |
| price | 88% | 2/2 |
| shops | 100% | 6/6 |
| health | 100% | 6/6 |
| environment | 100% | 5/5 |
| leisure | 100% | 4/4 |
| accessibility | 33% | 2/4 |

<details><summary>NaN share per column (habitable cells)</summary>

| column | NaN share |
|---|---|
| `accessibility.accessible_stop_share` | 100.0% |
| `accessibility.benches_300m` | 0.0% |
| `accessibility.lowfloor_trip_share` | 100.0% |
| `accessibility.slope_pct` | 0.0% |
| `active.bike_racks_300m` | 0.0% |
| `active.car_free_walk_min` | 0.0% |
| `active.cycleway_km_1km` | 0.0% |
| `active.intersection_density` | 0.0% |
| `education.kindergarten_walk_min` | 0.0% |
| `education.library_walk_min` | 0.0% |
| `education.nursery_walk_min` | 0.0% |
| `education.primary_school_walk_min` | 0.0% |
| `education.secondary_school_walk_min` | 0.0% |
| `education.university_walk_min` | 0.0% |
| `environment.industrial_ha_1km` | 0.0% |
| `environment.major_road_m` | 0.0% |
| `environment.noise_db` | 0.0% |
| `environment.pm10` | 0.0% |
| `environment.pm25` | 0.0% |
| `family.kids_sports_walk_min` | 0.0% |
| `family.paediatrician_walk_min` | 0.0% |
| `family.playgrounds_500m` | 0.0% |
| `green.forest_meadow_ha_1km` | 0.0% |
| `green.green_share_500m` | 0.0% |
| `green.park_walk_min` | 0.0% |
| `health.dentist_walk_min` | 0.0% |
| `health.gp_walk_min` | 0.0% |
| `health.gynaecology_walk_min` | 0.0% |
| `health.hospital_er_walk_min` | 0.0% |
| `health.maternity_walk_min` | 0.0% |
| `health.pharmacy_walk_min` | 0.0% |
| `leisure.culture_walk_min` | 0.0% |
| `leisure.food_10min` | 0.0% |
| `leisure.nightlife_10min` | 0.0% |
| `leisure.sports_walk_min` | 0.0% |
| `price.buy_per_m2` | 16.5% |
| `price.discount_grocery_walk_min` | 0.0% |
| `safety.crime_per_1000` | 0.0% |
| `safety.lit_share` | 0.0% |
| `shops.atm_walk_min` | 0.0% |
| `shops.bakery_walk_min` | 0.0% |
| `shops.marketplace_walk_min` | 0.0% |
| `shops.post_parcel_walk_min` | 0.0% |
| `shops.shops_10min` | 0.0% |
| `shops.supermarket_walk_min` | 0.0% |
| `transit.departures_per_h_500m` | 0.0% |
| `transit.lines_500m` | 0.0% |
| `transit.night_departures_500m` | 0.0% |
| `transit.rail_station_walk_min` | 0.0% |
| `transit.stop_walk_min` | 0.0% |
| `transit.tram_stop_walk_min` | 0.0% |

</details>

| sanity check (README §5) | result | detail |
|---|---|---|
| Stare Miasto top for transit | ✅ pass | rank 1/18 by median departures/h |
| Stare Miasto top for leisure | ✅ pass | rank 1/18 by median food venues within 10 min |
| Stare Miasto low for quiet (loud) | ✅ pass | rank 6/18 loudest by median noise |
| Stare Miasto low for price (expensive) | ✅ pass | rank 1/18 most expensive by median zł/m² |
| Nowa Huta steelworks area worse for air | ✅ pass | median PM10 percentile within 3 km = 0.78 |
| Las Wolski / Bielany / Wola Justowska top for green | ✅ pass | median green-share percentile = 0.95 |

<!-- coverage:krakow:end -->

<!-- coverage:praha:start -->
#### praha — built 2026-10-03T15:04:59+00:00

| criterion | coverage (weighted) | indicators with data / total |
|---|---|---|
| transit | 100% | 6/6 |
| active | 100% | 5/5 |
| green | 100% | 3/3 |
| education | 100% | 6/6 |
| family | 100% | 3/3 |
| safety | 100% | 2/2 |
| price | 100% | 2/2 |
| shops | 100% | 6/6 |
| health | 100% | 6/6 |
| environment | 100% | 5/5 |
| leisure | 100% | 4/4 |
| accessibility | 97% | 4/4 |

<details><summary>NaN share per column (habitable cells)</summary>

| column | NaN share |
|---|---|
| `accessibility.accessible_stop_share` | 4.6% |
| `accessibility.benches_300m` | 0.0% |
| `accessibility.lowfloor_trip_share` | 4.6% |
| `accessibility.slope_pct` | 0.0% |
| `active.bike_racks_300m` | 0.0% |
| `active.bikeshare_walk_min` | 0.0% |
| `active.car_free_walk_min` | 0.0% |
| `active.cycleway_km_1km` | 0.0% |
| `active.intersection_density` | 0.0% |
| `education.kindergarten_walk_min` | 0.0% |
| `education.library_walk_min` | 0.0% |
| `education.nursery_walk_min` | 0.0% |
| `education.primary_school_walk_min` | 0.0% |
| `education.secondary_school_walk_min` | 0.0% |
| `education.university_walk_min` | 0.0% |
| `environment.industrial_ha_1km` | 0.0% |
| `environment.major_road_m` | 0.0% |
| `environment.noise_db` | 0.0% |
| `environment.pm10` | 0.0% |
| `environment.pm25` | 0.0% |
| `family.kids_sports_walk_min` | 0.0% |
| `family.paediatrician_walk_min` | 0.0% |
| `family.playgrounds_500m` | 0.0% |
| `green.forest_meadow_ha_1km` | 0.0% |
| `green.green_share_500m` | 0.0% |
| `green.park_walk_min` | 0.0% |
| `health.dentist_walk_min` | 0.0% |
| `health.gp_walk_min` | 0.0% |
| `health.gynaecology_walk_min` | 0.0% |
| `health.hospital_er_walk_min` | 0.0% |
| `health.maternity_walk_min` | 0.0% |
| `health.pharmacy_walk_min` | 0.0% |
| `leisure.culture_walk_min` | 0.0% |
| `leisure.food_10min` | 0.0% |
| `leisure.nightlife_10min` | 0.0% |
| `leisure.sports_walk_min` | 0.0% |
| `price.discount_grocery_walk_min` | 0.0% |
| `price.rent_per_m2` | 0.0% |
| `safety.crime_per_1000` | 0.0% |
| `safety.lit_share` | 0.1% |
| `shops.atm_walk_min` | 0.0% |
| `shops.bakery_walk_min` | 0.0% |
| `shops.marketplace_walk_min` | 0.0% |
| `shops.post_parcel_walk_min` | 0.0% |
| `shops.shops_10min` | 0.0% |
| `shops.supermarket_walk_min` | 0.0% |
| `transit.departures_per_h_500m` | 0.0% |
| `transit.lines_500m` | 0.0% |
| `transit.night_departures_500m` | 0.0% |
| `transit.rail_station_walk_min` | 0.0% |
| `transit.stop_walk_min` | 0.0% |
| `transit.tram_stop_walk_min` | 0.0% |

</details>

| sanity check (README §5) | result | detail |
|---|---|---|
| Praha 1 top for transit | ✅ pass | rank 2/57 by median departures/h |
| Praha 1 top for leisure | ✅ pass | rank 1/57 by median food venues within 10 min |
| Praha 1 low for quiet (loud) | ⚠️ fail | rank 32/57 loudest by median noise |
| cells next to metro top for rail indicator | ✅ pass | 39 cells ≤3 min from metro, 100% have rail_station_walk_min ≤ 5 |
| Ruzyně airport zone worse for noise | ✅ pass | median noise percentile within 2.5 km = 0.84 |
| Stromovka / Divoká Šárka / Hostivař top for green | ✅ pass | median green-share percentile = 0.80 |

<!-- coverage:praha:end -->

---

## 6. Attribution list (for the UI footer and the About page)

**Both cities:**
- © OpenStreetMap contributors (ODbL)
- Copernicus DEM GLO-30 (© DLR / Airbus, provided under COPERNICUS by the EU and ESA)
- Basemap © OpenFreeMap / OpenMapTiles
- Routing by r5py / R5 (Conveyal)

**Kraków:**
- ZTP Kraków (GTFS, GTFS-RT, ArcGIS Hub)
- MSIP / UM Kraków (districts, EMUiA addresses, noise map 2022, RCN)
- Bezpieczny Kraków / UM Kraków (crime 2023)
- GIOŚ (air quality)
- MEN / dane.gov.pl (SIO school register, CC BY 4.0)
- NFZ (Informator o terminach leczenia)
- GUS BDL (population)

**Praha:**
- PID / ROPID (GTFS, CC BY 4.0)
- Golemio / OICT (CC BY 4.0)
- IPR Praha (městské části, katastrální území, noise map, parks, CC BY 4.0)
- ČÚZK RÚIAN (CC BY 4.0)
- MŠMT (school register, CC BY 4.0)
- MPSV (dětské skupiny)
- ÚZIS ČR, NRPZS (CC BY 4.0)
- ČHMÚ (air quality)
- Policie ČR (crime map, **non-commercial**)
- ČSÚ (population)
- MF ČR (rent price map)

## 7. Known limitations and findings

1. **Praha noise is road traffic only.** IPR publishes no tram or rail layer. Kraków uses max(road, rail + tram) as Lden; Praha uses LAeq day. Both are normalised within the city.
2. **Pedestrian historic cores model as quiet.** Strategic noise maps model traffic, not people. Staroměstské náměstí lies in IPR's < 40 dB band, which is why the README check "Praha 1 low for quiet" **fails**: Praha 1 is 32nd of 57 by median noise. Kraków's Stare Miasto is 6th of 18. We report this rather than tune it away.
3. **Crime is not comparable across cities.** Kraków counts public-space offences in 2023; Praha counts all registered criminal offences over 12 months (Voronoi-anonymised). Both are shown at district level only, with neutral wording (README §4).
4. **Kraków accessibility is beta.** The ZTP GTFS carries no wheelchair or low-floor flags, so only benches and slope count, and accessibility coverage is 33%. Praha's is 97%.
5. **Kraków price:** 12% of habitable cells have fewer than 5 RCN sales within k ≤ 3 rings, so they are NaN and the engine imputes the median.
6. **Population proxy = address points.** Large blocks of flats count as one address each, so `population_est` under-weights dense estates. It is only used for district aggregation and crime denominators.
7. **Walk minutes are capped at 60.** Commute times above 120 min (or unreachable) are stored as 255.

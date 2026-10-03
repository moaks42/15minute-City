# Workstream A — data pipeline notes (Kraków + Praha)

Branch `a-data`. Pipeline lives in `pipeline/` (own uv project, Python 3.12, Java 21 for r5py).
Run: `cd pipeline && make data CITY=krakow|praha|all` (steps: fetch → build → travel → ml → validate).

## Status log

### 2026-10-03 16:20 (≈H1)
**Done**
- Every §4 source hit with a real request; responses in `data/raw/{city}/` (gitignored), manifest entries in
  `data/processed/{city}/manifest.json`.
- Both OSM PBFs, ZTP GTFS A+T, PID GTFS downloaded. Routing/service date **Tue 2026-10-06** (inside all feeds;
  PID only covers 2026-10-03…10-16).
- Kraków core build (49 s): 3 217 res-9 cells, 2 162 habitable (≥3 EMUiA addresses), 18 dzielnic,
  neighbourhoods = nearest OSM `place=suburb|quarter|neighbourhood`; 45 indicator columns.

**Next**: Kraków adapters (MEN schools, noise, GIOŚ, safety, RCN, NFZ maternity) → Praha core → r5py matrices.

## Decisions (A-local; B may copy into docs/DECISIONS.md)
- 16:00 MŠMT XML `rejstriky.msmt.cz/opendata/vrejcz010.xml` is **404** (site moved to isv.gov.cz). Using the
  MŠMT LKOD JSON-LD for Hl. m. Praha: `lkod-ftp.msmt.gov.cz/.../RSSZ-Hl-m-Praha.jsonld` (found via NKOD SPARQL).
- 16:00 Kraków RCN: using the city's own WFS `geodezja.eco.um.krakow.pl/cgi-bin/krakow-rcn` (layer `ms:lokale`,
  point per transaction with price + area) instead of the GUGiK national WFS.
- 16:00 Kraków safety: GMK ArcGIS layer "Przestępstwa w przestrzeni publicznej 2023" (141 polygons with counts)
  → aggregated to dzielnice. Otwarte Dane portal has no parks/żłobki datasets reachable → OSM for those.
- 16:00 Kraków noise: MSIP "Mapa imisyjna 2022" (road / rail+tram / industry, LDWN 5-dB bands).
- 16:00 Praha noise: IPR "Hluková mapa – den/noc" (5-dB bands, all sources combined) via the IPR ArcGIS hub.
- 16:00 Praha k.ú.: IPR org feature service `katastry` (112 polygons, KATUZE_KOD).
- 16:00 Police ČR: national monthly zips `kriminalita.policie.gov.cz/api/v2/downloads/{YYYYMM}.zip` + Voronoi
  geometry `voronoi.geojson.zip`; last 12 complete months. **Non-commercial licence** — flag in roadmap.
- 16:00 Walk network built directly from OSM highway geometry (shared vertices = nodes) + scipy multi-source
  Dijkstra; no osmnx/Overpass dependency (Overpass unreachable from this network).
- Walk minutes are **capped at 60** (60 = "none within 60 min"); counts use euclidean radii (800 m ≈ 10 min).
- ZTP GTFS has no wheelchair info (all 0) → `accessibility.wheelchair_*` NaN in Kraków (beta); benches from OSM.


## Requests to other workstreams
- none yet

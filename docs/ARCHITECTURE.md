# Architecture

```
            config/indicators.yaml  ·  config/cities/{krakow,praha}.yaml      (single source of truth)
                         │                          │
 open data + OSM ──▶ pipeline/ (A) ──▶ data/processed/{city}/ ──▶ engine/ (B, FastAPI) ──▶ web/ (C, React)
  ZTP · PID GTFS        city-agnostic core     grid.geojson            loads both cities         MapLibre + OpenFreeMap
  MSIP · IPR · RÚIAN    + city adapters        features.parquet        normalizes per request    i18n pl / cs / en
  GIOŚ · ČHMÚ · NRPZS                          pois / addresses        scores, explains, ranks   state in the URL
  MEN · MŠMT · RCN · MF                        travel_times.npz        ML: archetypes, twins
                                               manifest.json           live: GIOŚ, ČHMÚ (cached)
                                                     ▲
                       contracts/DATA_CONTRACT.md ───┘   contracts/openapi.yaml + types.ts + fixtures ───▶ web
```

**Contracts are the integration points.**
- `DATA_CONTRACT.md` (A → B) is checked by `contracts/tools/validate_data.py`. The engine runs the same validator at startup and refuses data with errors.
- `openapi.yaml` (B → C) *is* the engine's `/openapi.json`, and every response is tested against it.
- `fixtures/` let C work without a running engine (`VITE_USE_FIXTURES=1`).

## Engine (`engine/app/`)

| module | role |
|---|---|
| `config.py` | settings from env; yaml → `IndicatorSpec` per city (applies `indicatorOverrides`) |
| `data.py` | loads `data/processed/{city}` into NumPy: raw `(cells × indicators)` matrix, imputation with the city median, coverage, normalized sub-score matrix **cached per walkFactor**, travel-time lookup, POIs, admin groups |
| `scoring.py` | `/score` core: effective indicator weights (yaml → persona → request), criterion scores as one matmul `S @ (G·v)`, commute from anchors, match % `Σ W(level)·S_c / Σ W`, hard-filter masks, relax hint, ranking, district/neighbourhood aggregation (population-weighted mean of all habitable cells), `rankBy` ordering (map lens), explanations, place detail |
| `explain.py` | pl/cs/en/ko number formatting (nbsp grouping, decimal comma) and templates; values are always raw |
| `ml.py` | pooled archetypes (KMeans → MLP), similar places, twins (see `docs/ML.md`) |
| `geocode.py` | accent-insensitive local index (districts, places, POIs, addresses) + Photon fallback |
| `live.py` | live air (GIOŚ with a 2 req/min limiter; ČHMÚ CSV), 10-min cache, stale fallback |
| `prefs.py` | P2 Bradley–Terry preference learning |
| `export.py` | static fallback `engine/export/criteria_scores_{city}.json` |
| `devdata.py` | synthetic data in the exact contract layout (until A's data lands) |
| `main.py` | FastAPI routes, CORS, gzip, contract error schema |

**Request path for `/score`:** pydantic request → `compute()` (≈ 3 ms for Praha's 4.9k cells) → top-N explanations → compact `cells: [[h3, score, passes]]` → `JSONResponse` (no response-model re-validation; the tests validate against the contract instead). Measured p95 ≈ 3–5 ms server-side, against a target of < 150 ms.

**No `if city ==` anywhere.** Price field, filter field, budget field, live-air provider, wording overrides, admin levels and the routing resolution all come from `config/cities/*.yaml`.

## Running

```bash
cd engine && uv sync && uv run uvicorn app.main:app --reload          # http://localhost:8000/docs
uv run pytest -q                                                       # contract + scoring + export tests
docker compose up --build                                              # engine + web
```

| env | default | meaning |
|---|---|---|
| `DATA_DIR` | `../data/processed` | A's output |
| `DATA_FALLBACK` | `synthetic` | missing/invalid real data → synthetic dev data (`none` = fail hard) |
| `MODELS_DIR` | `engine/models` | archetype model + metrics |
| `CORS_ORIGINS` | `*` | comma-separated |
| `GOLEMIO_API_KEY` | – | optional; features without a key disable themselves |
| `KOMPAS_OFFLINE` | `0` | `1` = no outbound HTTP (tests) |

## Adding a city

1. Add `config/cities/<id>.yaml` (same shape as `krakow.yaml`: centre, bbox, CRS, GTFS, price field/unit, admin levels, live provider, wording overrides).
2. A: run the city-agnostic core (OSM + GTFS), then add adapters in `pipeline/adapters/<id>/` that write the same `<criterion>.<indicator>` columns (missing → NaN).
3. The engine needs no code changes: it loads every city in `config/cities/`. Add the id to the `CityId` enum in `openapi.yaml` (an additive contract change).

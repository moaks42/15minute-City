# Workstream B: notes (engine + ML + API, integrator)

## Status
- **contracts-v1** is on main: `config/indicators.yaml`, `config/cities/{krakow,praha}.yaml`, `contracts/openapi.yaml`, `contracts/types.ts`, `contracts/DATA_CONTRACT.md`, `contracts/fixtures/**`, `contracts/tools/*`.
- The engine on branch `b-engine` implements every §7.2 endpoint (departures = P2 stub) and serves `contracts/openapi.yaml` as `/openapi.json`. 45 tests are green (contract, monotonicity, filters, relax hint, determinism, explanations = raw values, partial data, export, latency).
- Until A's data is in `data/processed/`, it runs on **synthetic** data (`/api/health` → `dataSource: synthetic`, status `degraded`).
- Perf: `/score` Praha (4.9k cells) compute p95 ≈ 3–5 ms single-threaded; load test 300 req at concurrency 16 on 2 workers → 0 errors, ~140 req/s, server p95 < 100 ms.
- Engine URL: _not deployed yet (postponed, before M2)._ The Render API needs a card (402) and HF Docker Spaces need PRO (402). `render.yaml` and `engine/scripts/deploy_hf.py` are ready.
- Local Docker could not be verified (colima VM on this machine fails SSH provisioning). The build steps were replicated without Docker (`--no-dev` env, warm-up, uvicorn): OK, ready in 0.4 s.

## Contract changes (after v1: additive only, tagged contracts-vN)
| tag | change |
|---|---|
| contracts-v1 | initial |
| contracts-v2 | `DATA_CONTRACT.md` §3b: **optional** `data/processed/{city}/addresses.parquet` (street, housenumber, postcode, lat, lon, h3_9, source) for the local geocoder; `validate_data.py` checks it when present. Nothing changes for C. |

## For A (data)
- Build exactly what `contracts/DATA_CONTRACT.md` describes. Column names come from `config/indicators.yaml` (`<criterion>.<indicator>`).
- Before each push: `uv run contracts/tools/validate_data.py --city all`. The engine runs the same check at startup and refuses data with errors.
- Missing data → **NaN column** (never zeros, never a missing column). Walk minutes are capped at 60.
- Praha also needs the aux column `poi.metro_station_walk_min` (for the must-have filter).
- A complete example dataset in the right layout (from M1, once `b-engine` is merged): `cd engine && uv run python -m app.devdata` → `engine/.devdata/{city}/` (synthetic values).

## For C (web)
- **Run the engine locally:** `cd engine && uv sync && uv run uvicorn app.main:app --port 8000` → http://localhost:8000/docs (CORS `*`). Synthetic data is generated on first start.
- Types: `contracts/types.ts` (generated: `./contracts/tools/gen-types.sh`). Use the aliases at the bottom (`ScoreRequest`, `ScoreResponse`, `Place`…).
- Fixtures: `contracts/fixtures/` → `cities.json`, `health.json`, `twins.json` (K→P), `twins_praha_krakow.json`, and per city: `meta`, `score_student`, `score_parent`, `score_districts` (aggregate=district), `score_nomatch` (relax hint), `place`, `commute`, `similar`, `districts`, `geocode`, `live_air`, `grid.sample.geojson` (217 cells, numeric feature `id`).
- Labels in `/meta` are `{pl, cs, en}` objects. Explanation, relax-hint and budget sentences arrive as strings in the requested `lang`.
- Archetypes come as ids (`historic_core`, `urban_mix`, `student_buzz`, `estate_blocks`, `green_residential`, `family_suburb`, `quiet_outskirts`, `industrial_edge`). Please add `archetype.<id>` names in pl/cs/en.
- Air-quality level labels (0–5) are in `config/indicators.yaml → texts.airLevel` if you want to reuse them.
- Grid geometry: `GET /api/{city}/grid` (real data) or `grid.sample.geojson` (fixtures). Colour it via `feature-state` keyed by feature `id` (row index), or use `promoteId: "h3"`.
- `docker-compose.yml` expects `web/Dockerfile` serving the built app on port 80, with build arg `VITE_API_URL`.
- `place` takes `state` = base64url(JSON of the ScoreRequest).

## Log
- 10-03: contracts v1 written; fixtures generated and validated (26 files, 0 schema errors); data validator tested on synthetic data (positive + negative).
- 10-03: contracts v2 (optional addresses.parquet). Engine on b-engine: all endpoints, ML (k=6, MLP holdout 0.95 on synthetic), live air verified against GIOŚ + ČHMÚ, Photon fallback, static export, CI workflow, load test script (`engine/scripts/loadtest.py`).

# Workstream B: notes (engine + ML + API, integrator)

## Status (10-03 ~18:20, after the integration merge)
- **main = a-data + b-engine + c-web**. The engine runs on **A's real data** for both cities (validator: 0 errors). 47 engine tests are green on real and on synthetic data. `/score` p95 ≈ 3.4 ms (Praha, 4,976 cells).
- **Hosting:** none (team decision). Everything runs locally; see README → "Run locally". Engine at `http://localhost:8000`, web at `http://localhost:5173`. `render.yaml` / `engine/scripts/deploy_hf.py` stay as options (Render needs a card, HF Docker needs PRO).
- Static fallback export from real data: `engine/export/criteria_scores_{krakow,praha}.json` (`npm run sync-data` copies them to `web/public/data/{city}/criteria_scores.json`).
- ML on real data: k = 8, holdout 0.943, 5 archetypes in use (see `docs/ML.md`).

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

## Resolved requests
- C1 (top-N diversity): `top` now lists at most one cell per neighbourhood.
- C2 (criteria_scores export): done from real data; the file names match `sync-data.mjs`.
- C3 (engine URL + CORS): local `http://localhost:8000`, CORS `*`.
- A (no2, optional): not added yet. It would be an additive indicator (`environment.no2`, crossCity false) if time allows.

## For A: data issue
- Praha `environment.noise_db`: 13 cells at 0 dB or up to 176 dB (Lipence, Ruzyně, Újezd nad Lesy). The engine now treats values outside 20–120 dB as missing, but please fix them at the source.

## For C: after merging main
- `contracts/fixtures` were regenerated (`noise_db`/`pm25`/`pm10` → `crossCity: false`; same shapes). Run `npm run sync-data` and commit the refreshed `web/public/data/fixtures`.
- Archetype ids actually emitted on real data: `urban_mix`, `estate_blocks`, `family_suburb`, `green_residential`, `quiet_outskirts`.

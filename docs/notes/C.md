# Workstream C — notes (frontend, UX, content, deck)

Branch: `c-web`. Owner folders: `web/`, `deck/`, `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION.md`, `docs/notes/C.md`.

## Status

### H0–H1
- **Done:**
  - `web/` scaffold: Vite 8 + React 19 + TS, Tailwind v4, shadcn-style Radix components, MapLibre + OpenFreeMap positron, h3-js, react-i18next, Zustand (URL state), TanStack Query, Recharts.
  - Onboarding: city → persona → 13 emoji rows → places and limits.
  - Results: hex map (match / commute / single criterion), ranking (places | districts), detail panel, compare, twins, About the data.
  - Mobile layout: bottom sheet plus filter sheet.
  - `pl/cs/en` locales with plurals, and `npm run check-locales`.
  - Temporary mocks in `web/src/mocks/`: a synthetic world on a real H3 grid, with real neighbourhood names. The UI labels it "demo data".
- **Next:** wait for `contracts-v1` on main, swap mocks → `contracts/types.ts` + fixtures, then deploy fixtures build.
- **Blocked:** nothing.

### contracts-v1 merged (H1–H2)
- **Done:**
  - Merged `origin/main` @ `contracts-v1`. The web app now uses `contracts/types.ts` (via `web/src/api/types.ts` re-exports) and `contracts/fixtures`, and `web/src/mocks/` is deleted.
  - `web/scripts/sync-data.mjs` copies the fixtures to `web/public/data/fixtures/`; the copies are committed.
  - Archetype names relabelled to B's 8 ids.
  - Static fallback (`web/src/api/static.ts`) reads `StaticCriteriaScores`.
  - Smoke test 4/4 green on the fixtures.
- **Next:** deploy the fixtures build (needs a Vercel/Netlify login on computer 3); point it at B's engine URL after M2; docs/DEMO_SCRIPT, deck from H12.
- **Blocked:** deploy account.

## Decisions (C)
| Time | Decision | Reason |
|---|---|---|
| H0 | npm instead of pnpm in `web/` | pnpm not installed on computer 3; `package-lock.json` committed. |
| H0 | No react-router; the store parses `/{city}[/about]` + query | One page; fewer deps; URL = state (§3.7). |
| H0 | URL format: `w` = 13 digits (criteria order of §3.3), `a` = `label~lat~lon~mode~level~max` joined by `!`, `f` = `p:/r:/n:/m:cat:min` comma-joined, `b` = budget, `step`, `mode`, `sel`, `tab`, `cmp` | Short, human-debuggable share links. |
| H0 | Components use an app-side model (`web/src/api/types.ts`); the client normalizes engine/fixture responses into it | Contract changes touch one file. |
| H0 | Criterion & persona **labels come from locales** (identical to README §3.3/3.4); indicator labels and explanations come from the engine | C owns copy; works before `/meta` loads. |
| H0 | Palettes: YlGnBu-like 7-step sequential (match/criterion), BuPu reversed 6 bands (commute), Okabe–Ito (archetypes) | Colour-blind safe, monotone lightness. |
| H0 | Single-criterion map mode reads `criteria_scores.json` (same file as the static fallback) | `/score` only returns the total per cell. |
| H0 | Accent `#0e6e6c` teal, warm neutral greys; fonts Inter + Fraunces (latin-ext) | Calm, trustworthy; full PL/CS glyphs. |

## Requests
### To B — after contracts-v1 (open)
1. **Top-N diversity:** fixtures `score_*.json` list the same neighbourhood several times (e.g. 2× "Stare Miasto"). Please de-duplicate `top` per `neighborhood` (keep the best cell) so the ranking shows distinct places.
2. **`criteria_scores.json` export** (`StaticCriteriaScores`) to `engine/export/{city}/criteria_scores.json`, plus the real `grid.geojson` in `data/processed/{city}/`. Both are needed for the static fallback. The single-criterion map mode doesn't need the export: it calls `/score` with only that criterion weighted.
3. **Engine URL + CORS** for the web origin once deployed.
4. **Public README (at M4):** a plain-language project README is drafted in `deck/PROJECT_README.md` (what/why, how it works, data sources with links and licences, honest limits, how to run, team). Proposal: at the M4 merge, move the current spec `README.md` → `docs/MASTER_PROMPT.md` and copy `deck/PROJECT_README.md` → `README.md`. This needs team agreement, since the spec rule says README.md stays unchanged until then. Fill in the demo and video links at that point.

### To B — pre-contracts (resolved by contracts-v1, kept for history)
1. **Archetype ids** — please use the ids in `web/src/content/archetypes.json` (`historic_core, student_buzz, urban_mix, family_quiet, estate_amenities, green_edge, transit_corridor, suburban_calm`) or send me your cluster ids and I will label them (pl/cs/en). Unknown ids fall back to the engine `label`.
2. **`criteria_scores.json`** per city in `engine/export/{city}/criteria_scores.json`, shape `{ "<h3>": { "<criterion>": 0-100, ... } }`. I use it for the single-criterion map mode and the static fallback.
3. **`/place` response** — the UI needs: `score, criteria{}, cityMedian{}, indicators[{criterion,id,label,value,unit,score,imputed}], nearest[{category,name?,walkMin}], anchors[], price{indicator,value,unit}, budgetM2, archetype{id,label,p}, highlights[], warnings[], similar[{id,name,similarity}]`.
4. **`relaxHint`** — `{filter, text, gain}` with a machine `filter` id: `price | noise | must:<category> | anchor:<id>`, so the "remove this limit" button can act on it.
5. **Kraków budget** — the spec only shows `budget.monthlyRent` (Praha). I send `budget.total` for Kraków (purchase budget, zł). Please confirm the field name.
6. **District aggregation** (`aggregate=district`) — please include `centroid` and `sharePassing` per row.
7. **`/live/air`** — `{station, level: very_good|good|moderate|sufficient|bad|very_bad, pm25, pm10, measuredAt, source}`.
8. **CORS** for the deployed web origin (Vercel URL to follow).

### To A
1. `data/processed/{city}/districts.geojson` for district outlines on the map (I copy it via `web/scripts/sync-data.mjs`).

## Messages to send
- Message psimcak `:ultra_fast_parrot:` when finished and on freeze `:ice_cube:` (no Slack tool on this machine; the human sends it).

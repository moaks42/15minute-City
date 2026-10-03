# contracts/

Shared contracts between A (data), B (engine) and C (web). Owner: B. After `contracts-v1`, changes are additive only (see `docs/notes/B.md`).

| file | what |
|---|---|
| `openapi.yaml` | Engine API (OpenAPI 3.1). Source of truth for every response shape. |
| `types.ts` | TypeScript types generated from `openapi.yaml`, with friendly aliases at the bottom |
| `DATA_CONTRACT.md` | Exact schema of `data/processed/{city}/*` (A → B) |
| `fixtures/` | Real H3 res-9 cells around each centre with **fake** values, valid against `openapi.yaml` |
| `tools/make_fixtures.py` | Regenerates `fixtures/` from `config/*.yaml` |
| `tools/validate_fixtures.py` | Validates `fixtures/` against `openapi.yaml` |
| `tools/validate_data.py` | Validates `data/processed/{city}/` against `DATA_CONTRACT.md` (also used by the engine at startup) |
| `tools/gen-types.sh` | Regenerates `types.ts` |

```bash
uv run contracts/tools/make_fixtures.py
uv run contracts/tools/validate_fixtures.py
uv run contracts/tools/validate_data.py --city all
./contracts/tools/gen-types.sh
```

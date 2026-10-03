#!/usr/bin/env bash
# Regenerate contracts/types.ts from contracts/openapi.yaml. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/../.."
npx -y openapi-typescript@7 contracts/openapi.yaml -o contracts/types.ts
{
  echo
  echo "// ───── Friendly aliases (appended by contracts/tools/gen-types.sh) ─────"
  echo 'type S = components["schemas"];'
  for name in $(awk '/^  schemas:$/{on=1;next} on' contracts/openapi.yaml | grep -E '^    [A-Z][A-Za-z0-9]+:' | sed -E 's/^ +([A-Za-z0-9]+):.*$/\1/' | sort -u); do
    echo "export type ${name} = S[\"${name}\"];"
  done
} >> contracts/types.ts
echo "wrote contracts/types.ts"

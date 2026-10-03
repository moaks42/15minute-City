#!/usr/bin/env node
// Copies shared artefacts into web/public/data so the static deploy works
// without the engine (README §11 C, step 3):
//   contracts/fixtures/**              → public/data/fixtures/**
//   data/processed/{city}/grid.geojson → public/data/{city}/grid.geojson (+ districts/neighborhoods)
//   engine/export/**.json              → public/data/{city}/<name>.json
// Missing sources are reported, not fatal. Run: npm run sync-data
import { cpSync, existsSync, mkdirSync, readdirSync, statSync, copyFileSync } from 'node:fs'
import { dirname, join, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const web = join(dirname(fileURLToPath(import.meta.url)), '..')
const root = join(web, '..')
const out = join(web, 'public/data')
const CITIES = ['krakow', 'praha']
const log = (ok, msg) => console.log(`${ok ? '✓' : '·'} ${msg}`)
const rel = (p) => p.replace(root + '/', '')

function copy(src, dst) {
  if (!existsSync(src)) return log(false, `missing ${rel(src)}`)
  mkdirSync(dirname(dst), { recursive: true })
  if (statSync(src).isDirectory()) cpSync(src, dst, { recursive: true })
  else copyFileSync(src, dst)
  log(true, `${rel(src)} → ${rel(dst)}`)
}

// 1. Contract fixtures (incl. cities.json, twins.json).
copy(join(root, 'contracts/fixtures'), join(out, 'fixtures'))

// 2. Pipeline geometry per city.
for (const city of CITIES) {
  for (const f of ['grid.geojson', 'districts.geojson', 'neighborhoods.geojson', 'manifest.json']) {
    copy(join(root, 'data/processed', city, f), join(out, city, f))
  }
}

// 3. Engine exports (static fallback): per-city subfolders or <name>_<city>.json / <city>_<name>.json.
const exp = join(root, 'engine/export')
if (existsSync(exp)) {
  for (const entry of readdirSync(exp)) {
    const p = join(exp, entry)
    if (statSync(p).isDirectory() && CITIES.includes(entry)) {
      copy(p, join(out, entry))
      continue
    }
    if (!entry.endsWith('.json')) continue
    const city = CITIES.find((c) => entry.includes(c))
    if (!city) {
      copy(p, join(out, entry))
      continue
    }
    const name = basename(entry, '.json').replace(new RegExp(`[_.-]?${city}[_.-]?`), '') || 'export'
    copy(p, join(out, city, `${name}.json`))
  }
} else log(false, 'missing engine/export')

// TEMPORARY mock of the engine endpoints, built on the mock world.
import { greatCircleDistance, latLngToCell } from 'h3-js'
import type {
  CityId,
  CommuteResponse,
  CriterionId,
  Explanation,
  Lang,
  Mode,
  Place,
  ScoreRequest,
  ScoreResponse,
  TopItem,
  TwinsResponse,
} from '@/api/types'
import { CRITERIA } from '@/api/types'
import { getWorld, type MockCell } from './world'

const LEVEL_W = [0, 1, 2, 3, 5, 8]
const SPEED: Record<Mode, (km: number) => number> = {
  transit: (k) => 6 + k * 3.1,
  bike: (k) => 2 + k * 4,
  walk: (k) => k * 13,
}
const decay = (t: number, good: number, bad: number) => (t <= good ? 100 : t >= bad ? 0 : (100 * (bad - t)) / (bad - good))

const T: Record<Lang, Record<string, string>> = {
  pl: { stop: 'Przystanek {v} min pieszo, {d} odjazdów/h', noise: 'Hałas ok. {v} dB', park: 'Park {v} min pieszo', school: 'Szkoła {v} min pieszo', shop: 'Supermarket {v} min pieszo', gp: 'Przychodnia {v} min pieszo', pm: 'PM2,5 ok. {v} µg/m³', rail: 'Stacja {v} min pieszo', price: 'Mediana {v}' },
  cs: { stop: 'Zastávka {v} min pěšky, {d} odjezdů/h', noise: 'Hluk cca {v} dB', park: 'Park {v} min pěšky', school: 'Škola {v} min pěšky', shop: 'Supermarket {v} min pěšky', gp: 'Lékař {v} min pěšky', pm: 'PM2,5 cca {v} µg/m³', rail: 'Metro {v} min pěšky', price: 'Medián {v}' },
  en: { stop: 'Stop {v} min walk, {d} departures/h', noise: 'Noise ~{v} dB', park: 'Park {v} min walk', school: 'School {v} min walk', shop: 'Supermarket {v} min walk', gp: 'GP {v} min walk', pm: 'PM2.5 ~{v} µg/m³', rail: 'Station {v} min walk', price: 'Median {v}' },
}

function explain(c: MockCell, crit: CriterionId, lang: Lang, city: CityId): string | null {
  const t = T[lang]
  const r = c.raw
  const fill = (s: string, v: number | string, d?: number) => s.replace('{v}', String(v)).replace('{d}', String(d ?? ''))
  switch (crit) {
    case 'transit':
      return fill(t.stop, r.stopWalkMin, r.depPerHour)
    case 'environment':
      return r.noiseDb > 58 ? fill(t.noise, r.noiseDb) : fill(t.pm, r.pm25)
    case 'green':
      return fill(t.park, r.parkWalkMin)
    case 'education':
    case 'family':
      return fill(t.school, r.schoolWalkMin)
    case 'shops':
      return fill(t.shop, r.supermarketWalkMin)
    case 'health':
      return fill(t.gp, r.gpWalkMin)
    case 'accessibility':
      return fill(t.rail, r.railWalkMin)
    case 'price':
      return fill(t.price, city === 'krakow' ? `${r.pricePerM2} zł/m²` : `${r.pricePerM2} Kč/m²`)
    default:
      return null
  }
}

function anchorMinutes(c: MockCell, a: { lat: number; lon: number; mode: Mode }) {
  return Math.round(SPEED[a.mode](greatCircleDistance([c.lat, c.lon], [a.lat, a.lon], 'km')))
}

type Req = ScoreRequest & { city: CityId }

function scoreCell(c: MockCell, req: Req) {
  const crit = { ...c.criteria }
  if (req.anchors.length) {
    let num = 0
    let den = 0
    for (const a of req.anchors) {
      const w = LEVEL_W[a.level] || 1
      num += w * decay(anchorMinutes(c, a), 15, 60)
      den += w
    }
    crit.commute = Math.round(num / den)
  }
  let num = 0
  let den = 0
  for (const k of CRITERIA) {
    if (k === 'commute' && !req.anchors.length) continue
    const w = LEVEL_W[req.weights[k] ?? 0]
    num += w * crit[k]
    den += w
  }
  const score = den ? Math.round(num / den) : 0
  const f = req.filters
  const priceMax = req.city === 'krakow' ? f.maxPricePerM2 : f.maxRentPerM2
  const fails: string[] = []
  if (priceMax && c.raw.pricePerM2 > priceMax) fails.push('price')
  if (f.maxNoiseDb && c.raw.noiseDb > f.maxNoiseDb) fails.push('noise')
  for (const a of req.anchors) if (a.maxMinutes && anchorMinutes(c, a) > a.maxMinutes) fails.push(`anchor:${a.id}`)
  for (const m of f.mustHave) {
    const walk = m.category.includes('school') || m.category.includes('kinder') || m.category === 'nursery' ? c.raw.schoolWalkMin : m.category === 'park' ? c.raw.parkWalkMin : m.category.includes('station') || m.category === 'tram_stop' ? c.raw.stopWalkMin : c.raw.gpWalkMin
    if (walk > m.maxWalkMin) fails.push(`must:${m.category}`)
  }
  return { crit, score, fails }
}

function topItem(c: MockCell, s: ReturnType<typeof scoreCell>, rank: number, req: Req, medians: Record<CriterionId, number>): TopItem {
  const W = (k: CriterionId) => LEVEL_W[req.weights[k] ?? 0]
  const contrib = CRITERIA.filter((k) => W(k) > 0 && (k !== 'commute' || req.anchors.length)).map((k) => ({ k, v: W(k) * (s.crit[k] - medians[k]) }))
  contrib.sort((a, b) => b.v - a.v)
  const highlights: Explanation[] = []
  for (const { k } of contrib) {
    const text = explain(c, k, req.lang, req.city)
    if (text) highlights.push({ criterion: k, text })
    if (highlights.length === 2) break
  }
  const warnings: Explanation[] = []
  for (const { k } of [...contrib].reverse()) {
    const text = explain(c, k, req.lang, req.city)
    if (text && !highlights.some((h) => h.criterion === k)) {
      warnings.push({ criterion: k, text })
      break
    }
  }
  const crit: TopItem['criteria'] = {}
  for (const k of CRITERIA) if (W(k) > 0) crit[k] = s.crit[k]
  const budget = req.city === 'krakow' ? req.budget.total : req.budget.monthlyRent
  return {
    id: c.h3,
    kind: 'hex',
    rank,
    score: s.score,
    name: c.hood.name,
    district: { id: c.hood.district, name: c.hood.district },
    centroid: { lat: c.lat, lon: c.lon },
    criteria: crit,
    highlights,
    warnings,
    anchors: req.anchors.map((a) => ({ id: a.id, minutes: anchorMinutes(c, a), mode: a.mode })),
    price: { indicator: req.city === 'krakow' ? 'buy_per_m2' : 'rent_per_m2', value: c.raw.pricePerM2, unit: req.city === 'krakow' ? 'zł/m²' : 'Kč/m²/měs.' },
    budgetM2: budget ? Math.round(budget / c.raw.pricePerM2) : null,
    archetype: c.archetype,
    imputed: [],
  }
}

export function mockScore(req: Req): ScoreResponse {
  const t0 = performance.now()
  const world = getWorld(req.city)
  const scored = world.cells.map((c) => ({ c, s: scoreCell(c, req) }))
  const passing = scored.filter((x) => x.c.habitable && x.s.fails.length === 0)
  const ranked = [...passing].sort((a, b) => b.s.score - a.s.score)

  // One top cell per neighbourhood keeps the list diverse.
  let top: TopItem[] = []
  if (req.aggregate === 'district') {
    const groups = new Map<string, typeof scored>()
    for (const x of scored.filter((y) => y.c.habitable)) {
      const g = groups.get(x.c.hood.district) ?? []
      g.push(x)
      groups.set(x.c.hood.district, g)
    }
    const rows = [...groups.entries()].map(([d, g]) => {
      const pass = g.filter((x) => x.s.fails.length === 0).sort((a, b) => b.s.score - a.s.score)
      const half = pass.slice(0, Math.max(1, Math.ceil(pass.length / 2)))
      const score = pass.length ? Math.round(half.reduce((s, x) => s + x.s.score, 0) / half.length) : 0
      const best = pass[0] ?? g[0]
      return { d, score, best, share: pass.length / g.length }
    })
    rows.sort((a, b) => b.score - a.score)
    top = rows.slice(0, req.limit).map((r, i) => ({
      ...topItem(r.best.c, r.best.s, i + 1, req, world.medians),
      id: r.d,
      kind: 'district' as const,
      name: r.d,
      score: r.score,
      sharePassing: Math.round(r.share * 100) / 100,
    }))
  } else {
    const seen = new Set<string>()
    for (const x of ranked) {
      if (seen.has(x.c.hood.name)) continue
      seen.add(x.c.hood.name)
      top.push(topItem(x.c, x.s, top.length + 1, req, world.medians))
      if (top.length >= req.limit) break
    }
  }

  let relaxHint: ScoreResponse['relaxHint'] = null
  if (passing.length === 0) {
    const counts = new Map<string, number>()
    for (const x of scored) if (x.c.habitable && x.s.fails.length === 1) counts.set(x.s.fails[0], (counts.get(x.s.fails[0]) ?? 0) + 1)
    const best = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
    if (best) relaxHint = { filter: best[0], text: best[0], gain: best[1] }
  }

  return {
    city: req.city,
    currency: req.city === 'krakow' ? 'PLN' : 'CZK',
    computeMs: Math.round(performance.now() - t0),
    count: { cells: world.cells.length, habitable: world.cells.filter((c) => c.habitable).length, passing: passing.length },
    cells: scored.map((x) => [x.c.h3, x.s.score, x.c.habitable && x.s.fails.length === 0 ? 1 : 0]),
    top,
    relaxHint,
  }
}

export function mockPlace(city: CityId, h3: string, req: Req): Place {
  const world = getWorld(city)
  const c = world.byId.get(h3) ?? world.cells[0]
  const s = scoreCell(c, req)
  const t = topItem(c, s, 1, req, world.medians)
  const isK = city === 'krakow'
  const r = c.raw
  const lbl = (pl: string, cs: string, en: string) => ({ pl, cs, en })[req.lang]
  const similar = world.cells
    .filter((x) => x.habitable && x.hood.name !== c.hood.name && x.archetype.id === c.archetype.id)
    .map((x) => ({ x, d: CRITERIA.reduce((s2, k) => s2 + Math.abs(x.criteria[k] - c.criteria[k]), 0) }))
    .sort((a, b) => a.d - b.d)
  const seen = new Set<string>()
  const sim: Place['similar'] = []
  for (const { x, d } of similar) {
    if (seen.has(x.hood.name)) continue
    seen.add(x.hood.name)
    sim.push({ id: x.h3, name: x.hood.name, similarity: Math.max(0.5, 1 - d / 900) })
    if (sim.length >= 4) break
  }
  return {
    ...t,
    cityMedian: world.medians,
    criteria: s.crit,
    indicators: [
      { criterion: 'transit', id: 'stop_walk_min', label: lbl('Najbliższy przystanek', 'Nejbližší zastávka', 'Nearest stop'), value: r.stopWalkMin, unit: 'min', score: Math.round(decay(r.stopWalkMin, 3, 12)) },
      { criterion: 'transit', id: 'departures_per_hour', label: lbl('Odjazdy/h (7–9)', 'Odjezdy/h (7–9)', 'Departures/h (7–9)'), value: r.depPerHour, unit: '/h', score: c.criteria.transit },
      { criterion: 'transit', id: 'rail_station_walk_min', label: lbl('Stacja kolejowa', 'Metro / vlak', 'Rail / metro'), value: r.railWalkMin, unit: 'min', score: Math.round(decay(r.railWalkMin, 5, 20)) },
      { criterion: 'green', id: 'park_walk_min', label: lbl('Park ≥ 2 ha', 'Park ≥ 2 ha', 'Park ≥ 2 ha'), value: r.parkWalkMin, unit: 'min', score: Math.round(decay(r.parkWalkMin, 5, 20)) },
      { criterion: 'education', id: 'primary_school_walk_min', label: lbl('Szkoła podstawowa', 'Základní škola', 'Primary school'), value: r.schoolWalkMin, unit: 'min', score: Math.round(decay(r.schoolWalkMin, 5, 20)) },
      { criterion: 'shops', id: 'supermarket_walk_min', label: lbl('Supermarket', 'Supermarket', 'Supermarket'), value: r.supermarketWalkMin, unit: 'min', score: Math.round(decay(r.supermarketWalkMin, 4, 15)) },
      { criterion: 'health', id: 'gp_walk_min', label: lbl('Przychodnia POZ', 'Praktický lékař', 'GP clinic'), value: r.gpWalkMin, unit: 'min', score: Math.round(decay(r.gpWalkMin, 5, 20)) },
      { criterion: 'environment', id: 'noise_db', label: lbl('Hałas', 'Hluk', 'Noise'), value: r.noiseDb, unit: 'dB', score: Math.round(decay(r.noiseDb, 50, 70)) },
      { criterion: 'environment', id: 'pm25', label: lbl('PM2,5', 'PM2,5', 'PM2.5'), value: r.pm25, unit: 'µg/m³', score: Math.round(decay(r.pm25, 8, 30)) },
      { criterion: 'price', id: isK ? 'buy_per_m2' : 'rent_per_m2', label: lbl(isK ? 'Cena zł/m²' : 'Czynsz Kč/m²', isK ? 'Cena zł/m²' : 'Nájem Kč/m²', isK ? 'Price PLN/m²' : 'Rent CZK/m²'), value: r.pricePerM2, unit: isK ? 'zł/m²' : 'Kč/m²', score: c.criteria.price },
      { criterion: 'safety', id: 'crime_per_1000', label: lbl('Zdarzenia / 1000 mieszk.', 'Události / 1000 obyv.', 'Incidents / 1,000'), value: null, unit: '', score: null, imputed: true },
    ],
    nearest: [
      { category: 'tram_stop', walkMin: r.stopWalkMin },
      { category: 'supermarket', walkMin: r.supermarketWalkMin },
      { category: 'park', walkMin: r.parkWalkMin },
      { category: 'primary_school', walkMin: r.schoolWalkMin },
      { category: 'pharmacy', walkMin: Math.max(1, r.supermarketWalkMin + 1) },
      { category: 'gp_clinic', walkMin: r.gpWalkMin },
    ],
    similar: sim,
  }
}

export function mockCommute(city: CityId, lat: number, lon: number, mode: Mode): CommuteResponse {
  const world = getWorld(city)
  return {
    anchorCell: latLngToCell(lat, lon, 9),
    cells: world.cells.map((c) => [c.h3, Math.min(255, anchorMinutes(c, { lat, lon, mode }))]),
  }
}

export function mockTwins(from: CityId, h3: string, to: CityId, limit = 5): TwinsResponse {
  const src = getWorld(from).byId.get(h3) ?? getWorld(from).cells[0]
  const target = getWorld(to)
  const vec = (c: MockCell) => CRITERIA.filter((k) => k !== 'price' && k !== 'commute').map((k) => c.criteria[k])
  const a = vec(src)
  const na = Math.hypot(...a.map((x) => x - 50))
  const rows = target.cells
    .filter((c) => c.habitable)
    .map((c) => {
      const b = vec(c)
      const dot = a.reduce((s, x, i) => s + (x - 50) * (b[i] - 50), 0)
      return { c, sim: dot / (na * Math.hypot(...b.map((x) => x - 50)) || 1) }
    })
    .sort((x, y) => y.sim - x.sim)
  const seen = new Set<string>()
  const twins: TwinsResponse['twins'] = []
  for (const { c, sim } of rows) {
    if (seen.has(c.hood.name)) continue
    seen.add(c.hood.name)
    twins.push({ id: c.h3, name: c.hood.name, district: { id: c.hood.district, name: c.hood.district }, centroid: { lat: c.lat, lon: c.lon }, similarity: Math.max(0, Math.round(sim * 100) / 100), archetype: c.archetype })
    if (twins.length >= limit) break
  }
  return { from, to, source: { id: src.h3, name: src.hood.name }, twins }
}

export function mockGeocode(city: CityId, q: string) {
  const world = getWorld(city)
  const norm = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  const nq = norm(q)
  const seen = new Set<string>()
  const out: { label: string; lat: number; lon: number }[] = []
  for (const c of world.cells) {
    if (seen.has(c.hood.name)) continue
    if (norm(c.hood.name).includes(nq)) {
      seen.add(c.hood.name)
      out.push({ label: `${c.hood.name}, ${c.hood.district}`, lat: c.hood.lat, lon: c.hood.lon })
    }
  }
  return out.slice(0, 6)
}

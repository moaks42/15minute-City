// Static fallback (README §8, VITE_STATIC_FALLBACK=1): the engine is down, so
// match % is the weighted sum of B's precomputed criterion scores
// (public/data/{city}/criteria_scores.json, schema StaticCriteriaScores).
// Commute, hard filters, explanations, twins and live data are unavailable;
// the UI says so instead of inventing numbers.
import type { CityId, CriterionId, Place, RankedPlace, ScoreRequest, ScoreResponse, StaticCriteriaScores } from './types'

interface Row {
  h3: string
  habitable: boolean
  scores: (number | null)[]
}
interface Loaded {
  s: StaticCriteriaScores
  rows: Row[]
  byPersona: Record<string, (number | null)[][]>
  props: Map<string, { name: string; districtId: string; district: string; lat: number; lon: number; pop: number }>
}

const cache = new Map<CityId, Promise<Loaded>>()

function centroid(g: GeoJSON.Polygon): [number, number] {
  const ring = g.coordinates[0].slice(0, -1)
  return [ring.reduce((a, p) => a + p[1], 0) / ring.length, ring.reduce((a, p) => a + p[0], 0) / ring.length]
}

function load(city: CityId): Promise<Loaded> {
  let p = cache.get(city)
  if (!p) {
    p = Promise.all([
      fetch(`/data/${city}/criteria_scores.json`).then((r) => r.json() as Promise<StaticCriteriaScores>),
      fetch(`/data/${city}/grid.geojson`).then((r) => r.json() as Promise<GeoJSON.FeatureCollection<GeoJSON.Polygon>>),
    ]).then(([s, grid]) => {
      const props: Loaded['props'] = new Map()
      for (const f of grid.features) {
        const q = f.properties as Record<string, string>
        const [lat, lon] = centroid(f.geometry)
        props.set(q.h3, { name: q.neighborhood || q.district_name, districtId: String(q.district_id), district: q.district_name, lat, lon, pop: Number(q.population_est) || 0 })
      }
      const rows = s.cells.map((c) => ({ h3: String(c[0]), habitable: !!c[1], scores: c.slice(2) as (number | null)[] }))
      return { s, rows, byPersona: (s.byPersona ?? {}) as Loaded['byPersona'], props }
    })
    cache.set(city, p)
  }
  return p
}

function weighted(scores: (number | null)[], criteria: CriterionId[], req: ScoreRequest, levels: Record<string, number>) {
  let num = 0
  let den = 0
  let all = 0
  let n = 0
  criteria.forEach((c, i) => {
    const v = scores[i]
    if (v == null) return
    all += v
    n += 1
    const w = levels[String(req.weights[c] ?? 0)] ?? 0
    num += w * v
    den += w
  })
  // Like the engine: nothing rated with data here → equal weights, not 0 (which would colour it as the worst).
  if (!den) return n ? Math.round(all / n) : 0
  return Math.round(num / den)
}

export async function staticScore(city: CityId, req: ScoreRequest): Promise<ScoreResponse> {
  const t0 = performance.now()
  const { s, rows, byPersona, props } = await load(city)
  const criteria = s.criteria as CriterionId[]
  const personaRows = req.persona ? byPersona[req.persona] : undefined
  const scored = rows.map((r, i) => ({ r, scores: personaRows?.[i] ?? r.scores }))
  const cells: ScoreResponse['cells'] = scored.map(({ r, scores }) => [r.h3, weighted(scores, criteria, req, s.levels), r.habitable ? 1 : 0])
  // Like the engine: rankBy = a criterion orders `top` by it (anchors need the engine), and that criterion is always listed.
  const rankIdx = req.rankBy ? criteria.indexOf(req.rankBy as CriterionId) : -1
  const crit = (scores: (number | null)[]) =>
    Object.fromEntries(criteria.map((c, i) => [c, scores[i]]).filter(([c, v]) => v != null && ((req.weights[c as CriterionId] ?? 0) > 0 || c === req.rankBy))) as Record<string, number>
  const habitable = cells.map((c, i) => [c, i] as const).filter(([c]) => c[2] === 1)
  const top: RankedPlace[] = []

  if (req.aggregate === 'hex') {
    const key = (i: number) => (rankIdx >= 0 ? (scored[i].scores[rankIdx] ?? -1) : cells[i][1])
    const order = habitable.filter(([c]) => !req.district || props.get(c[0])?.districtId === req.district).sort((a, b) => key(b[1]) - key(a[1]) || b[0][1] - a[0][1])
    const seen = new Set<string>()
    for (const [c, i] of order) {
      const p = props.get(c[0])
      if (!p || seen.has(p.name)) continue // one cell per neighbourhood
      seen.add(p.name)
      top.push({
        id: c[0], kind: 'hex', rank: top.length + 1, score: c[1], name: p.name,
        district: { id: p.districtId, name: p.district }, centroid: { lat: p.lat, lon: p.lon },
        criteria: crit(scored[i].scores), highlights: [], warnings: [], anchors: [], imputed: [], passes: true,
      })
      if (top.length >= req.limit) break
    }
  } else {
    // A district is the population-weighted mean of all its habitable cells.
    const groups = new Map<string, number[]>()
    for (const [c, i] of habitable) {
      const d = props.get(c[0])?.districtId
      if (d) groups.set(d, [...(groups.get(d) ?? []), i])
    }
    const mean = (idx: number[], v: (i: number) => number | null) => {
      let num = 0
      let den = 0
      for (const i of idx) {
        const x = v(i)
        if (x == null) continue
        const w = (props.get(rows[i].h3)?.pop ?? 0) + 1
        num += w * x
        den += w
      }
      return den ? num / den : null
    }
    const ranked = [...groups].map(([id, idx]) => {
      const score = mean(idx, (i) => cells[i][1]) ?? 0
      const means = criteria.map((_, k) => mean(idx, (i) => scored[i].scores[k]))
      return { id, idx, score, means, key: rankIdx >= 0 ? (means[rankIdx] ?? -1) : score }
    })
    ranked.sort((a, b) => b.key - a.key || b.score - a.score || a.id.localeCompare(b.id))
    for (const g of ranked.slice(0, req.limit)) {
      const ps = g.idx.map((i) => props.get(rows[i].h3)!)
      const lat = ps.reduce((a, p) => a + p.lat, 0) / ps.length
      const lon = ps.reduce((a, p) => a + p.lon, 0) / ps.length
      top.push({
        id: g.id, kind: 'district', rank: top.length + 1, score: Math.round(g.score), name: ps[0].district, district: null,
        centroid: { lat, lon }, criteria: crit(g.means.map((v) => (v == null ? null : Math.round(v)))),
        highlights: [], warnings: [], anchors: [], imputed: [], passes: true,
        sharePassing: 1, cellCount: g.idx.length, populationEst: ps.reduce((a, p) => a + p.pop, 0),
      })
    }
  }

  return {
    city,
    currency: city === 'krakow' ? 'PLN' : 'CZK',
    lang: req.lang ?? 'pl',
    computeMs: Math.round(performance.now() - t0),
    aggregate: req.aggregate,
    count: { cells: rows.length, habitable: habitable.length, passing: habitable.length },
    cells: req.includeCells === false ? [] : cells,
    top,
    relaxHint: null,
    excludedCriteria: ['commute'],
    weightsUsed: req.weights,
    cityMedian: s.cityMedian ?? {},
  }
}

export async function staticPlace(city: CityId, h3: string, req: ScoreRequest): Promise<Place> {
  const { s, rows, byPersona, props } = await load(city)
  const i = rows.findIndex((r) => r.h3 === h3)
  const row = rows[i]
  const scores = (req.persona && byPersona[req.persona]?.[i]) || row?.scores || []
  const criteria = s.criteria as CriterionId[]
  const p = props.get(h3)
  return {
    id: h3,
    kind: 'hex',
    city,
    centroid: { lat: p?.lat ?? 0, lon: p?.lon ?? 0 },
    name: p?.name ?? h3,
    district: p ? { id: p.districtId, name: p.district } : null,
    habitable: !!row?.habitable,
    score: weighted(scores, criteria, req, s.levels),
    criteria: Object.fromEntries(criteria.map((c, k) => [c, scores[k]]).filter(([, v]) => v != null)) as Record<string, number>,
    cityMedian: s.cityMedian ?? {},
    indicators: [],
    nearest: [],
    anchors: [],
  }
}

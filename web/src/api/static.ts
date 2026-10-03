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
  props: Map<string, { name: string; districtId: string; district: string; lat: number; lon: number }>
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
        props.set(q.h3, { name: q.neighborhood || q.district_name, districtId: String(q.district_id), district: q.district_name, lat, lon })
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
  criteria.forEach((c, i) => {
    const v = scores[i]
    const w = levels[String(req.weights[c] ?? 0)] ?? 0
    if (v == null || !w) return
    num += w * v
    den += w
  })
  return den ? Math.round(num / den) : 0
}

export async function staticScore(city: CityId, req: ScoreRequest): Promise<ScoreResponse> {
  const t0 = performance.now()
  const { s, rows, byPersona, props } = await load(city)
  const criteria = s.criteria as CriterionId[]
  const personaRows = req.persona ? byPersona[req.persona] : undefined
  const scored = rows.map((r, i) => ({ r, scores: personaRows?.[i] ?? r.scores }))
  const cells: ScoreResponse['cells'] = scored.map(({ r, scores }) => [r.h3, weighted(scores, criteria, req, s.levels), r.habitable ? 1 : 0])
  const crit = (scores: (number | null)[]) => Object.fromEntries(criteria.map((c, i) => [c, scores[i]]).filter(([c, v]) => v != null && (req.weights[c as CriterionId] ?? 0) > 0)) as Record<string, number>

  const order = cells.map((c, i) => [c, i] as const).filter(([c]) => c[2] === 1).sort((a, b) => b[0][1] - a[0][1])
  const top: RankedPlace[] = []
  const groupKey = (h3: string) => (req.aggregate === 'hex' ? props.get(h3)?.name : props.get(h3)?.districtId) ?? h3
  const seen = new Set<string>()
  for (const [c, i] of order) {
    const p = props.get(c[0])
    const key = groupKey(c[0])
    if (!p || seen.has(key)) continue
    seen.add(key)
    top.push({
      id: req.aggregate === 'hex' ? c[0] : p.districtId,
      kind: req.aggregate === 'hex' ? 'hex' : 'district',
      rank: top.length + 1,
      score: c[1],
      name: req.aggregate === 'hex' ? p.name : p.district,
      district: { id: p.districtId, name: p.district },
      centroid: { lat: p.lat, lon: p.lon },
      criteria: crit(scored[i].scores),
      highlights: [],
      warnings: [],
      anchors: [],
      imputed: [],
      passes: true,
    })
    if (top.length >= req.limit) break
  }

  return {
    city,
    currency: city === 'krakow' ? 'PLN' : 'CZK',
    lang: req.lang ?? 'pl',
    computeMs: Math.round(performance.now() - t0),
    aggregate: req.aggregate,
    count: { cells: rows.length, habitable: order.length, passing: order.length },
    cells,
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

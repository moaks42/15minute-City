// Single entry point for engine data (README §7.2, contracts/openapi.yaml).
// Modes (README §8): live engine · VITE_USE_FIXTURES=1 (contracts/fixtures,
// copied to /data/fixtures by scripts/sync-data.mjs) · VITE_STATIC_FALLBACK=1
// (scores computed in the browser from criteria_scores.json).
import type {
  City,
  CityId,
  CommuteResponse,
  GeocodeHit,
  GeocodeResponse,
  Lang,
  LiveAir,
  Meta,
  Mode,
  Place,
  RankedPlace,
  ScoreRequest,
  ScoreResponse,
  SimilarResponse,
  TwinsResponse,
} from './types'
import { API_URL, STATIC_FALLBACK, USE_FIXTURES } from '@/lib/env'
import { fold } from '@/lib/format'
import { staticPlace, staticScore } from './static'

const FX = '/data/fixtures'

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  return res.json() as Promise<T>
}
const get = <T>(path: string) => getJson<T>(`${API_URL}${path}`)
async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

/** base64url (no padding) of the JSON ScoreRequest, for /place?state=. */
export function encodeState(req: ScoreRequest): string {
  const bytes = new TextEncoder().encode(JSON.stringify(req))
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

// ---------- fixtures (static files; responses don't react to weights) ----------
/** Order and filter a fixture's `top` the way the engine does for rankBy / district. */
function fxRank(res: ScoreResponse, req: ScoreRequest): ScoreResponse {
  const rb = req.rankBy
  if (!rb && !req.district) return res
  const key = (p: RankedPlace) =>
    !rb ? p.score : rb.startsWith('anchor:') ? -(p.anchors.find((a) => `anchor:${a.id}` === rb)?.minutes ?? 999) : (p.criteria[rb] ?? -1)
  const top = res.top.filter((p) => !req.district || p.district?.id === req.district).sort((a, b) => key(b) - key(a) || b.score - a.score)
  return { ...res, top: top.map((p, i) => ({ ...p, rank: i + 1 })) }
}

const fx = {
  async score(city: CityId, req: ScoreRequest): Promise<ScoreResponse> {
    const f = req.filters
    const tight = !!(f?.maxPricePerM2 || f?.maxRentPerM2 || f?.maxNoiseDb || f?.mustHave?.length)
    const name =
      req.aggregate !== 'hex' ? 'score_districts' : tight && f?.mustHave?.length ? 'score_nomatch' : req.persona === 'parent' || req.persona === 'expecting' ? 'score_parent' : 'score_student'
    return fxRank(await getJson<ScoreResponse>(`${FX}/${city}/${name}.json`), req)
  },
  async geocode(city: CityId, q: string): Promise<GeocodeHit[]> {
    const r = await getJson<GeocodeResponse>(`${FX}/${city}/geocode.json`)
    const nq = fold(q)
    const hits = r.items.filter((i) => fold(`${i.label} ${i.sublabel ?? ''}`).includes(nq))
    return hits.length ? hits : r.items.slice(0, 5)
  },
  twins: (from: CityId): Promise<TwinsResponse> => getJson(`${FX}/${from === 'krakow' ? 'twins' : 'twins_praha_krakow'}.json`),
}

const OFFLINE = USE_FIXTURES || STATIC_FALLBACK

export const api = {
  cities: (): Promise<City[]> => (OFFLINE ? getJson(`${FX}/cities.json`) : get('/api/cities')),

  meta: (city: CityId, lang: Lang): Promise<Meta> => (OFFLINE ? getJson(`${FX}/${city}/meta.json`) : get(`/api/${city}/meta?lang=${lang}`)),

  grid: (city: CityId): Promise<GeoJSON.FeatureCollection> =>
    USE_FIXTURES ? getJson(`${FX}/${city}/grid.sample.geojson`) : STATIC_FALLBACK ? getJson(`/data/${city}/grid.geojson`) : get(`/api/${city}/grid`),

  districtShapes: (city: CityId): Promise<GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon>> => getJson(`/data/${city}/districts.geojson`),

  score: (city: CityId, req: ScoreRequest): Promise<ScoreResponse> =>
    STATIC_FALLBACK ? staticScore(city, req) : USE_FIXTURES ? fx.score(city, req) : post(`/api/${city}/score`, req),

  place: (city: CityId, h3: string, req: ScoreRequest): Promise<Place> =>
    STATIC_FALLBACK
      ? staticPlace(city, h3, req)
      : USE_FIXTURES
      ? getJson<Place>(`${FX}/${city}/place.json`).then((p) => ({ ...p, id: h3 }))
      : get(`/api/${city}/place/${h3}?lang=${req.lang}&state=${encodeState(req)}`),

  similar: (city: CityId, h3: string): Promise<SimilarResponse> =>
    OFFLINE ? getJson(`${FX}/${city}/similar.json`) : get(`/api/${city}/similar/${h3}?limit=5`),

  commute: (city: CityId, lat: number, lon: number, mode: Mode): Promise<CommuteResponse> =>
    OFFLINE ? getJson(`${FX}/${city}/commute.json`) : get(`/api/${city}/commute?lat=${lat}&lon=${lon}&mode=${mode}`),

  twins: (from: CityId, h3: string, to: CityId, lang: Lang, limit = 5): Promise<TwinsResponse> =>
    OFFLINE ? fx.twins(from) : get(`/api/twins?from=${from}&h3=${h3}&to=${to}&limit=${limit}&lang=${lang}`),

  geocode: (city: CityId, q: string): Promise<GeocodeHit[]> =>
    OFFLINE ? fx.geocode(city, q) : get<GeocodeResponse>(`/api/${city}/geocode?q=${encodeURIComponent(q)}`).then((r) => r.items),

  air: (city: CityId, lat: number, lon: number): Promise<LiveAir> =>
    OFFLINE ? getJson(`${FX}/${city}/live_air.json`) : get(`/api/${city}/live/air?lat=${lat}&lon=${lon}`),
}

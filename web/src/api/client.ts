// Single entry point for engine data. Switches between the live engine,
// fixtures and the static fallback via env flags (README §8).
import type {
  AirResponse,
  City,
  CityId,
  CommuteResponse,
  CriterionId,
  GeocodeHit,
  Lang,
  Meta,
  Mode,
  Place,
  ScoreRequest,
  ScoreResponse,
  TwinsResponse,
} from './types'
import { API_URL, USE_FIXTURES, STATIC_FALLBACK } from '@/lib/env'
import { MOCK_CITIES, mockMeta } from '@/mocks/meta'
import { mockCommute, mockGeocode, mockPlace, mockScore, mockTwins } from '@/mocks/engine'
import { getWorld } from '@/mocks/world'

const OFFLINE = USE_FIXTURES || STATIC_FALLBACK
const delay = <T,>(v: T, ms = 120) => new Promise<T>((r) => setTimeout(() => r(v), ms))

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  cities: (): Promise<City[]> => (OFFLINE ? delay(MOCK_CITIES, 0) : get('/api/cities')),

  meta: (city: CityId, lang: Lang): Promise<Meta> =>
    OFFLINE ? delay(mockMeta(city), 50) : get(`/api/${city}/meta?lang=${lang}`),

  score: (city: CityId, req: ScoreRequest): Promise<ScoreResponse> =>
    OFFLINE ? delay(mockScore({ ...req, city }), 80) : post(`/api/${city}/score`, req),

  place: (city: CityId, h3: string, req: ScoreRequest): Promise<Place> =>
    OFFLINE
      ? delay(mockPlace(city, h3, { ...req, city }))
      : get(`/api/${city}/place/${h3}?lang=${req.lang}&state=${encodeURIComponent(JSON.stringify(req))}`),

  commute: (city: CityId, lat: number, lon: number, mode: Mode): Promise<CommuteResponse> =>
    OFFLINE ? delay(mockCommute(city, lat, lon, mode)) : get(`/api/${city}/commute?lat=${lat}&lon=${lon}&mode=${mode}`),

  twins: (from: CityId, h3: string, to: CityId, lang: Lang, limit = 5): Promise<TwinsResponse> =>
    OFFLINE
      ? delay(mockTwins(from, h3, to, limit))
      : get(`/api/twins?from=${from}&h3=${h3}&to=${to}&limit=${limit}&lang=${lang}`),

  geocode: (city: CityId, q: string): Promise<GeocodeHit[]> =>
    OFFLINE ? delay(mockGeocode(city, q), 60) : get(`/api/${city}/geocode?q=${encodeURIComponent(q)}`),

  air: (city: CityId, lat: number, lon: number): Promise<AirResponse | null> =>
    OFFLINE ? delay(null, 0) : get(`/api/${city}/live/air?lat=${lat}&lon=${lon}`),

  /** Per-cell criterion scores (engine export criteria_scores.json): single-criterion map mode + static fallback. */
  criteriaScores: (city: CityId): Promise<Record<string, Partial<Record<CriterionId, number>>>> =>
    OFFLINE
      ? delay(Object.fromEntries(getWorld(city).cells.map((c) => [c.h3, c.criteria])), 0)
      : fetch(`/data/${city}/criteria_scores.json`).then((r) => r.json()),

  grid: (city: CityId): Promise<GeoJSON.FeatureCollection> =>
    OFFLINE ? delay(getWorld(city).grid as GeoJSON.FeatureCollection, 0) : fetch(`/data/${city}/grid.geojson`).then((r) => r.json()),
}

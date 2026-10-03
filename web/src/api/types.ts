// App-side model of the engine API (README §7.2).
// Until contracts/types.ts lands on main these are hand-written; the client
// normalizes whatever the engine/fixtures return into these shapes so the
// components never depend on wire details.

export type Lang = 'pl' | 'cs' | 'en'
export type CityId = 'krakow' | 'praha'
export type Mode = 'transit' | 'bike' | 'walk'
export type Localized = string | Partial<Record<Lang, string>>

export const CRITERIA = [
  'commute',
  'transit',
  'active',
  'green',
  'education',
  'family',
  'safety',
  'price',
  'shops',
  'health',
  'environment',
  'leisure',
  'accessibility',
] as const
export type CriterionId = (typeof CRITERIA)[number]
export type Weights = Record<CriterionId, number> // importance level 0–5

export interface City {
  id: CityId
  name: Localized
  defaultLang: Lang
  currency: 'PLN' | 'CZK'
  center: [number, number] // [lat, lon]
  zoom: number
  coverage?: Record<string, number>
}

export interface Indicator {
  id: string
  label: Localized
  unit?: string
  source?: string
  coverage?: number
}

export interface Criterion {
  id: CriterionId
  emoji: string
  label: Localized
  indicators: Indicator[]
  coverage: number // 0–1 in this city; 0 = hidden/beta
}

export interface Persona {
  id: string
  emoji: string
  label: Localized
  weights: Weights
  suggestedAnchors?: { label: Localized; mode: Mode }[]
}

export interface ManifestEntry {
  key: string
  url?: string
  fetchedAt?: string
  licence?: string
  rows?: number
  status: 'ok' | 'fallback' | 'missing'
  note?: string
}

export interface Meta {
  city: CityId
  levels: Record<string, number>
  levelEmoji: Record<string, string>
  criteria: Criterion[]
  personas: Persona[]
  mustHaveCategories: string[]
  price: { indicator: string; mode: 'buy' | 'rent'; unit: Localized }
  manifest: ManifestEntry[]
}

export interface Anchor {
  id: string
  label: string
  lat: number
  lon: number
  mode: Mode
  level: number
  maxMinutes?: number | null
}

export interface MustHave {
  category: string
  maxWalkMin: number
}

export interface Filters {
  maxPricePerM2?: number | null // Kraków (buy)
  maxRentPerM2?: number | null // Praha (rent)
  mustHave: MustHave[]
  maxNoiseDb?: number | null
}

export interface Budget {
  total?: number | null // Kraków: total purchase budget
  monthlyRent?: number | null // Praha
}

export interface ScoreRequest {
  v: 1
  lang: Lang
  persona: string
  weights: Weights
  anchors: Anchor[]
  filters: Filters
  budget: Budget
  aggregate: 'hex' | 'district'
  limit: number
}

export interface Explanation {
  criterion: CriterionId
  text: string
}

export interface Archetype {
  id: string
  label?: string
  p: number
}

export interface TopItem {
  id: string
  kind: 'hex' | 'district'
  rank: number
  score: number
  name: string
  district?: { id: string; name: string }
  centroid: { lat: number; lon: number }
  criteria: Partial<Record<CriterionId, number>>
  highlights: Explanation[]
  warnings: Explanation[]
  anchors: { id: string; minutes: number | null; mode: Mode }[]
  price?: { indicator: string; value: number | null; unit: string }
  budgetM2?: number | null
  archetype?: Archetype | null
  imputed: string[]
  sharePassing?: number
}

export interface ScoreResponse {
  city: CityId
  currency: string
  computeMs: number
  count: { cells: number; habitable: number; passing: number }
  cells: [string, number, 0 | 1][]
  top: TopItem[]
  relaxHint: { filter: string; text: string; gain?: number } | null
}

export interface PlaceIndicator {
  criterion: CriterionId
  id: string
  label: string
  value: number | null
  unit?: string
  score: number | null // 0–100 sub-score
  imputed?: boolean
}

export interface Place {
  id: string
  name: string
  district?: { id: string; name: string }
  centroid: { lat: number; lon: number }
  score: number
  criteria: Partial<Record<CriterionId, number>>
  cityMedian: Partial<Record<CriterionId, number>>
  indicators: PlaceIndicator[]
  nearest: { category: string; name?: string; walkMin: number }[]
  anchors: { id: string; minutes: number | null; mode: Mode }[]
  price?: { indicator: string; value: number | null; unit: string }
  budgetM2?: number | null
  archetype?: Archetype | null
  highlights: Explanation[]
  warnings: Explanation[]
  similar: { id: string; name: string; score?: number; similarity?: number }[]
}

export interface CommuteResponse {
  anchorCell: string
  cells: [string, number][]
}

export interface Twin {
  id: string
  name: string
  district?: { id: string; name: string }
  centroid: { lat: number; lon: number }
  similarity: number // 0–1
  archetype?: Archetype | null
}

export interface TwinsResponse {
  from: CityId
  to: CityId
  source: { id: string; name: string }
  twins: Twin[]
}

export interface AirResponse {
  station?: string
  index?: string | number | null
  level?: 'very_good' | 'good' | 'moderate' | 'sufficient' | 'bad' | 'very_bad' | null
  pm25?: number | null
  pm10?: number | null
  measuredAt?: string
  source?: string
}

export interface GeocodeHit {
  label: string
  lat: number
  lon: number
}

export interface GridFeatureProps {
  h3: string
  district_id?: string
  district_name?: string
  neighborhood?: string
  habitable?: boolean | number
  population_est?: number
}

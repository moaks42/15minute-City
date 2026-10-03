// All app state lives here and is mirrored to the URL (README §3.7):
// /{city}[/about]?v=1&lang=&p=&w=&a=&f=&b=&mode=&sel=&step=&cmp=
import { create } from 'zustand'
import type { Anchor, CityId, CriterionId, Filters, Lang, Mode, MustHave, Weights } from '@/api/types'
import { CRITERIA } from '@/api/types'

export type Step = 'persona' | 'criteria' | 'places' | 'results'
export type MapMode = 'match' | 'commute' | CriterionId
export type Tab = 'places' | 'districts'

export interface AppState {
  city: CityId | null
  view: 'app' | 'about'
  lang: Lang
  step: Step
  persona: string | null
  weights: Weights
  anchors: Anchor[]
  filters: Filters
  budget: number | null // Kraków: total zł · Praha: monthly rent Kč
  mapMode: MapMode
  commuteAnchor: string | null
  sel: string | null
  tab: Tab
  compare: string[]
  hover: string | null
}

export const CITY_IDS: CityId[] = ['krakow', 'praha']
export const CITY_LANG: Record<CityId, Lang> = { krakow: 'pl', praha: 'cs' }
const LANGS: Lang[] = ['pl', 'cs', 'en']

export const DEFAULT_WEIGHTS = Object.fromEntries(CRITERIA.map((c) => [c, 3])) as Weights
const EMPTY_FILTERS: Filters = { maxPricePerM2: null, maxRentPerM2: null, mustHave: [], maxNoiseDb: null }

export function browserLang(): Lang {
  for (const l of navigator.languages ?? [navigator.language]) {
    const s = l.slice(0, 2).toLowerCase()
    if ((LANGS as string[]).includes(s)) return s as Lang
    if (s === 'sk') return 'cs'
  }
  return 'pl'
}

// ---------- URL encoding ----------
const clean = (s: string) => s.replace(/[~!]/g, ' ').slice(0, 60)

export function encodeWeights(w: Weights) {
  return CRITERIA.map((c) => w[c] ?? 0).join('')
}
export function decodeWeights(s: string | null): Weights | null {
  if (!s || !/^[0-5]{13}$/.test(s)) return null
  return Object.fromEntries(CRITERIA.map((c, i) => [c, Number(s[i])])) as Weights
}
function encodeAnchors(a: Anchor[]) {
  return a.map((x) => [clean(x.label), x.lat.toFixed(5), x.lon.toFixed(5), x.mode[0], x.level, x.maxMinutes ?? ''].join('~')).join('!')
}
function decodeAnchors(s: string | null): Anchor[] {
  if (!s) return []
  const modes: Record<string, Mode> = { t: 'transit', b: 'bike', w: 'walk' }
  return s
    .split('!')
    .map((part, i) => {
      const [label, lat, lon, m, level, max] = part.split('~')
      return {
        id: `a${i + 1}`,
        label: label ?? '',
        lat: Number(lat),
        lon: Number(lon),
        mode: modes[m] ?? 'transit',
        level: Math.min(5, Math.max(1, Number(level) || 4)),
        maxMinutes: max ? Number(max) : null,
      }
    })
    .filter((a) => Number.isFinite(a.lat) && Number.isFinite(a.lon))
    .slice(0, 3)
}
function encodeFilters(f: Filters) {
  const parts: string[] = []
  if (f.maxPricePerM2) parts.push(`p:${f.maxPricePerM2}`)
  if (f.maxRentPerM2) parts.push(`r:${f.maxRentPerM2}`)
  if (f.maxNoiseDb) parts.push(`n:${f.maxNoiseDb}`)
  for (const m of f.mustHave) parts.push(`m:${m.category}:${m.maxWalkMin}`)
  return parts.join(',')
}
function decodeFilters(s: string | null): Filters {
  const f: Filters = { ...EMPTY_FILTERS, mustHave: [] }
  if (!s) return f
  for (const part of s.split(',')) {
    const [k, a, b] = part.split(':')
    if (k === 'p') f.maxPricePerM2 = Number(a) || null
    if (k === 'r') f.maxRentPerM2 = Number(a) || null
    if (k === 'n') f.maxNoiseDb = Number(a) || null
    if (k === 'm' && a) f.mustHave.push({ category: a, maxWalkMin: Number(b) || 10 } as MustHave)
  }
  return f
}

export function stateFromUrl(loc: Location = window.location): Partial<AppState> {
  const segs = loc.pathname.split('/').filter(Boolean)
  const city = CITY_IDS.includes(segs[0] as CityId) ? (segs[0] as CityId) : null
  const q = new URLSearchParams(loc.search)
  const lang = q.get('lang') as Lang | null
  const step = q.get('step') as Step | null
  const mode = q.get('mode')
  return {
    city,
    view: segs[1] === 'about' ? 'about' : 'app',
    lang: lang && LANGS.includes(lang) ? lang : city ? CITY_LANG[city] : browserLang(),
    step: step && ['persona', 'criteria', 'places', 'results'].includes(step) ? step : q.get('p') ? 'results' : 'persona',
    persona: q.get('p'),
    weights: decodeWeights(q.get('w')) ?? DEFAULT_WEIGHTS,
    anchors: decodeAnchors(q.get('a')),
    filters: decodeFilters(q.get('f')),
    budget: Number(q.get('b')) || null,
    mapMode: mode === 'commute' || (CRITERIA as readonly string[]).includes(mode ?? '') ? (mode as MapMode) : 'match',
    sel: q.get('sel'),
    tab: q.get('tab') === 'districts' ? 'districts' : 'places',
    compare: (q.get('cmp') ?? '').split(',').filter(Boolean).slice(0, 3),
  }
}

export function urlFromState(s: AppState): string {
  if (!s.city) return `/${s.lang !== browserLang() ? `?lang=${s.lang}` : ''}`
  const q = new URLSearchParams()
  q.set('v', '1')
  q.set('lang', s.lang)
  if (s.persona) q.set('p', s.persona)
  q.set('w', encodeWeights(s.weights))
  if (s.anchors.length) q.set('a', encodeAnchors(s.anchors))
  const f = encodeFilters(s.filters)
  if (f) q.set('f', f)
  if (s.budget) q.set('b', String(s.budget))
  if (s.step !== 'results') q.set('step', s.step)
  if (s.mapMode !== 'match') q.set('mode', s.mapMode)
  if (s.sel) q.set('sel', s.sel)
  if (s.tab !== 'places') q.set('tab', s.tab)
  if (s.compare.length) q.set('cmp', s.compare.join(','))
  return `/${s.city}${s.view === 'about' ? '/about' : ''}?${q.toString()}`
}

// ---------- store ----------
interface Actions {
  set: (p: Partial<AppState>) => void
  setCity: (c: CityId | null) => void
  setLang: (l: Lang) => void
  pickPersona: (id: string, weights: Record<string, number>) => void
  setLevel: (c: CriterionId, level: number) => void
  setAnchors: (a: Anchor[]) => void
  setFilters: (f: Partial<Filters>) => void
  select: (h3: string | null) => void
  toggleCompare: (id: string) => void
}

const initial: AppState = {
  city: null,
  view: 'app',
  lang: 'pl',
  step: 'persona',
  persona: null,
  weights: DEFAULT_WEIGHTS,
  anchors: [],
  filters: EMPTY_FILTERS,
  budget: null,
  mapMode: 'match',
  commuteAnchor: null,
  sel: null,
  tab: 'places',
  compare: [],
  hover: null,
  ...stateFromUrl(),
}

export const useApp = create<AppState & Actions>((set, get) => ({
  ...initial,
  set: (p) => set(p),
  setCity: (city) => {
    const s = get()
    // Switching city keeps persona, levels and language; anchors, price
    // limits and selection are city-specific so they reset.
    if (s.city && city && s.city !== city) {
      set({
        city,
        anchors: [],
        filters: { ...s.filters, maxPricePerM2: null, maxRentPerM2: null },
        budget: null,
        sel: null,
        compare: [],
        commuteAnchor: null,
        mapMode: s.mapMode === 'commute' ? 'match' : s.mapMode,
      })
    } else {
      set({ city, lang: s.city || !city ? s.lang : CITY_LANG[city], view: 'app' })
    }
  },
  setLang: (lang) => set({ lang }),
  pickPersona: (persona, weights) => set({ persona, weights: { ...DEFAULT_WEIGHTS, ...weights } as Weights }),
  setLevel: (c, level) => set((s) => ({ weights: { ...s.weights, [c]: level } })),
  setAnchors: (anchors) => set({ anchors: anchors.map((a, i) => ({ ...a, id: `a${i + 1}` })) }),
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),
  select: (sel) => set({ sel }),
  toggleCompare: (id) =>
    set((s) => ({
      compare: s.compare.includes(id) ? s.compare.filter((x) => x !== id) : [...s.compare, id].slice(-3),
    })),
}))

// Mirror to the URL. City/step/view changes push history so Back works.
let lastUrl = window.location.pathname + window.location.search
let fromPop = false
useApp.subscribe((s, prev) => {
  if (fromPop) return
  const url = urlFromState(s)
  if (url === lastUrl) return
  const push = s.city !== prev.city || s.step !== prev.step || s.view !== prev.view
  if (push) window.history.pushState(null, '', url)
  else window.history.replaceState(null, '', url)
  lastUrl = url
})
window.addEventListener('popstate', () => {
  fromPop = true
  useApp.setState({ ...stateFromUrl(), hover: null })
  lastUrl = window.location.pathname + window.location.search
  fromPop = false
})

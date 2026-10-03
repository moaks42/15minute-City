// TEMPORARY mock of GET /api/{city}/meta and /api/cities (README §3.3, §3.4, §7.1).
import type { City, CityId, Criterion, Meta, Persona, Weights } from '@/api/types'

export const MOCK_CITIES: City[] = [
  {
    id: 'krakow',
    name: { pl: 'Kraków', cs: 'Krakov', en: 'Kraków' },
    defaultLang: 'pl',
    currency: 'PLN',
    center: [50.0614, 19.9366],
    zoom: 11.5,
  },
  {
    id: 'praha',
    name: { pl: 'Praga', cs: 'Praha', en: 'Prague' },
    defaultLang: 'cs',
    currency: 'CZK',
    center: [50.0755, 14.4378],
    zoom: 11,
  },
]

const ind = (id: string, pl: string, cs: string, en: string, unit?: string) => ({ id, label: { pl, cs, en }, unit })

const CRITERIA_DEF: Omit<Criterion, 'coverage'>[] = [
  { id: 'commute', emoji: '🧭', label: {}, indicators: [ind('anchor_minutes', 'Czas dojazdu', 'Doba dojezdu', 'Travel time', 'min')] },
  {
    id: 'transit',
    emoji: '🚋',
    label: {},
    indicators: [
      ind('stop_walk_min', 'Najbliższy przystanek', 'Nejbližší zastávka', 'Nearest stop', 'min'),
      ind('departures_per_hour', 'Odjazdy/h (7–9)', 'Odjezdy/h (7–9)', 'Departures/h (7–9)', '/h'),
      ind('rail_station_walk_min', 'Stacja kolejowa', 'Metro / vlak', 'Rail / metro station', 'min'),
    ],
  },
  { id: 'active', emoji: '🚲', label: {}, indicators: [ind('cycleway_km_1km', 'Drogi rowerowe w promieniu 1 km', 'Cyklostezky do 1 km', 'Cycle paths within 1 km', 'km')] },
  {
    id: 'green',
    emoji: '🌳',
    label: {},
    indicators: [
      ind('green_share_500m', 'Udział zieleni (500 m)', 'Podíl zeleně (500 m)', 'Green share (500 m)', '%'),
      ind('park_walk_min', 'Park ≥ 2 ha', 'Park ≥ 2 ha', 'Park ≥ 2 ha', 'min'),
    ],
  },
  { id: 'education', emoji: '🎓', label: {}, indicators: [ind('primary_school_walk_min', 'Szkoła podstawowa', 'Základní škola', 'Primary school', 'min')] },
  { id: 'family', emoji: '🧸', label: {}, indicators: [ind('playgrounds_500m', 'Place zabaw (500 m)', 'Dětská hřiště (500 m)', 'Playgrounds (500 m)')] },
  { id: 'safety', emoji: '🛡️', label: {}, indicators: [ind('crime_per_1000', 'Zdarzenia / 1000 mieszk.', 'Události / 1000 obyv.', 'Incidents / 1,000 residents')] },
  { id: 'price', emoji: '💰', label: {}, indicators: [] },
  { id: 'shops', emoji: '🛒', label: {}, indicators: [ind('supermarket_walk_min', 'Supermarket', 'Supermarket', 'Supermarket', 'min')] },
  { id: 'health', emoji: '🏥', label: {}, indicators: [ind('gp_walk_min', 'Przychodnia POZ', 'Praktický lékař', 'GP clinic', 'min')] },
  {
    id: 'environment',
    emoji: '🌬️',
    label: {},
    indicators: [
      ind('noise_db', 'Hałas', 'Hluk', 'Noise', 'dB'),
      ind('pm25', 'PM2,5', 'PM2,5', 'PM2.5', 'µg/m³'),
    ],
  },
  { id: 'leisure', emoji: '🎭', label: {}, indicators: [ind('venues_10min', 'Lokale i kultura (10 min)', 'Podniky a kultura (10 min)', 'Venues & culture (10 min)')] },
  { id: 'accessibility', emoji: '♿', label: {}, indicators: [ind('accessible_trips_share', 'Kursy niskopodłogowe', 'Bezbariérové spoje', 'Step-free trips', '%')] },
]

const w = (a: number[]): Weights => ({
  commute: a[0],
  transit: a[1],
  active: a[2],
  green: a[3],
  education: a[4],
  family: a[5],
  safety: a[6],
  price: a[7],
  shops: a[8],
  health: a[9],
  environment: a[10],
  leisure: a[11],
  accessibility: a[12],
})

export const MOCK_PERSONAS: Persona[] = [
  { id: 'student', emoji: '🎒', label: {}, weights: w([5, 5, 3, 2, 1, 0, 3, 5, 3, 1, 2, 5, 0]), suggestedAnchors: [{ label: { pl: 'Moja uczelnia', cs: 'Moje škola/univerzita', en: 'My university' }, mode: 'transit' }] },
  { id: 'working', emoji: '💼', label: {}, weights: w([5, 4, 4, 3, 0, 0, 3, 4, 4, 2, 3, 4, 0]), suggestedAnchors: [{ label: { pl: 'Praca', cs: 'Práce', en: 'Work' }, mode: 'transit' }] },
  { id: 'parent', emoji: '👨‍👩‍👧', label: {}, weights: w([3, 3, 2, 5, 5, 5, 5, 3, 4, 4, 4, 1, 2]), suggestedAnchors: [{ label: { pl: 'Praca', cs: 'Práce', en: 'Work' }, mode: 'transit' }, { label: { pl: 'Szkoła dziecka', cs: 'Škola dítěte', en: "Child's school" }, mode: 'walk' }] },
  { id: 'expecting', emoji: '🤰', label: {}, weights: w([3, 4, 2, 4, 3, 4, 4, 3, 4, 5, 5, 1, 4]) },
  { id: 'senior', emoji: '🧓', label: {}, weights: w([1, 4, 3, 4, 0, 0, 5, 3, 5, 5, 4, 3, 5]) },
  { id: 'custom', emoji: '✏️', label: {}, weights: w([3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]) },
]

export function mockMeta(city: CityId): Meta {
  const isK = city === 'krakow'
  const criteria: Criterion[] = CRITERIA_DEF.map((c) => ({
    ...c,
    indicators:
      c.id === 'price'
        ? [
            isK
              ? ind('buy_per_m2', 'Mediana ceny transakcyjnej', 'Medián transakční ceny', 'Median sale price', 'zł/m²')
              : ind('rent_per_m2', 'Mediana czynszu', 'Medián nájemného', 'Median rent', 'Kč/m²/měs.'),
          ]
        : c.indicators,
    coverage: !isK && c.id === 'accessibility' ? 0.4 : 1,
  }))
  return {
    city,
    levels: { 0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 8 },
    levelEmoji: { 1: '😐', 2: '🙂', 3: '😊', 4: '😍', 5: '🤩' },
    criteria,
    personas: MOCK_PERSONAS,
    mustHaveCategories: ['nursery', 'kindergarten', 'primary_school', 'tram_stop', 'metro_station', 'park', 'pharmacy', 'gp_clinic', 'supermarket', 'maternity_ward'],
    price: isK
      ? { indicator: 'buy_per_m2', mode: 'buy', unit: 'zł/m²' }
      : { indicator: 'rent_per_m2', mode: 'rent', unit: { pl: 'Kč/m²/mies.', cs: 'Kč/m²/měs.', en: 'CZK/m²/month' } },
    manifest: (isK
      ? ['osm_krakow', 'gtfs_ztp', 'msip', 'gios', 'men_schools', 'rcn', 'safety_krk', 'krk_open']
      : ['osm_praha', 'gtfs_pid', 'ipr', 'ruian', 'msmt_schools', 'nrpzs', 'chmi_air', 'police_cz', 'mf_rent']
    ).map((key) => ({ key, status: 'ok' as const, fetchedAt: '2026-10-03', note: 'mock' })),
  }
}

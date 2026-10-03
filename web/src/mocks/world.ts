// TEMPORARY mock world (deleted once contracts/fixtures land on main).
// Plausible fake values on a real H3 res-9 grid around each city centre,
// shaped like the engine API (§7.2). Labelled "demo data" in the UI.
import { cellToBoundary, cellToLatLng, gridDisk, latLngToCell, greatCircleDistance } from 'h3-js'
import type { CityId, CriterionId } from '@/api/types'
import { CRITERIA } from '@/api/types'

interface Hood {
  name: string
  lat: number
  lon: number
  district: string
}

const HOODS: Record<CityId, Hood[]> = {
  krakow: [
    ['Stare Miasto', 50.0614, 19.9372, 'I Stare Miasto'],
    ['Kazimierz', 50.051, 19.945, 'I Stare Miasto'],
    ['Kleparz', 50.069, 19.942, 'I Stare Miasto'],
    ['Grzegórzki', 50.059, 19.96, 'II Grzegórzki'],
    ['Zabłocie', 50.048, 19.96, 'XIII Podgórze'],
    ['Podgórze', 50.043, 19.95, 'XIII Podgórze'],
    ['Płaszów', 50.04, 19.985, 'XIII Podgórze'],
    ['Krowodrza', 50.075, 19.92, 'V Krowodrza'],
    ['Azory', 50.085, 19.915, 'IV Prądnik Biały'],
    ['Prądnik Biały', 50.095, 19.93, 'IV Prądnik Biały'],
    ['Prądnik Czerwony', 50.085, 19.965, 'III Prądnik Czerwony'],
    ['Olsza', 50.075, 19.96, 'III Prądnik Czerwony'],
    ['Bronowice', 50.08, 19.885, 'VI Bronowice'],
    ['Salwator', 50.053, 19.91, 'VII Zwierzyniec'],
    ['Wola Justowska', 50.06, 19.87, 'VII Zwierzyniec'],
    ['Bielany', 50.045, 19.845, 'VII Zwierzyniec'],
    ['Dębniki', 50.045, 19.92, 'VIII Dębniki'],
    ['Ruczaj', 50.025, 19.905, 'VIII Dębniki'],
    ['Łagiewniki', 50.025, 19.935, 'IX Łagiewniki-Borek Fałęcki'],
    ['Swoszowice', 49.995, 19.94, 'X Swoszowice'],
    ['Kurdwanów', 50.015, 19.955, 'XI Podgórze Duchackie'],
    ['Prokocim', 50.02, 20.0, 'XII Bieżanów-Prokocim'],
    ['Bieżanów', 50.015, 20.03, 'XII Bieżanów-Prokocim'],
    ['Czyżyny', 50.07, 20.01, 'XIV Czyżyny'],
    ['Mistrzejowice', 50.095, 20.005, 'XV Mistrzejowice'],
    ['Bieńczyce', 50.085, 20.025, 'XVI Bieńczyce'],
    ['Wzgórza Krzesławickie', 50.1, 20.06, 'XVII Wzgórza Krzesławickie'],
    ['Nowa Huta', 50.072, 20.038, 'XVIII Nowa Huta'],
  ].map(([name, lat, lon, district]) => ({ name, lat, lon, district }) as Hood),
  praha: [
    ['Staré Město', 50.087, 14.421, 'Praha 1'],
    ['Nové Město', 50.079, 14.425, 'Praha 1'],
    ['Vinohrady', 50.076, 14.445, 'Praha 2'],
    ['Žižkov', 50.084, 14.46, 'Praha 3'],
    ['Karlín', 50.093, 14.452, 'Praha 8'],
    ['Libeň', 50.103, 14.475, 'Praha 8'],
    ['Holešovice', 50.103, 14.438, 'Praha 7'],
    ['Troja', 50.116, 14.42, 'Praha 7'],
    ['Bubeneč', 50.102, 14.408, 'Praha 6'],
    ['Dejvice', 50.1, 14.39, 'Praha 6'],
    ['Břevnov', 50.084, 14.36, 'Praha 6'],
    ['Ruzyně', 50.085, 14.31, 'Praha 17'],
    ['Smíchov', 50.07, 14.403, 'Praha 5'],
    ['Stodůlky', 50.045, 14.32, 'Praha 13'],
    ['Nusle', 50.064, 14.44, 'Praha 4'],
    ['Michle', 50.053, 14.46, 'Praha 4'],
    ['Krč', 50.035, 14.45, 'Praha 4'],
    ['Vršovice', 50.07, 14.46, 'Praha 10'],
    ['Strašnice', 50.073, 14.495, 'Praha 10'],
    ['Chodov', 50.031, 14.49, 'Praha 11'],
    ['Modřany', 50.005, 14.41, 'Praha 12'],
    ['Hostivař', 50.057, 14.53, 'Praha 15'],
    ['Vysočany', 50.11, 14.5, 'Praha 9'],
    ['Prosek', 50.118, 14.495, 'Praha 9'],
    ['Letňany', 50.133, 14.515, 'Praha 18'],
    ['Černý Most', 50.105, 14.58, 'Praha 14'],
  ].map(([name, lat, lon, district]) => ({ name, lat, lon, district }) as Hood),
}

const CENTER: Record<CityId, [number, number]> = {
  krakow: [50.0614, 19.9366],
  praha: [50.0755, 14.4378],
}
const RINGS: Record<CityId, number> = { krakow: 32, praha: 39 }

// Big green areas (lat, lon, radius km) — makes the green layer look sane.
const GREEN: Record<CityId, [number, number, number][]> = {
  krakow: [
    [50.055, 19.85, 2.2], // Las Wolski
    [50.061, 19.912, 0.8], // Błonia
    [50.085, 20.06, 1.3], // Łąki Nowohuckie
    [50.015, 19.92, 1.0], // Zakrzówek / Ruczaj
  ],
  praha: [
    [50.106, 14.42, 1.0], // Stromovka
    [50.095, 14.33, 1.6], // Divoká Šárka
    [50.057, 14.53, 1.4], // Hostivař
    [50.04, 14.44, 1.2], // Kunratický les
    [50.115, 14.41, 0.9], // Troja
  ],
}

// Pollution / noise hotspots (Nowa Huta steelworks, airport, highways).
const BAD_AIR: Record<CityId, [number, number, number][]> = {
  krakow: [[50.07, 20.1, 3]],
  praha: [
    [50.1, 14.26, 2.5],
    [50.03, 14.49, 1.0],
  ],
}

function hash01(s: string, salt = 0): number {
  let h = 2166136261 ^ salt
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 10000) / 10000
}

const clamp = (x: number, a = 0, b = 100) => Math.max(a, Math.min(b, x))
const km = (a: [number, number], b: [number, number]) => greatCircleDistance(a, b, 'km')

export interface MockCell {
  h3: string
  lat: number
  lon: number
  hood: Hood
  habitable: boolean
  population: number
  criteria: Record<CriterionId, number>
  raw: {
    stopWalkMin: number
    depPerHour: number
    noiseDb: number
    pricePerM2: number
    parkWalkMin: number
    schoolWalkMin: number
    supermarketWalkMin: number
    gpWalkMin: number
    pm25: number
    railWalkMin: number
  }
  archetype: { id: string; p: number }
}

export interface MockWorld {
  city: CityId
  cells: MockCell[]
  byId: Map<string, MockCell>
  medians: Record<CriterionId, number>
  grid: GeoJSON.FeatureCollection<GeoJSON.Polygon, Record<string, unknown>>
}

const cache = new Map<CityId, MockWorld>()

function archetypeFor(c: Omit<MockCell, 'archetype'>, dCentre: number): { id: string; p: number } {
  const j = hash01(c.h3, 7) * 0.25
  if (dCentre < 1.6) return { id: 'historic_core', p: 0.72 + j }
  if (c.criteria.leisure > 70 && c.criteria.transit > 70) return { id: 'student_buzz', p: 0.6 + j }
  if (c.criteria.green > 72) return { id: 'green_edge', p: 0.62 + j }
  if (c.criteria.family > 65 && c.criteria.environment > 55) return { id: 'family_quiet', p: 0.58 + j }
  if (c.raw.noiseDb > 64) return { id: 'transit_corridor', p: 0.55 + j }
  if (dCentre > 6.5) return { id: 'suburban_calm', p: 0.6 + j }
  return { id: 'urban_mix', p: 0.55 + j }
}

export function getWorld(city: CityId): MockWorld {
  const hit = cache.get(city)
  if (hit) return hit
  const centre = CENTER[city]
  const origin = latLngToCell(centre[0], centre[1], 9)
  const ids = gridDisk(origin, RINGS[city])
  const hoods = HOODS[city]
  const priceBase = city === 'krakow' ? 17500 : 430
  const priceStep = city === 'krakow' ? 850 : 16
  const cells: MockCell[] = []
  for (const h3 of ids) {
    const [lat, lon] = cellToLatLng(h3)
    const d = km([lat, lon], centre)
    let best = hoods[0]
    let bd = Infinity
    for (const h of hoods) {
      const dd = km([lat, lon], [h.lat, h.lon])
      if (dd < bd) {
        bd = dd
        best = h
      }
    }
    const n = (salt: number, amp: number) => (hash01(h3, salt) - 0.5) * amp
    const wave = Math.sin(lat * 140) * Math.cos(lon * 90) * 8
    const greenBoost = Math.max(...GREEN[city].map(([la, lo, r]) => clamp(100 * (1 - km([lat, lon], [la, lo]) / (r * 1.8)))))
    const airPenalty = Math.max(0, ...BAD_AIR[city].map(([la, lo, r]) => clamp(60 * (1 - km([lat, lon], [la, lo]) / (r * 2)))))
    const inGreenCore = greenBoost > 75
    const habitable = !inGreenCore && d < RINGS[city] * 0.17 && hash01(h3, 99) > 0.08

    const transit = clamp(98 - d * 9 + wave + n(1, 18))
    const leisure = clamp(100 - d * 14 + n(2, 20))
    const green = clamp(25 + greenBoost * 0.8 + d * 3 + n(3, 20))
    const environment = clamp(25 + d * 8 - airPenalty + greenBoost * 0.2 + n(4, 16))
    const price = clamp(10 + d * 11 + n(5, 22))
    const shops = clamp(95 - d * 8 + n(6, 24))
    const health = clamp(90 - d * 7 + n(7, 26))
    const education = clamp(80 - Math.abs(d - 3.5) * 9 + n(8, 26))
    const family = clamp(55 + (d > 2 && d < 7 ? 20 : -10) + greenBoost * 0.15 + n(9, 26))
    const safety = clamp(45 + d * 5 + hash01(best.district, 3) * 25 + n(10, 8))
    const active = clamp(80 - Math.abs(d - 2.5) * 8 + greenBoost * 0.15 + n(11, 20))
    const accessibility = clamp(transit * 0.7 + 20 + n(12, 16))
    const criteria = {
      commute: 50,
      transit,
      active,
      green,
      education,
      family,
      safety,
      price,
      shops,
      health,
      environment,
      leisure,
      accessibility,
    } as Record<CriterionId, number>
    for (const k of CRITERIA) criteria[k] = Math.round(criteria[k])

    const raw = {
      stopWalkMin: Math.max(1, Math.round(1 + d * 0.9 + hash01(h3, 20) * 5)),
      depPerHour: Math.max(2, Math.round(70 - d * 7 + n(21, 20))),
      noiseDb: Math.round(clamp(68 - d * 1.6 + airPenalty * 0.15 + n(22, 8), 38, 78)),
      pricePerM2: Math.round((priceBase - d * priceStep) * (1 + n(23, 0.18))),
      parkWalkMin: Math.max(1, Math.round(14 - greenBoost * 0.12 + hash01(h3, 24) * 6)),
      schoolWalkMin: Math.max(2, Math.round(4 + Math.abs(d - 3.5) * 1.5 + hash01(h3, 25) * 6)),
      supermarketWalkMin: Math.max(1, Math.round(2 + d * 0.7 + hash01(h3, 26) * 6)),
      gpWalkMin: Math.max(2, Math.round(4 + d * 1.1 + hash01(h3, 27) * 7)),
      pm25: Math.round(clamp(14 + airPenalty * 0.2 - d * 0.4 + n(28, 4), 6, 40) * 10) / 10,
      railWalkMin: Math.max(2, Math.round(4 + d * 2.2 + hash01(h3, 29) * 8)),
    }
    if (city === 'krakow') raw.pricePerM2 = Math.round(raw.pricePerM2 / 10) * 10
    const partial = {
      h3,
      lat,
      lon,
      hood: best,
      habitable,
      population: habitable ? Math.round(40 + 600 * Math.max(0, 1 - d / 9) * hash01(h3, 30)) : 0,
      criteria,
      raw,
    }
    cells.push({ ...partial, archetype: archetypeFor(partial, d) })
  }

  const medians = {} as Record<CriterionId, number>
  const hab = cells.filter((c) => c.habitable)
  for (const k of CRITERIA) {
    const vals = hab.map((c) => c.criteria[k]).sort((a, b) => a - b)
    medians[k] = vals[Math.floor(vals.length / 2)] ?? 50
  }

  const grid: MockWorld['grid'] = {
    type: 'FeatureCollection',
    features: cells.map((c) => {
      const ring = cellToBoundary(c.h3, true)
      ring.push(ring[0])
      return {
        type: 'Feature',
        id: c.h3,
        properties: {
          h3: c.h3,
          district_id: c.hood.district,
          district_name: c.hood.district,
          neighborhood: c.hood.name,
          habitable: c.habitable ? 1 : 0,
          population_est: c.population,
        },
        geometry: { type: 'Polygon', coordinates: [ring] },
      }
    }),
  }

  const world: MockWorld = { city, cells, byId: new Map(cells.map((c) => [c.h3, c])), medians, grid }
  cache.set(city, world)
  return world
}

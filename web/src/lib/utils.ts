import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Lang, Localized } from '@/api/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Resolve a label that may be a plain string or a {pl,cs,en} map. */
export function L(label: Localized | undefined, lang: Lang): string {
  if (!label) return ''
  if (typeof label === 'string') return label
  return label[lang] ?? label.en ?? label.pl ?? Object.values(label)[0] ?? ''
}

export function debounce<A extends unknown[]>(fn: (...a: A) => void, ms: number) {
  let t: ReturnType<typeof setTimeout> | undefined
  return (...a: A) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...a), ms)
  }
}

/** [[west, south], [east, north]] of a polygon, for fitBounds and a rough centre. */
export function geoBounds(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): [[number, number], [number, number]] {
  const rings = g.type === 'Polygon' ? g.coordinates : g.coordinates.flat()
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const ring of rings)
    for (const [x, y] of ring) {
      w = Math.min(w, x)
      s = Math.min(s, y)
      e = Math.max(e, x)
      n = Math.max(n, y)
    }
  return [
    [w, s],
    [e, n],
  ]
}

import { useQuery } from '@tanstack/react-query'
import { useId, useMemo } from 'react'
import { api } from '@/api/client'
import { useGrid } from '@/api/hooks'
import type { CityId } from '@/api/types'
import type { PersonaLite } from '@/content/defaults'
import { useApp } from '@/state/store'
import { personaRequest } from './shared'

const GOLD = '#D4A84B'
const M_PER_DEG = 111_320
const UNIT = 10 // metres per SVG unit
const TOP_SHARE = 0.15 // cells drawn as "high match"
const HEX = 35 // width of a res-9 cell (~350 m) in SVG units

type Shape = { viewBox: string; outline: string; cell: Map<string, string> }

/** The city's H3 cells as SVG paths (equirectangular around the city: fine at this scale). */
function toShape(fc: GeoJSON.FeatureCollection): Shape | null {
  const rings: [string, GeoJSON.Position[][]][] = []
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const f of fc.features) {
    const g = f.geometry
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []
    for (const poly of polys)
      for (const [x, y] of poly[0]) {
        w = Math.min(w, x)
        e = Math.max(e, x)
        s = Math.min(s, y)
        n = Math.max(n, y)
      }
    rings.push([String(f.properties?.h3 ?? f.id), polys.map((p) => p[0])])
  }
  if (!rings.length) return null
  const kx = (Math.cos((((s + n) / 2) * Math.PI) / 180) * M_PER_DEG) / UNIT
  const ky = M_PER_DEG / UNIT
  const cell = new Map<string, string>()
  for (const [id, polys] of rings)
    cell.set(id, polys.map((ring) => 'M' + ring.map(([x, y]) => `${((x - w) * kx).toFixed(1)} ${((n - y) * ky).toFixed(1)}`).join('L') + 'Z').join(''))
  const width = (e - w) * kx
  const height = (n - s) * ky
  const pad = Math.max(width, height) * 0.04
  return { viewBox: `${-pad} ${-pad} ${width + 2 * pad} ${height + 2 * pad}`, outline: [...cell.values()].join(''), cell }
}

/** Decorative silhouette of the city's real hex grid: thin outlines, the persona's
 *  best cells faintly filled, its single best cell in gold. Fades out to the left. */
export function HeroGrid({ city, persona, className }: { city: CityId; persona: PersonaLite; className?: string }) {
  const lang = useApp((s) => s.lang)
  const glow = `glow${useId().replace(/\W/g, '')}` // usable inside url(#…)
  const grid = useGrid(city)
  const score = useQuery({
    queryKey: ['welcome-hero', city, persona.id],
    queryFn: () => api.score(city, personaRequest(lang, persona, 1, true)),
    staleTime: Infinity,
  })
  const shape = useMemo(() => (grid.data ? toShape(grid.data) : null), [grid.data])
  const marks = useMemo(() => {
    if (!shape || !score.data) return null
    const passing = score.data.cells.filter((c) => c[2] === 1).sort((a, b) => b[1] - a[1])
    const cut = passing[Math.floor(passing.length * TOP_SHARE)]?.[1] ?? 101
    const high = passing.filter((c) => c[1] >= cut).map((c) => shape.cell.get(c[0]) ?? '')
    const best = score.data.top[0]?.id
    return { high: high.join(''), top: best ? shape.cell.get(best) : undefined }
  }, [shape, score.data])

  if (!shape) return null
  return (
    <svg
      viewBox={shape.viewBox}
      preserveAspectRatio="xMaxYMid meet"
      className={className}
      style={{ maskImage: 'linear-gradient(to right, transparent 0%, #000 45%)', WebkitMaskImage: 'linear-gradient(to right, transparent 0%, #000 45%)' }}
      aria-hidden
    >
      <defs>
        <filter id={glow} x="-2" y="-2" width="5" height="5">
          <feGaussianBlur stdDeviation={HEX / 2} />
        </filter>
      </defs>
      <path d={shape.outline} fill="none" stroke="#fff" strokeOpacity={0.2} strokeWidth={0.75} vectorEffect="non-scaling-stroke" />
      {marks?.high && <path d={marks.high} fill="#fff" fillOpacity={0.13} />}
      {marks?.top && (
        <>
          <path d={marks.top} fill={GOLD} filter={`url(#${glow})`} className="motion-safe:animate-pulse" />
          <path d={marks.top} fill={GOLD} stroke="#fff" strokeOpacity={0.6} strokeWidth={1} vectorEffect="non-scaling-stroke" />
        </>
      )}
    </svg>
  )
}

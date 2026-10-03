import { Search, X } from 'lucide-react'
import { cellToLatLng, gridDisk, latLngToCell } from 'h3-js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { useGrid } from '@/api/hooks'
import type { GeocodeHit } from '@/api/types'
import { GeoSearch } from '@/components/common/GeoSearch'
import { Button } from '@/components/ui/button'
import { useApp } from '@/state/store'

const MSG_MS = 4000
const MAX_RING = 3

type Resolved = { h3: string | null; msg: 'nearest' | 'noneNearby' | 'outside' | null }

/** The searched point's res-9 cell if people live there, else the nearest habitable cell within 3 rings. */
function resolveCell(lat: number, lon: number, habitable: ReadonlyMap<string, boolean>): Resolved {
  const h = latLngToCell(lat, lon, 9)
  if (habitable.size === 0 || habitable.get(h)) return { h3: h, msg: null }
  for (let k = 1; k <= MAX_RING; k++) {
    const near = gridDisk(h, k).filter((c) => habitable.get(c))
    if (near.length) {
      const d = (c: string) => {
        const [a, b] = cellToLatLng(c)
        return (a - lat) ** 2 + ((b - lon) * Math.cos((lat * Math.PI) / 180)) ** 2
      }
      near.sort((x, y) => d(x) - d(y))
      return { h3: near[0], msg: 'nearest' }
    }
  }
  return { h3: null, msg: habitable.has(h) ? 'noneNearby' : 'outside' }
}

/** Address search in the header (results view only): desktop field in the middle, mobile magnifier → full-width field. */
export function HeaderSearch() {
  const { t } = useTranslation()
  const city = useApp((s) => s.city)
  const step = useApp((s) => s.step)
  const view = useApp((s) => s.view)
  const select = useApp((s) => s.select)
  const grid = useGrid(city)
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const mobileRef = useRef<HTMLDivElement>(null)

  const habitable = useMemo(() => {
    const m = new Map<string, boolean>()
    for (const f of grid.data?.features ?? []) {
      const p = f.properties as { h3: string; habitable?: boolean | number }
      m.set(p.h3, !!p.habitable)
    }
    return m
  }, [grid.data])

  useEffect(() => {
    if (!msg) return
    const h = setTimeout(() => setMsg(null), MSG_MS)
    return () => clearTimeout(h)
  }, [msg])

  useEffect(() => {
    if (open) mobileRef.current?.querySelector('input')?.focus()
  }, [open])

  if (!city || step !== 'results' || view !== 'app') return null

  const onPick = (hit: GeocodeHit) => {
    const r = resolveCell(hit.lat, hit.lon, habitable)
    if (r.h3) select(r.h3)
    setMsg(r.msg ? t(`mapUi.${r.msg}`) : null)
    setOpen(false)
  }
  const placeholder = t('mapUi.searchPlaceholder')

  return (
    <>
      <div className="hidden min-w-0 flex-1 justify-center md:flex">
        <GeoSearch className="w-full max-w-[420px]" onPick={onPick} placeholder={placeholder} />
      </div>
      <Button variant="ghost" size="icon" className="ml-auto md:hidden" onClick={() => setOpen(true)} aria-label={t('mapUi.openSearch')} aria-expanded={open}>
        <Search size={18} />
      </Button>
      {open && (
        <div
          ref={mobileRef}
          className="absolute inset-0 z-40 flex items-center gap-2 bg-surface px-3 md:hidden"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false)
          }}
        >
          <GeoSearch className="min-w-0 flex-1" onPick={onPick} placeholder={placeholder} />
          <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label={t('mapUi.closeSearch')}>
            <X size={20} />
          </Button>
        </div>
      )}
      {msg &&
        createPortal(
          <div role="status" className="fixed left-1/2 top-20 z-50 max-w-[90vw] -translate-x-1/2 rounded-full bg-ink px-4 py-2 text-center text-sm text-white shadow-[var(--shadow-pop)]">
            {msg}
          </div>,
          document.body,
        )}
    </>
  )
}

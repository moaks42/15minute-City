import { MapPin } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { CityId, GeocodeHit } from '@/api/types'
import { cn } from '@/lib/utils'
import { useApp } from '@/state/store'

const inputCls = 'h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] placeholder:text-ink-3 focus:border-accent focus:outline-none focus-visible:outline-3 focus-visible:outline-accent'

export function GeoSearch({ onPick, city: cityProp, placeholder, className }: { onPick: (h: GeocodeHit) => void; city?: CityId; placeholder?: string; className?: string }) {
  const { t } = useTranslation()
  const storeCity = useApp((s) => s.city)
  const city = (cityProp ?? storeCity)!
  const label = placeholder ?? t('places.searchPlaceholder')
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<GeocodeHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState(0)
  const listId = useId()

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits(null)
      return
    }
    setBusy(true)
    const h = setTimeout(() => {
      api
        .geocode(city, q.trim())
        .then((r) => {
          setHits(r)
          setActive(0)
        })
        .catch(() => setHits([]))
        .finally(() => setBusy(false))
    }, 250)
    return () => clearTimeout(h)
  }, [q, city])

  const pick = (h: GeocodeHit) => {
    onPick(h)
    setQ('')
    setHits(null)
  }

  return (
    <div className={cn('relative', className)}>
      <MapPin size={18} className="pointer-events-none absolute left-3 top-3 text-ink-3" />
      <input
        className={cn(inputCls, 'pl-9')}
        placeholder={label}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        role="combobox"
        aria-expanded={!!hits?.length}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={label}
        data-testid="geo-search"
        onKeyDown={(e) => {
          if (!hits?.length) return
          if (e.key === 'ArrowDown') setActive((a) => Math.min(hits.length - 1, a + 1))
          else if (e.key === 'ArrowUp') setActive((a) => Math.max(0, a - 1))
          else if (e.key === 'Enter') {
            e.preventDefault()
            pick(hits[active])
          } else return
          e.preventDefault()
        }}
      />
      {q.trim().length >= 2 && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-[var(--shadow-pop)]">
          {busy && !hits && <p className="px-3 py-2 text-sm text-ink-3">{t('places.searching')}</p>}
          {hits && hits.length === 0 && <p className="px-3 py-2 text-sm text-ink-3">{t('places.searchNoResults')}</p>}
          {hits && hits.length > 0 && (
            <ul id={listId} role="listbox">
              {hits.map((h, i) => (
                <li
                  key={`${h.label}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    pick(h)
                  }}
                  className={cn('cursor-pointer px-3 py-2.5 text-sm', i === active && 'bg-accent-soft')}
                >
                  {h.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

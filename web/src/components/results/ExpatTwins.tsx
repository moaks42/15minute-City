import { useQuery } from '@tanstack/react-query'
import { latLngToCell } from 'h3-js'
import { ArrowRight, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { CityId, GeocodeHit } from '@/api/types'
import { GeoSearch } from '@/components/common/GeoSearch'
import { STATIC_FALLBACK } from '@/lib/env'
import { archetypeInfo } from '@/lib/format'
import { useApp } from '@/state/store'

/** Relocation helper: pick your current address in the other city, get look-alike places here. */
export function ExpatTwins({ city }: { city: CityId }) {
  const { t } = useTranslation()
  const { lang, select } = useApp()
  const other: CityId = city === 'krakow' ? 'praha' : 'krakow'
  const [home, setHome] = useState<{ label: string; h3: string } | null>(null)
  const twins = useQuery({
    queryKey: ['expat-twins', other, home?.h3, city, lang],
    queryFn: () => api.twins(other, home!.h3, city, lang),
    enabled: !!home && !STATIC_FALLBACK,
    staleTime: Infinity,
  })
  const items = twins.data?.items.slice(0, 5) ?? []

  return (
    <section className="mb-3 rounded-2xl border border-accent bg-accent-soft p-3" data-testid="expat-twins">
      <h3 className="font-semibold">
        <span aria-hidden>🧳 </span>
        {t('expat.title', { in: t(`cities.in.${other}`) })}
      </h3>
      {STATIC_FALLBACK ? (
        <p className="mt-1 text-sm text-ink-3">{t('expat.unavailable')}</p>
      ) : !home ? (
        <>
          <p className="mb-2 mt-1 text-sm text-ink-2">{t('expat.lead', { in: t(`cities.in.${city}`) })}</p>
          <GeoSearch city={other} placeholder={t('expat.placeholder')} onPick={(h: GeocodeHit) => setHome({ label: h.label, h3: h.h3 ?? latLngToCell(h.lat, h.lon, 9) })} />
        </>
      ) : (
        <>
          <p className="mb-2 mt-1 flex items-center gap-2 text-sm text-ink-2">
            <span className="min-w-0 flex-1 truncate">{t('expat.from', { name: home.label })}</span>
            <button className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-xs font-medium hover:bg-surface" onClick={() => setHome(null)}>
              <X size={14} /> {t('expat.change')}
            </button>
          </p>
          {twins.isPending && (
            <div className="h-24 animate-pulse rounded-xl bg-sunken" aria-busy="true" aria-label={t('expat.loading')} />
          )}
          {twins.isError && (
            <p className="text-sm text-ink-3" role="alert">
              {t('expat.error')}
            </p>
          )}
          {twins.isSuccess && items.length === 0 && <p className="text-sm text-ink-3">{t('expat.empty')}</p>}
          <ul className="space-y-2">
            {items.map((tw) => {
              const a = tw.archetype ? archetypeInfo(tw.archetype.id, lang) : null
              return (
                <li key={tw.id}>
                  <button
                    className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface p-3 text-left hover:border-accent"
                    onClick={() => select(tw.id)}
                    data-testid="expat-twin"
                  >
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sunken text-sm font-bold tabular-nums">{Math.round(tw.similarity * 100)}%</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{tw.name}</span>
                      <span className="block truncate text-xs text-ink-3">
                        {tw.district?.name}
                        {a && ` · ${a.label}`}
                      </span>
                    </span>
                    <span className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-accent">
                      {t('expat.show')} <ArrowRight size={14} />
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}

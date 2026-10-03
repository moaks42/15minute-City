import { latLngToCell } from 'h3-js'
import { AlertTriangle, Check, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useScore } from '@/api/hooks'
import type { TopItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CRITERION_EMOJI } from '@/content/defaults'
import { archetypeInfo, fmtPricePerM2 } from '@/lib/format'
import { CATEGORICAL, seqColor } from '@/lib/palette'
import { cn } from '@/lib/utils'
import { useApp } from '@/state/store'

export function ScoreBadge({ score, size = 'md' }: { score: number; size?: 'md' | 'lg' }) {
  const dark = score >= 57
  return (
    <span
      className={cn('grid shrink-0 place-items-center rounded-xl font-bold tabular-nums', size === 'lg' ? 'h-16 w-16 text-2xl' : 'h-12 w-12 text-lg')}
      style={{ background: seqColor(score), color: dark ? '#fff' : '#1f1d1a' }}
    >
      {score}
      <span className="sr-only">%</span>
    </span>
  )
}

function MiniBars({ criteria }: { criteria: TopItem['criteria'] }) {
  const { t } = useTranslation()
  const rows = Object.entries(criteria)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
    .slice(0, 4)
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
      {rows.map(([k, v]) => (
        <li key={k} className="flex items-center gap-1.5 text-xs" title={`${t(`criteria.${k}`)}: ${v}`}>
          <span aria-hidden>{CRITERION_EMOJI[k as keyof typeof CRITERION_EMOJI]}</span>
          <span className="sr-only">{t(`criteria.${k}`)}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${v}%` }} />
          </span>
          <span className="w-6 text-right tabular-nums text-ink-3">{v}</span>
        </li>
      ))}
    </ul>
  )
}

export function PlaceCard({ p }: { p: TopItem }) {
  const { t } = useTranslation()
  const { city, lang, anchors, sel, select, set, compare, toggleCompare, hover } = useApp()
  const arch = p.archetype ? archetypeInfo(p.archetype.id, lang, p.archetype.label) : null
  const active = sel === p.id
  const inCompare = compare.includes(p.id)
  return (
    <li
      className={cn(
        'group relative rounded-2xl border bg-surface p-3 transition-shadow',
        active ? 'border-ink shadow-[var(--shadow-pop)]' : hover === p.id ? 'border-accent' : 'border-line',
      )}
      onMouseEnter={() => p.kind === 'hex' && set({ hover: p.id })}
      onMouseLeave={() => set({ hover: null })}
      data-testid="place-card"
    >
      <button className="absolute inset-0 rounded-2xl" onClick={() => select(p.kind === 'hex' ? p.id : latLngToCell(p.centroid.lat, p.centroid.lon, 9))} aria-label={t('results.openDetail', { name: p.name })} />
      <div className="pointer-events-none relative flex gap-3">
        <ScoreBadge score={p.score} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-semibold text-ink-3">{p.rank}.</span>
            <h3 className="truncate font-semibold">{p.name}</h3>
          </div>
          <p className="truncate text-xs text-ink-3">
            {p.kind === 'hex' ? p.district?.name : p.sharePassing != null ? t('results.sharePassing', { pct: Math.round(p.sharePassing * 100) }) : ''}
          </p>
          {arch && (
            <span className="mt-1 inline-flex items-center gap-1.5 text-xs text-ink-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORICAL[arch.color] }} />
              {arch.label}
            </span>
          )}
        </div>
      </div>
      <div className="pointer-events-none relative mt-3">
        <MiniBars criteria={p.criteria} />
      </div>
      {(p.highlights.length > 0 || p.warnings.length > 0) && (
        <ul className="pointer-events-none relative mt-3 space-y-1 text-sm">
          {p.highlights.slice(0, 2).map((h, i) => (
            <li key={i} className="flex gap-1.5">
              <Check size={16} className="mt-0.5 shrink-0 text-good" aria-label={t('results.highlights')} />
              <span>{h.text}</span>
            </li>
          ))}
          {p.warnings.slice(0, 1).map((h, i) => (
            <li key={i} className="flex gap-1.5 text-ink-2">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" aria-label={t('results.warning')} />
              <span>{h.text}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="relative mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-2">
        {p.anchors.map((a) => {
          const an = anchors.find((x) => x.id === a.id)
          return (
            <span key={a.id} className="pointer-events-none">
              🧭 {an?.label ?? a.id}: <b className="tabular-nums">{a.minutes != null ? t('map.minutes', { count: a.minutes }) : '–'}</b>
            </span>
          )
        })}
        {p.price?.value != null && city && <span className="pointer-events-none">💰 {fmtPricePerM2(p.price.value, lang, city)}</span>}
        {p.budgetM2 != null && <span className="pointer-events-none font-medium text-accent">{t('results.budgetM2', { m2: p.budgetM2 })}</span>}
        {p.kind === 'hex' && (
          <label className="relative z-10 ml-auto inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full px-2 hover:bg-sunken">
            <input type="checkbox" checked={inCompare} onChange={() => toggleCompare(p.id)} className="h-4 w-4 accent-[var(--color-accent)]" data-testid="compare-toggle" />
            {t('results.compare')}
          </label>
        )}
      </div>
    </li>
  )
}

export function RankingPanel() {
  const { t } = useTranslation()
  const { tab, set, setFilters, filters, anchors, setAnchors } = useApp()
  const places = useScore('hex')
  const districts = useScore('district', tab === 'districts')
  const q = tab === 'districts' ? districts : places
  const data = q.data

  const relax = (filter: string) => {
    if (filter === 'price') setFilters({ maxPricePerM2: null, maxRentPerM2: null })
    else if (filter === 'noise') setFilters({ maxNoiseDb: null })
    else if (filter.startsWith('must:')) setFilters({ mustHave: filters.mustHave.filter((m) => `must:${m.category}` !== filter) })
    else if (filter.startsWith('anchor:')) setAnchors(anchors.map((a) => (`anchor:${a.id}` === filter ? { ...a, maxMinutes: null } : a)))
  }
  const relaxName = (filter: string) => {
    if (filter === 'price') return t('criteria.price')
    if (filter === 'noise') return t('places.maxNoise')
    if (filter.startsWith('must:')) return t(`places.categories.${filter.slice(5)}`)
    if (filter.startsWith('anchor:')) return anchors.find((a) => `anchor:${a.id}` === filter)?.label ?? filter
    return filter
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pb-2 pt-3">
        <Tabs value={tab} onValueChange={(v) => set({ tab: v as 'places' | 'districts' })}>
          <TabsList>
            <TabsTrigger value="places">{t('results.tabs.places')}</TabsTrigger>
            <TabsTrigger value="districts" data-testid="tab-districts">
              {t('results.tabs.districts')}
            </TabsTrigger>
          </TabsList>
        </Tabs>
        {q.isFetching && <RefreshCw size={16} className="animate-spin text-ink-3" aria-label={t('states.loading')} />}
      </div>
      {data && (
        <p className="px-4 pb-2 text-xs text-ink-3" aria-live="polite">
          {t('results.passing', { count: data.count.passing })} · {t('results.computed', { ms: data.computeMs })}
        </p>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {q.isPending && (
          <div className="space-y-3 pt-1" aria-busy="true" aria-label={t('results.loading')}>
            <p className="px-1 text-sm text-ink-3">{t('results.loading')}</p>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-40 animate-pulse rounded-2xl bg-sunken" />
            ))}
          </div>
        )}
        {q.isError && !data && (
          <div className="rounded-2xl border border-line p-4 text-center" role="alert">
            <p className="mb-3 text-sm">{t('results.error')}</p>
            <Button variant="secondary" size="sm" onClick={() => q.refetch()}>
              {t('results.retry')}
            </Button>
          </div>
        )}
        {data && data.top.length === 0 && (
          <div className="rounded-2xl border border-dashed border-line-strong p-4 text-sm" role="status">
            <p className="font-medium">{tab === 'districts' ? t('results.noDistricts') : t('results.empty')}</p>
            {data.relaxHint && (
              <>
                <p className="mt-2 text-ink-2">
                  {t('results.relax', { filter: relaxName(data.relaxHint.filter), places: t('units.places', { count: data.relaxHint.gain ?? 0 }) })}
                </p>
                <Button className="mt-3" size="sm" variant="secondary" onClick={() => relax(data.relaxHint!.filter)}>
                  {t('results.relaxAction')}
                </Button>
              </>
            )}
          </div>
        )}
        {data && data.top.length > 0 && (
          <ol className="space-y-3" aria-label={t(`results.tabs.${tab}`)}>
            {data.top.map((p) => (
              <PlaceCard key={p.id} p={p} />
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

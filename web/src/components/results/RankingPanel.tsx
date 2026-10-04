import { AlertTriangle, Bookmark, BookmarkCheck, Check, RefreshCw, Trash2, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { type Lens, noEffectiveWeights, useLens, useRanking } from '@/api/hooks'
import type { CityId, CriterionId, RankedPlace } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CRITERION_EMOJI } from '@/content/defaults'
import { archetypeInfo, fmtPricePerM2 } from '@/lib/format'
import { CATEGORICAL, COMMUTE, commuteColor, seqColor, seqIndex } from '@/lib/palette'
import { cn } from '@/lib/utils'
import { type SavedItem, useIsSaved, useSaved } from '@/state/saved'
import { useApp } from '@/state/store'
import { ExpatTwins } from './ExpatTwins'

export function SaveButton({ item, className }: { item: Omit<SavedItem, 'savedAt' | 'city'> & { city: CityId | null }; className?: string }) {
  const { t } = useTranslation()
  const saved = useIsSaved(item.city, item.id)
  const toggle = useSaved((s) => s.toggle)
  const label = saved ? t('saved.saved') : t('saved.save')
  const Icon = saved ? BookmarkCheck : Bookmark
  return (
    <button
      type="button"
      aria-pressed={saved}
      title={label}
      aria-label={label}
      disabled={!item.city}
      onClick={() => item.city && toggle({ ...item, city: item.city })}
      className={cn('relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full hover:bg-sunken', saved ? 'text-accent' : 'text-ink-2', className)}
      data-testid="save-toggle"
    >
      <Icon size={18} fill={saved ? 'currentColor' : 'none'} />
    </button>
  )
}

function SavedList() {
  const { t } = useTranslation()
  const { city, select, sel, selectDistrict, selDistrict } = useApp()
  const all = useSaved((s) => s.items)
  const remove = useSaved((s) => s.remove)
  const items = all.filter((x) => x.city === city).sort((a, b) => b.savedAt - a.savedAt)
  if (!items.length)
    return (
      <div className="rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2" role="status" data-testid="saved-empty">
        {t('saved.empty')}
      </div>
    )
  return (
    <ul className="space-y-2" aria-label={t('saved.tab')} data-testid="saved-list">
      {items.map((x) => {
        const hex = x.kind === 'hex'
        return (
          <li key={x.id} className={cn('flex items-center gap-2 rounded-2xl border bg-surface p-2 pl-3', (hex ? sel : selDistrict) === x.id ? 'border-ink' : 'border-line')}>
            <Bookmark size={16} className="shrink-0 text-accent" fill="currentColor" aria-hidden />
            <button className="min-w-0 flex-1 py-1 text-left" onClick={() => (hex ? select(x.id) : selectDistrict(x.id))} aria-label={t('saved.open', { name: x.name })}>
              <span className="block truncate font-medium">{x.name}</span>
              {x.kind === 'district' && <span className="block text-xs text-ink-3">{t('saved.district')}</span>}
            </button>
            <button className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink" onClick={() => remove(x.city, x.id)} aria-label={t('saved.remove', { name: x.name })} title={t('saved.remove', { name: x.name })}>
              <Trash2 size={16} />
            </button>
          </li>
        )
      })}
    </ul>
  )
}

/** One number on its map colour, with a small caption saying what it is. */
function Badge({ value, caption, bg, dark, size = 'md', label }: { value: ReactNode; caption?: string; bg: string; dark: boolean; size?: 'md' | 'lg'; label: string }) {
  return (
    <span
      className={cn('flex shrink-0 flex-col items-center justify-center rounded-xl font-bold leading-none tabular-nums', size === 'lg' ? 'h-16 w-16 text-2xl' : 'h-12 w-12 text-lg')}
      style={{ background: bg, color: dark ? '#fff' : '#1f1d1a' }}
      title={label}
      data-testid="lens-badge"
      data-value={typeof value === 'number' ? value : undefined}
    >
      <span aria-hidden>{value}</span>
      {caption && (
        <span aria-hidden className={cn('mt-0.5 font-semibold opacity-80', size === 'lg' ? 'text-xs' : 'text-[10px]')}>
          {caption}
        </span>
      )}
      <span className="sr-only">{label}</span>
    </span>
  )
}

/** Match % badge; pass the map's `breaks` so it has the colour of the place's hexagon. */
export function ScoreBadge({ score, size = 'md', breaks }: { score: number; size?: 'md' | 'lg'; breaks?: number[] }) {
  const { t } = useTranslation()
  return <Badge value={score} caption="%" bg={seqColor(score, breaks)} dark={seqIndex(score, breaks) >= 4} size={size} label={t('results.matchPct', { pct: score })} />
}

/** The number the results are ordered by, coloured like the place on the map:
 *  match %, the lens criterion's score or the travel time to the lens place. */
export function LensBadge({ p, lens, size }: { p: RankedPlace; lens: Lens; size?: 'md' | 'lg' }) {
  const { t } = useTranslation()
  const rb = lens.rankBy
  if (rb?.startsWith('anchor:')) {
    const m = p.anchors.find((a) => `anchor:${a.id}` === rb)?.minutes ?? null
    const bg = commuteColor(m)
    return <Badge value={m ?? '–'} caption="min" bg={bg} dark={COMMUTE.indexOf(bg) <= 1} size={size} label={m != null ? t('map.minutes', { count: m }) : t('map.over60')} />
  }
  const v = rb ? p.criteria[rb] : undefined
  if (rb && v != null)
    return (
      <Badge
        value={v}
        caption={CRITERION_EMOJI[rb as CriterionId]}
        bg={seqColor(v, lens.breaks)}
        dark={seqIndex(v, lens.breaks) >= 4}
        size={size}
        label={t('mapUi.hover.criterion', { criterion: t(`criteria.${rb}`), value: v })}
      />
    )
  return <ScoreBadge score={p.score} size={size} breaks={lens.breaks} />
}

/** The four strongest criteria; `focus` (the one the map shows) always comes first and stands out. */
function MiniBars({ criteria, focus }: { criteria: RankedPlace['criteria']; focus?: string | null }) {
  const { t } = useTranslation()
  const rows = Object.entries(criteria)
    .sort((a, b) => Number(b[0] === focus) - Number(a[0] === focus) || (b[1] ?? 0) - (a[1] ?? 0))
    .slice(0, 4)
  const lens = !!focus && focus in criteria
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
      {rows.map(([k, v]) => (
        <li key={k} className={cn('flex items-center gap-1.5 text-xs', lens && (k === focus ? 'font-semibold' : 'opacity-55'))} title={`${t(`criteria.${k}`)}: ${v}`}>
          <span aria-hidden>{CRITERION_EMOJI[k as keyof typeof CRITERION_EMOJI]}</span>
          <span className="sr-only">{t(`criteria.${k}`)}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${v}%` }} />
          </span>
          <span className={cn('w-6 text-right tabular-nums', lens && k === focus ? 'text-accent' : 'text-ink-3')}>{v}</span>
        </li>
      ))}
    </ul>
  )
}

/** A ranked place or district. `showMatch`: the lens is not match %, so the match % goes under the name. */
export function PlaceCard({ p, lens, showMatch }: { p: RankedPlace; lens: Lens; showMatch: boolean }) {
  const { t } = useTranslation()
  const { city, lang, anchors, sel, selDistrict, select, selectDistrict, set, compare, toggleCompare, hover, hoverDistrict } = useApp()
  const hex = p.kind === 'hex'
  const arch = p.archetype ? archetypeInfo(p.archetype.id, lang) : null
  const lensAnchorId = lens.rankBy?.startsWith('anchor:') ? lens.rankBy.slice('anchor:'.length) : null
  const active = hex ? sel === p.id : selDistrict === p.id
  const hovered = hex ? hover === p.id : hoverDistrict === p.id
  const inCompare = compare.includes(p.id)
  const sub = [
    hex ? p.district?.name : t('saved.district'),
    !hex && p.sharePassing != null && p.sharePassing < 1 ? t('results.sharePassing', { pct: Math.round(p.sharePassing * 100) }) : null,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <li
      className={cn(
        'group relative rounded-2xl border bg-surface p-3 transition-shadow',
        active ? 'border-ink shadow-[var(--shadow-pop)]' : hovered ? 'border-accent' : 'border-line',
      )}
      onMouseEnter={() => set(hex ? { hover: p.id } : { hoverDistrict: p.id })}
      onMouseLeave={() => set({ hover: null, hoverDistrict: null })}
      data-testid="place-card"
    >
      <button className="absolute inset-0 rounded-2xl" onClick={() => (hex ? select(p.id) : selectDistrict(p.id))} aria-label={t('results.openDetail', { name: p.name })} />
      <div className="pointer-events-none relative flex gap-3">
        <LensBadge p={p} lens={lens} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-semibold text-ink-3">{p.rank}.</span>
            <h3 className="truncate font-semibold">{p.name}</h3>
            {showMatch && <span className="ml-auto shrink-0 text-xs font-medium tabular-nums text-ink-2">{t('results.matchPct', { pct: p.score })}</span>}
          </div>
          <p className="truncate text-xs text-ink-3">{sub}</p>
          {arch && (
            <span className="mt-1 inline-flex items-center gap-1.5 text-xs text-ink-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORICAL[arch.color] }} />
              {arch.label}
            </span>
          )}
        </div>
      </div>
      <div className="pointer-events-none relative mt-3">
        <MiniBars criteria={p.criteria} focus={lensAnchorId ? null : lens.rankBy} />
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
            <span key={a.id} className={cn('pointer-events-none', a.id === lensAnchorId && 'font-semibold text-accent')}>
              🧭 {an?.label ?? a.label ?? a.id}: <b className="tabular-nums">{a.minutes != null ? t('map.minutes', { count: a.minutes }) : '–'}</b>
            </span>
          )
        })}
        {p.price?.value != null && city && <span className="pointer-events-none">💰 {fmtPricePerM2(p.price.value, lang, city)}</span>}
        {p.budgetM2 != null && <span className="pointer-events-none font-medium text-accent">{p.budgetText ?? t('results.budgetM2', { m2: p.budgetM2 })}</span>}
        <span className="relative z-10 ml-auto flex items-center gap-1">
          {hex && (
            <label className="relative z-10 inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full px-2 hover:bg-sunken">
              <input type="checkbox" checked={inCompare} onChange={() => toggleCompare(p.id)} className="h-4 w-4 accent-[var(--color-accent)]" data-testid="compare-toggle" />
              {t('results.compare')}
            </label>
          )}
          <SaveButton item={{ city, id: p.id, kind: hex ? 'hex' : 'district', name: p.name, lat: p.centroid.lat, lon: p.centroid.lon }} />
        </span>
      </div>
    </li>
  )
}

/** "Sorted by" follows the map lens; the chip's × switches the map back to match %. */
function SortedBy({ rankBy }: { rankBy: string | null }) {
  const { t } = useTranslation()
  const { set, anchors } = useApp()
  const anchorId = rankBy?.startsWith('anchor:') ? rankBy.slice('anchor:'.length) : null
  const label = !rankBy
    ? null
    : anchorId
      ? `🧭 ${t('results.sortCommute', { place: anchors.find((a) => a.id === anchorId)?.label || t('map.legend.anchor') })}`
      : `${CRITERION_EMOJI[rankBy as CriterionId] ?? ''} ${t(`criteria.${rankBy}`)}`
  return (
    <div className="flex min-h-7 min-w-0 items-center gap-1.5 text-xs" data-testid="sorted-by">
      <span className="shrink-0 text-ink-3">{t('results.sortedBy')}</span>
      {label ? (
        <span className="inline-flex h-7 min-w-0 items-center gap-0.5 rounded-full bg-accent-soft pl-2.5 pr-0.5 font-semibold text-accent-strong">
          <span className="truncate">{label}</span>
          <button
            onClick={() => set({ mapMode: 'match' })}
            aria-label={t('results.sortReset')}
            title={t('results.sortReset')}
            className="grid h-6 w-6 shrink-0 place-items-center rounded-full hover:bg-ink/5"
            data-testid="sort-reset"
          >
            <X size={14} />
          </button>
        </span>
      ) : (
        <span className="font-semibold text-ink-2">{t('results.sortMatch')}</span>
      )}
    </div>
  )
}

export function RankingPanel() {
  const { t } = useTranslation()
  const { tab, set, setFilters, filters, anchors, setAnchors, city, persona } = useApp()
  const [showSaved, setShowSaved] = useState(false)
  const savedCount = useSaved((s) => s.items.filter((x) => x.city === city).length)
  const lens = useLens()
  const places = useRanking('hex')
  const districts = useRanking('district', tab === 'districts')
  const q = tab === 'districts' ? districts : places
  const data = q.data
  const unrated = noEffectiveWeights(data)
  // Nothing rated means no match ranking; a lens (one criterion, a commute) still orders the places.
  const neutral = unrated && !lens.rankBy

  const relax = (filter: string) => {
    if (filter === 'price') setFilters({ maxPricePerM2: null, maxRentPerM2: null })
    else if (filter === 'noise') setFilters({ maxNoiseDb: null })
    else if (filter.startsWith('mustHave:')) setFilters({ mustHave: filters.mustHave.filter((m) => `mustHave:${m.category}` !== filter) })
    else if (filter.startsWith('commute:')) setAnchors(anchors.map((a) => (`commute:${a.id}` === filter ? { ...a, maxMinutes: null } : a)))
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pb-2 pt-3">
        <Tabs
          value={showSaved ? 'saved' : tab}
          onValueChange={(v) => {
            setShowSaved(v === 'saved')
            if (v !== 'saved') set({ tab: v as 'places' | 'districts' })
          }}
        >
          <TabsList>
            <TabsTrigger value="places">{t('results.tabs.places')}</TabsTrigger>
            <TabsTrigger value="districts" data-testid="tab-districts">
              {t('results.tabs.districts')}
            </TabsTrigger>
            <TabsTrigger value="saved" data-testid="tab-saved">
              {t('saved.tab')}
              {savedCount > 0 && <span className="ml-1 tabular-nums text-ink-3">{savedCount}</span>}
            </TabsTrigger>
          </TabsList>
        </Tabs>
        {!showSaved && q.isFetching && <RefreshCw size={16} className="animate-spin text-ink-3" aria-label={t('states.loading')} />}
      </div>
      {data && !showSaved && (
        <div className="px-4 pb-2">
          <SortedBy rankBy={lens.rankBy} />
          <p className="mt-0.5 text-xs text-ink-3" aria-live="polite">
            {t('results.passing', { count: data.count.passing })} · {t('results.computed', { ms: data.computeMs })}
          </p>
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {showSaved ? (
          <SavedList />
        ) : (
          <>
            {persona === 'expat' && city && <ExpatTwins city={city} />}
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
            {data && neutral && (
              <div className="rounded-2xl border border-dashed border-line-strong p-4 text-sm" role="status" data-testid="no-prefs">
                <p className="font-medium">{t('results.noPrefs.title')}</p>
                <p className="mt-2 text-ink-2">{t('results.noPrefs.body')}</p>
                <Button className="mt-3" size="sm" variant="secondary" onClick={() => set({ prefsOpen: true, prefsSection: 'criteria' })}>
                  {t('results.noPrefs.action')}
                </Button>
              </div>
            )}
            {data && !neutral && data.top.length === 0 && (
              <div className="rounded-2xl border border-dashed border-line-strong p-4 text-sm" role="status">
                <p className="font-medium">{tab === 'districts' ? t('results.noDistricts') : t('results.empty')}</p>
                {data.relaxHint && (
                  <>
                    <p className="mt-2 text-ink-2">{data.relaxHint.text}</p>
                    <Button className="mt-3" size="sm" variant="secondary" onClick={() => relax(data.relaxHint!.filter)}>
                      {t('results.relaxAction')}
                    </Button>
                  </>
                )}
              </div>
            )}
            {data && !neutral && data.top.length > 0 && (
              <ol className="space-y-3" aria-label={t(`results.tabs.${tab}`)}>
                {data.top.map((p) => (
                  <PlaceCard key={p.id} p={p} lens={lens} showMatch={!!lens.rankBy && !unrated} />
                ))}
              </ol>
            )}
          </>
        )}
      </div>
    </div>
  )
}

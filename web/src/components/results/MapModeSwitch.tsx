import { ChevronDown, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import type { CriterionId, Mode } from '@/api/types'
import { AddPlaceForm, MODE_ICON } from '@/components/onboarding/PlacesStep'
import { DEFAULT_CRITERIA } from '@/content/defaults'
import { STATIC_FALLBACK } from '@/lib/env'
import { cn } from '@/lib/utils'
import { activeAnchor, useApp, type MapMode } from '@/state/store'

/** Commute lens: add a place right here (name + address), or pick, remove and set how you travel. */
function CommuteRow() {
  const { t } = useTranslation()
  const { anchors, setAnchors, removeAnchor, commuteAnchor, set } = useApp()
  const [adding, setAdding] = useState(false)
  // Focus the form only with a mouse: on phones it would pop the keyboard over the map.
  const [canHover] = useState(() => window.matchMedia('(hover: hover)').matches)
  const active = activeAnchor({ anchors, commuteAnchor })

  if (!active || adding)
    return (
      <div className="border-t border-line px-3 pb-3 pt-2.5" data-testid="lens-commute" onKeyDown={(e) => e.key === 'Escape' && setAdding(false)}>
        <div className="mb-2 flex items-center gap-2">
          <p className="min-w-0 flex-1 text-sm font-medium">{active ? t('places.addAnchor') : t('map.commuteAsk')}</p>
          {active && (
            <button onClick={() => setAdding(false)} aria-label={t('nav.close')} title={t('nav.close')} className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink">
              <X size={16} />
            </button>
          )}
        </div>
        <AddPlaceForm
          autoFocus={canHover}
          testPrefix="commute"
          onAdded={(id) => {
            set({ commuteAnchor: id })
            setAdding(false)
          }}
        />
      </div>
    )

  return (
    <div className="flex items-start gap-2 border-t border-line px-3 py-2" data-testid="lens-commute">
      <span className="pt-1.5 text-xs font-medium text-ink-3">{t('map.commuteTo')}</span>
      <div role="group" aria-label={t('map.commuteTo')} className="flex min-w-0 flex-1 flex-wrap gap-1">
        {anchors.map((a) => {
          const on = a.id === active.id
          const name = a.label || t('map.legend.anchor')
          return (
            <span
              key={a.id}
              className={cn('inline-flex h-8 max-w-40 items-center rounded-full border pl-2.5', on ? 'border-accent bg-accent-soft text-accent-strong' : 'border-line text-ink-2 hover:bg-sunken')}
            >
              <button aria-pressed={on} onClick={() => set({ commuteAnchor: a.id })} title={a.address} className="min-w-0 truncate text-[13px] font-medium" data-testid="commute-anchor">
                {name}
              </button>
              <button
                onClick={() => removeAnchor(a.id)}
                aria-label={t('places.removeAnchor', { label: name })}
                title={t('places.removeAnchor', { label: name })}
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-ink/5 hover:text-ink"
                data-testid="commute-remove"
              >
                <X size={14} />
              </button>
            </span>
          )
        })}
        {anchors.length < 3 && (
          <button
            onClick={() => setAdding(true)}
            aria-label={t('places.addAnchor')}
            title={t('places.addAnchor')}
            className="grid h-8 w-8 place-items-center rounded-full border border-dashed border-line-strong text-ink-2 hover:bg-sunken hover:text-ink"
            data-testid="commute-add"
          >
            <Plus size={16} />
          </button>
        )}
      </div>
      <div role="radiogroup" aria-label={t('places.mode')} className="inline-flex shrink-0 rounded-full bg-sunken p-0.5">
        {(['transit', 'bike', 'walk'] as Mode[]).map((m) => {
          const Icon = MODE_ICON[m]
          return (
            <button
              key={m}
              role="radio"
              aria-checked={active.mode === m}
              aria-label={t(`places.modes.${m}`)}
              title={t(`places.modes.${m}`)}
              onClick={() => setAnchors(anchors.map((a) => (a.id === active.id ? { ...a, mode: m } : a)))}
              className={cn('grid h-7 w-8 place-items-center rounded-full text-ink-2 hover:text-ink', active.mode === m && 'bg-surface text-accent shadow-sm hover:text-accent')}
            >
              <Icon size={16} />
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Map lens: the mode switch and, in the same card, everything the active mode needs. */
export function MapModeSwitch() {
  const { t } = useTranslation()
  const { city, mapMode, set, weights } = useApp()
  const { data: meta } = useMeta(city)
  const critMode = mapMode !== 'match' && mapMode !== 'commute'
  const crits = (meta?.criteria?.length ? meta.criteria : DEFAULT_CRITERIA).filter((c) => c.coverage > 0 && c.id !== 'commute')
  const firstCrit = [...crits].sort((a, b) => (weights[b.id] ?? 0) - (weights[a.id] ?? 0))[0]?.id ?? 'transit'
  const opts: { id: 'match' | 'commute' | 'criterion'; label: string }[] = [
    { id: 'match', label: t('map.modes.match') },
    ...(STATIC_FALLBACK ? [] : [{ id: 'commute' as const, label: t('map.modes.commute') }]),
    { id: 'criterion', label: t('map.modes.criterion') },
  ]
  const pick = (id: string) => set({ mapMode: (id === 'criterion' ? (critMode ? mapMode : firstCrit) : id) as MapMode })

  return (
    // Fixed width so switching never resizes or wraps the card; z-30 keeps the search list above the mobile sheet.
    <div className="pointer-events-auto absolute left-3 top-3 z-30 w-90 max-w-[calc(100%-4.5rem)] rounded-[22px] border border-line bg-surface shadow-[var(--shadow-card)]" data-testid="map-lens">
      <div role="radiogroup" aria-label={t('map.modes.label')} className="flex p-1">
        {opts.map((o) => {
          const active = o.id === 'criterion' ? critMode : mapMode === o.id
          return (
            <button
              key={o.id}
              role="radio"
              aria-checked={active}
              data-testid={`mode-${o.id}`}
              onClick={() => pick(o.id)}
              className={cn('min-h-9 flex-1 whitespace-nowrap rounded-full px-2 text-[13px] font-medium text-ink-2 hover:bg-sunken sm:text-sm', active && 'bg-accent text-accent-ink hover:bg-accent')}
            >
              {o.label}
            </button>
          )
        })}
      </div>
      {mapMode === 'commute' && <CommuteRow />}
      {critMode && (
        <div className="relative border-t border-line px-3 py-2">
          <select
            className="h-9 w-full appearance-none rounded-full bg-sunken pl-3 pr-9 text-sm font-medium text-ink hover:bg-line"
            value={mapMode}
            onChange={(e) => set({ mapMode: e.target.value as CriterionId })}
            aria-label={t('map.modes.criterion')}
            data-testid="criterion-select"
          >
            {crits.map((c) => (
              <option key={c.id} value={c.id}>
                {c.emoji} {t(`criteria.${c.id}`)}
              </option>
            ))}
          </select>
          <ChevronDown size={16} className="pointer-events-none absolute right-6 top-1/2 -translate-y-1/2 text-ink-3" />
        </div>
      )}
    </div>
  )
}

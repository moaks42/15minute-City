import { useTranslation } from 'react-i18next'
import { CRITERIA, type CriterionId } from '@/api/types'
import { STATIC_FALLBACK } from '@/lib/env'
import { cn } from '@/lib/utils'
import { useApp, type MapMode } from '@/state/store'

export function MapModeSwitch() {
  const { t } = useTranslation()
  const { mapMode, set, anchors, commuteAnchor, weights } = useApp()
  const critMode = mapMode !== 'match' && mapMode !== 'commute'
  const firstCrit = CRITERIA.filter((c) => c !== 'commute').sort((a, b) => (weights[b] ?? 0) - (weights[a] ?? 0))[0]
  const opts: { id: 'match' | 'commute' | 'criterion'; label: string }[] = [
    { id: 'match', label: t('map.modes.match') },
    ...(STATIC_FALLBACK ? [] : [{ id: 'commute' as const, label: t('map.modes.commute') }]),
    { id: 'criterion', label: t('map.modes.criterion') },
  ]
  const pick = (id: string) => set({ mapMode: (id === 'criterion' ? firstCrit : id) as MapMode })
  const sel = 'h-9 rounded-full border border-line bg-surface px-3 text-sm shadow-sm'
  return (
    <div className="pointer-events-auto absolute left-3 top-3 z-10 flex max-w-[calc(100%-4.5rem)] flex-wrap items-center gap-2">
      <div role="radiogroup" aria-label={t('map.modes.label')} className="inline-flex rounded-full border border-line bg-surface p-1 shadow-sm">
        {opts.map((o) => {
          const active = o.id === 'criterion' ? critMode : mapMode === o.id
          return (
            <button
              key={o.id}
              role="radio"
              aria-checked={active}
              data-testid={`mode-${o.id}`}
              onClick={() => pick(o.id)}
              className={cn('min-h-9 whitespace-nowrap rounded-full px-2.5 text-[13px] font-medium text-ink-2 sm:px-3 sm:text-sm', active && 'bg-accent text-accent-ink')}
            >
              {o.label}
            </button>
          )
        })}
      </div>
      {critMode && (
        <select className={sel} value={mapMode} onChange={(e) => set({ mapMode: e.target.value as CriterionId })} aria-label={t('map.modes.criterion')}>
          {CRITERIA.filter((c) => c !== 'commute').map((c) => (
            <option key={c} value={c}>
              {t(`criteria.${c}`)}
            </option>
          ))}
        </select>
      )}
      {mapMode === 'commute' && anchors.length > 1 && (
        <select className={sel} value={commuteAnchor ?? anchors[0].id} onChange={(e) => set({ commuteAnchor: e.target.value })} aria-label={t('map.commuteFrom')}>
          {anchors.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label}
            </option>
          ))}
        </select>
      )}
      {mapMode === 'commute' && anchors.length === 0 && (
        <button onClick={() => set({ step: 'places' })} className="rounded-full bg-ink px-3 py-2 text-xs font-medium text-white shadow">
          {t('map.commuteNoAnchor')}
        </button>
      )}
    </div>
  )
}

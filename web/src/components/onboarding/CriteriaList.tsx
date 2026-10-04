import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import { DEFAULT_CRITERIA, type CriterionLite } from '@/content/defaults'
import { useApp } from '@/state/store'
import { EmojiRow } from './EmojiRow'

export function CriteriaList({ compact }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { city, weights, setLevel, mapMode, anchors } = useApp()
  const { data: meta } = useMeta(city)
  const criteria: CriterionLite[] = (meta?.criteria?.length ? meta.criteria : DEFAULT_CRITERIA).filter((c) => c.coverage > 0)
  const ref = useRef<HTMLDivElement>(null)
  // In the results panel, keep the row the map shows in view when the lens changes.
  useEffect(() => {
    if (compact) ref.current?.querySelector<HTMLElement>('[data-focus]')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [compact, mapMode])
  // Match % is a weighted average, so only the differences between levels
  // change the ranking: all 😐 ranks exactly like all 🤩. Say so.
  const rated = criteria.filter((c) => (weights[c.id] ?? 0) > 0 && (c.id !== 'commute' || anchors.length > 0))
  const note = rated.length === 0 ? t('criteria.noneHint') : rated.length > 1 && new Set(rated.map((c) => weights[c.id])).size === 1 ? t('criteria.equalHint') : null
  return (
    <div ref={ref}>
      {note && (
        <p className="mt-2 rounded-xl bg-sunken px-3 py-2 text-sm leading-snug text-ink-2" role="status" data-testid="criteria-note">
          {note}
        </p>
      )}
      {criteria.map((c) => (
        <EmojiRow key={c.id} criterion={c} value={weights[c.id] ?? 0} onChange={setLevel} compact={compact} onMap={compact && mapMode === c.id} />
      ))}
    </div>
  )
}

import { useEffect, useRef } from 'react'
import { useMeta } from '@/api/hooks'
import { DEFAULT_CRITERIA, type CriterionLite } from '@/content/defaults'
import { useApp } from '@/state/store'
import { EmojiRow } from './EmojiRow'

export function CriteriaList({ compact }: { compact?: boolean }) {
  const { city, weights, setLevel, mapMode } = useApp()
  const { data: meta } = useMeta(city)
  const criteria: CriterionLite[] = (meta?.criteria?.length ? meta.criteria : DEFAULT_CRITERIA).filter((c) => c.coverage > 0)
  const ref = useRef<HTMLDivElement>(null)
  // In the results panel, keep the row the map shows in view when the lens changes.
  useEffect(() => {
    if (compact) ref.current?.querySelector<HTMLElement>('[data-focus]')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [compact, mapMode])
  return (
    <div ref={ref}>
      {criteria.map((c) => (
        <EmojiRow key={c.id} criterion={c} value={weights[c.id] ?? 0} onChange={setLevel} compact={compact} onMap={compact && mapMode === c.id} />
      ))}
    </div>
  )
}

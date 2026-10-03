import { useMeta } from '@/api/hooks'
import { DEFAULT_CRITERIA, type CriterionLite } from '@/content/defaults'
import { useApp } from '@/state/store'
import { EmojiRow } from './EmojiRow'

export function CriteriaList({ compact }: { compact?: boolean }) {
  const { city, weights, setLevel } = useApp()
  const { data: meta } = useMeta(city)
  const criteria: CriterionLite[] = (meta?.criteria?.length ? meta.criteria : DEFAULT_CRITERIA).filter((c) => c.coverage > 0)
  return (
    <div>
      {criteria.map((c) => (
        <EmojiRow key={c.id} criterion={c} value={weights[c.id] ?? 0} onChange={setLevel} compact={compact} />
      ))}
    </div>
  )
}

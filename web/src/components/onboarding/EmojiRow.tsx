import { Map as MapIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { CriterionId } from '@/api/types'
import type { CriterionLite } from '@/content/defaults'
import { Tip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { LEVEL_EMOJI } from './icons'

/** One criterion row: native radio group (arrow keys work), 5 emoji + skip. */
export function EmojiRow({
  criterion,
  value,
  onChange,
  compact,
  onMap,
}: {
  criterion: CriterionLite
  value: number
  onChange: (id: CriterionId, level: number) => void
  compact?: boolean
  /** The map currently shows this criterion (results panel only). */
  onMap?: boolean
}) {
  const { t } = useTranslation()
  const name = t(`criteria.${criterion.id}`)
  const beta = criterion.beta || (criterion.coverage > 0 && criterion.coverage < 0.6)
  return (
    <fieldset
      className={cn('flex flex-col gap-2 border-b border-line py-3 last:border-0', compact ? 'gap-1 py-2' : 'sm:flex-row sm:items-center', onMap && '-mx-2 rounded-xl bg-accent-soft px-2')}
      data-testid={`criterion-${criterion.id}`}
      data-focus={onMap || undefined}
    >
      <legend className="sr-only">{t('levels.groupLabel', { criterion: name })}</legend>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="text-2xl" aria-hidden>
          {criterion.emoji}
        </span>
        <div className="min-w-0">
          <div className={cn('font-medium leading-tight', compact && 'text-sm')}>
            {name}
            {beta && (
              <Tip content={t('criteria.betaHint')}>
                <span tabIndex={0} className="ml-2 rounded bg-sunken px-1.5 py-0.5 align-middle text-[11px] font-semibold uppercase text-ink-3">
                  {t('criteria.beta')}
                </span>
              </Tip>
            )}
            {onMap && (
              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-accent px-1.5 py-0.5 align-middle text-[11px] font-semibold text-accent-ink" data-testid="on-map">
                <MapIcon size={11} aria-hidden /> {t('map.onMap')}
              </span>
            )}
          </div>
          {!compact && <div className="mt-0.5 text-sm leading-snug text-ink-3">{t(`criteria.hint.${criterion.id}`)}</div>}
        </div>
      </div>
      <div className={cn('flex shrink-0 items-center gap-1', compact && 'justify-between pl-9')}>
        {[0, 1, 2, 3, 4, 5].map((lvl) => {
          const checked = value === lvl
          const label = t(`levels.${lvl}`)
          return (
            <Tip key={lvl} content={label}>
              <label
                className={cn(
                  'relative grid cursor-pointer place-items-center rounded-full border-2 transition-all has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-accent',
                  compact ? 'h-9 w-9 text-lg' : 'h-11 w-11 text-2xl',
                  checked ? cn('scale-110 border-accent', onMap ? 'bg-surface' : 'bg-accent-soft') : 'border-transparent hover:bg-sunken',
                  lvl === 0 && 'text-xs font-semibold text-ink-3',
                  lvl > 0 && !checked && 'grayscale-[.6] opacity-70 hover:grayscale-0 hover:opacity-100',
                )}
              >
                <input
                  type="radio"
                  className="sr-only"
                  name={`lvl-${criterion.id}`}
                  value={lvl}
                  checked={checked}
                  onChange={() => onChange(criterion.id, lvl)}
                  aria-label={`${name}: ${label}`}
                />
                {lvl === 0 ? '–' : <span aria-hidden>{LEVEL_EMOJI[lvl]}</span>}
              </label>
            </Tip>
          )
        })}
      </div>
    </fieldset>
  )
}

import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import { DEFAULT_PERSONAS } from '@/content/defaults'
import { cn } from '@/lib/utils'
import { useApp } from '@/state/store'

export function PersonaStep({ onPicked }: { onPicked: () => void }) {
  const { t } = useTranslation()
  const { city, persona, pickPersona } = useApp()
  const { data: meta } = useMeta(city)
  const personas = meta?.personas?.length ? meta.personas : DEFAULT_PERSONAS
  return (
    <div role="radiogroup" aria-label={t('steps.persona.title')} className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {personas.map((p) => {
        const active = persona === p.id
        return (
          <button
            key={p.id}
            role="radio"
            aria-checked={active}
            data-testid={`persona-${p.id}`}
            onClick={() => {
              pickPersona(p.id, p.weights)
              onPicked()
            }}
            className={cn(
              'flex min-h-36 flex-col items-start rounded-2xl border-2 bg-surface p-4 text-left transition-colors hover:border-accent/60',
              active ? 'border-accent bg-accent-soft' : 'border-line',
            )}
          >
            <span className="text-4xl" aria-hidden>
              {p.emoji}
            </span>
            <span className="mt-2 font-semibold">{t(`personas.${p.id}`, { defaultValue: p.id })}</span>
            <span className="mt-1 text-sm leading-snug text-ink-3">{t(`personas.desc.${p.id}`, { defaultValue: '' })}</span>
          </button>
        )
      })}
    </div>
  )
}

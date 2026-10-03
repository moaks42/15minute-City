import { Bike, Footprints, Plus, TramFront, Trash2 } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import type { Anchor, GeocodeHit, Mode } from '@/api/types'
import { GeoSearch } from '@/components/common/GeoSearch'
import { Button } from '@/components/ui/button'
import { MUST_HAVE } from '@/content/defaults'
import { CURRENCY } from '@/lib/format'
import { L, cn } from '@/lib/utils'
import { useApp } from '@/state/store'
import { LEVEL_EMOJI } from './EmojiRow'

const MODE_ICON: Record<Mode, typeof TramFront> = { transit: TramFront, bike: Bike, walk: Footprints }
const inputCls = 'h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] placeholder:text-ink-3 focus:border-accent focus:outline-none focus-visible:outline-3 focus-visible:outline-accent'

function AnchorRow({ a, onChange, onRemove }: { a: Anchor; onChange: (a: Anchor) => void; onRemove: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-2xl border border-line bg-surface p-3" data-testid="anchor-row">
      <div className="flex items-center gap-2">
        <input className={inputCls} value={a.label} aria-label={t('places.labelPlaceholder')} placeholder={t('places.labelPlaceholder')} onChange={(e) => onChange({ ...a, label: e.target.value })} />
        <Button variant="ghost" size="icon" onClick={onRemove} aria-label={t('places.removeAnchor', { label: a.label })}>
          <Trash2 size={18} />
        </Button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="radiogroup" aria-label={t('places.mode')} className="inline-flex rounded-full bg-sunken p-1">
          {(['transit', 'bike', 'walk'] as Mode[]).map((m) => {
            const Icon = MODE_ICON[m]
            return (
              <button
                key={m}
                role="radio"
                aria-checked={a.mode === m}
                aria-label={t(`places.modes.${m}`)}
                title={t(`places.modes.${m}`)}
                onClick={() => onChange({ ...a, mode: m })}
                className={cn('grid h-9 w-11 place-items-center rounded-full text-ink-2', a.mode === m && 'bg-surface text-accent shadow-sm')}
              >
                <Icon size={18} />
              </button>
            )
          })}
        </div>
        <div role="radiogroup" aria-label={t('places.importance')} className="flex items-center gap-0.5">
          {[1, 2, 3, 4, 5].map((l) => (
            <button
              key={l}
              role="radio"
              aria-checked={a.level === l}
              aria-label={t(`levels.${l}`)}
              title={t(`levels.${l}`)}
              onClick={() => onChange({ ...a, level: l })}
              className={cn('grid h-9 w-9 place-items-center rounded-full text-lg', a.level === l ? 'bg-accent-soft ring-2 ring-accent' : 'opacity-60 grayscale-[.6] hover:opacity-100')}
            >
              <span aria-hidden>{LEVEL_EMOJI[l]}</span>
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          {t('places.maxMinutes')}
          <select
            className="h-9 rounded-lg border border-line bg-surface px-2"
            value={a.maxMinutes ?? ''}
            onChange={(e) => onChange({ ...a, maxMinutes: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t('places.noLimit')}</option>
            {[15, 20, 30, 45, 60].map((m) => (
              <option key={m} value={m}>
                {t('map.minutes', { count: m })}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}

function NumberField({ label, value, onChange, suffix, hint, testId }: { label: string; value: number | null | undefined; onChange: (v: number | null) => void; suffix: string; hint?: string; testId?: string }) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-ink-2">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          data-testid={testId}
          type="number"
          inputMode="numeric"
          min={0}
          className={cn(inputCls, 'pr-24')}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        />
        <span className="pointer-events-none absolute right-3 top-2.5 text-sm text-ink-3">{suffix}</span>
      </div>
      {hint && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
    </div>
  )
}

/** `compact`: inside the narrow preferences panel (one column, tighter spacing). */
export function PlacesStep({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { city, lang, persona, anchors, setAnchors, filters, setFilters, budget, set } = useApp()
  const { data: meta } = useMeta(city)
  const isBuy = city === 'krakow'
  const cur = CURRENCY[city!]
  const curSym = cur === 'PLN' ? (lang === 'en' ? 'PLN' : 'zł') : lang === 'en' ? 'CZK' : 'Kč'
  const suggested = meta?.personas.find((p) => p.id === persona)?.suggestedAnchors?.[anchors.length]
  const categories = (meta?.mustHaveCategories?.length ? meta.mustHaveCategories.filter((c) => c.available) : MUST_HAVE.map((id) => ({ id, emoji: '', label: null }))).map((c) => ({
    id: c.id,
    label: `${c.emoji ? c.emoji + ' ' : ''}${c.label ? L(c.label, lang) : t(`places.categories.${c.id}`, { defaultValue: c.id })}`,
  }))
  const catLabel = (id: string) => categories.find((c) => c.id === id)?.label ?? t(`places.categories.${id}`, { defaultValue: id })
  const [mhCat, setMhCat] = useState(categories[0]?.id ?? 'park')

  const add = (h: GeocodeHit) => {
    const label = suggested ? L(suggested.label, lang) : h.label.split(',')[0]
    setAnchors([...anchors, { id: '', label, lat: h.lat, lon: h.lon, mode: suggested?.mode ?? 'transit', level: suggested?.level ?? 4, maxMinutes: null }])
  }

  return (
    <div className={compact ? 'space-y-5' : 'space-y-8'}>
      <section>
        <h3 className={cn('font-semibold', compact && 'text-sm')}>{t('places.anchors')}</h3>
        <p className="mb-3 text-sm text-ink-3">{t('places.anchorsHint')}</p>
        <div className="space-y-3">
          {anchors.map((a, i) => (
            <AnchorRow key={i} a={a} onChange={(n) => setAnchors(anchors.map((x, j) => (j === i ? n : x)))} onRemove={() => setAnchors(anchors.filter((_, j) => j !== i))} />
          ))}
          {anchors.length < 3 && (
            <div>
              {suggested && <p className="mb-1 text-xs font-medium text-accent">{t('places.suggested', { label: L(suggested.label, lang) })}</p>}
              <GeoSearch onPick={add} />
            </div>
          )}
        </div>
      </section>

      <section>
        <h3 className={cn('mb-3 font-semibold', compact && 'text-sm')}>{t('places.limits')}</h3>
        <div className={cn('grid', compact ? 'gap-3' : 'gap-4 sm:grid-cols-2')}>
          <NumberField
            testId="budget"
            label={t(isBuy ? 'places.budget.buy' : 'places.budget.rent')}
            hint={t('places.budget.hint')}
            value={budget}
            onChange={(v) => set({ budget: v })}
            suffix={isBuy ? curSym : `${curSym}/${lang === 'en' ? 'mo' : lang === 'pl' ? 'mies.' : 'měs.'}`}
          />
          <NumberField
            label={t(isBuy ? 'places.maxPrice.buy' : 'places.maxPrice.rent')}
            value={isBuy ? filters.maxPricePerM2 : filters.maxRentPerM2}
            onChange={(v) => setFilters(isBuy ? { maxPricePerM2: v } : { maxRentPerM2: v })}
            suffix={`${curSym}/m²`}
          />
          <NumberField label={t('places.maxNoise')} value={filters.maxNoiseDb} onChange={(v) => setFilters({ maxNoiseDb: v })} suffix="dB" />
        </div>

        <h4 className={cn('mb-2 text-sm font-medium text-ink-2', compact ? 'mt-4' : 'mt-6')}>{t('places.mustHave')}</h4>
        <ul className="mb-3 flex flex-wrap gap-2">
          {filters.mustHave.map((m, i) => (
            <li key={i} className="inline-flex items-center gap-1 rounded-full bg-accent-soft py-1 pl-3 pr-1 text-sm">
              {catLabel(m.category)} · {t('places.walkMinutes', { count: m.maxWalkMin })}
              <button
                className="grid h-7 w-7 place-items-center rounded-full hover:bg-white"
                aria-label={t('places.removeAnchor', { label: catLabel(m.category) })}
                onClick={() => setFilters({ mustHave: filters.mustHave.filter((_, j) => j !== i) })}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <select className={cn('h-11 rounded-xl border border-line bg-surface px-3', compact && 'min-w-0 flex-1')} value={mhCat} onChange={(e) => setMhCat(e.target.value)} aria-label={t('places.mustHave')}>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            onClick={() => setFilters({ mustHave: [...filters.mustHave.filter((m) => m.category !== mhCat), { category: mhCat, maxWalkMin: 10 }] })}
          >
            <Plus size={16} /> {t('places.addMustHave')}
          </Button>
        </div>
      </section>
    </div>
  )
}

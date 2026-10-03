import { Bike, Footprints, MapPin, Plus, TramFront, Trash2 } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { useMeta } from '@/api/hooks'
import type { Anchor, GeocodeHit, Mode } from '@/api/types'
import { Button } from '@/components/ui/button'
import { MUST_HAVE } from '@/content/defaults'
import { CURRENCY } from '@/lib/format'
import { L, cn } from '@/lib/utils'
import { useApp } from '@/state/store'
import { LEVEL_EMOJI } from './EmojiRow'

const MODE_ICON: Record<Mode, typeof TramFront> = { transit: TramFront, bike: Bike, walk: Footprints }
const inputCls = 'h-11 w-full rounded-xl border border-line bg-surface px-3 text-[15px] placeholder:text-ink-3 focus:border-accent focus:outline-none focus-visible:outline-3 focus-visible:outline-accent'

function GeoSearch({ onPick }: { onPick: (h: GeocodeHit) => void }) {
  const { t } = useTranslation()
  const city = useApp((s) => s.city)!
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<GeocodeHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState(0)
  const listId = useId()

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits(null)
      return
    }
    setBusy(true)
    const h = setTimeout(() => {
      api
        .geocode(city, q.trim())
        .then((r) => {
          setHits(r)
          setActive(0)
        })
        .catch(() => setHits([]))
        .finally(() => setBusy(false))
    }, 250)
    return () => clearTimeout(h)
  }, [q, city])

  const pick = (h: GeocodeHit) => {
    onPick(h)
    setQ('')
    setHits(null)
  }

  return (
    <div className="relative">
      <MapPin size={18} className="pointer-events-none absolute left-3 top-3 text-ink-3" />
      <input
        className={cn(inputCls, 'pl-9')}
        placeholder={t('places.searchPlaceholder')}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        role="combobox"
        aria-expanded={!!hits?.length}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={t('places.searchPlaceholder')}
        data-testid="geo-search"
        onKeyDown={(e) => {
          if (!hits?.length) return
          if (e.key === 'ArrowDown') setActive((a) => Math.min(hits.length - 1, a + 1))
          else if (e.key === 'ArrowUp') setActive((a) => Math.max(0, a - 1))
          else if (e.key === 'Enter') {
            e.preventDefault()
            pick(hits[active])
          } else return
          e.preventDefault()
        }}
      />
      {q.trim().length >= 2 && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-[var(--shadow-pop)]">
          {busy && !hits && <p className="px-3 py-2 text-sm text-ink-3">{t('places.searching')}</p>}
          {hits && hits.length === 0 && <p className="px-3 py-2 text-sm text-ink-3">{t('places.searchNoResults')}</p>}
          {hits && hits.length > 0 && (
            <ul id={listId} role="listbox">
              {hits.map((h, i) => (
                <li
                  key={`${h.label}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    pick(h)
                  }}
                  className={cn('cursor-pointer px-3 py-2.5 text-sm', i === active && 'bg-accent-soft')}
                >
                  {h.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

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

export function PlacesStep() {
  const { t } = useTranslation()
  const { city, lang, persona, anchors, setAnchors, filters, setFilters, budget, set } = useApp()
  const { data: meta } = useMeta(city)
  const isBuy = city === 'krakow'
  const cur = CURRENCY[city!]
  const curSym = cur === 'PLN' ? (lang === 'en' ? 'PLN' : 'zł') : lang === 'en' ? 'CZK' : 'Kč'
  const suggested = meta?.personas.find((p) => p.id === persona)?.suggestedAnchors?.[anchors.length]
  const categories = meta?.mustHaveCategories?.length ? meta.mustHaveCategories : MUST_HAVE
  const [mhCat, setMhCat] = useState(categories[0])

  const add = (h: GeocodeHit) => {
    const label = suggested ? L(suggested.label, lang) : h.label.split(',')[0]
    setAnchors([...anchors, { id: '', label, lat: h.lat, lon: h.lon, mode: suggested?.mode ?? 'transit', level: 4, maxMinutes: null }])
  }

  return (
    <div className="space-y-8">
      <section>
        <h3 className="font-semibold">{t('places.anchors')}</h3>
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
        <h3 className="mb-3 font-semibold">{t('places.limits')}</h3>
        <div className="grid gap-4 sm:grid-cols-2">
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

        <h4 className="mb-2 mt-6 text-sm font-medium text-ink-2">{t('places.mustHave')}</h4>
        <ul className="mb-3 flex flex-wrap gap-2">
          {filters.mustHave.map((m, i) => (
            <li key={i} className="inline-flex items-center gap-1 rounded-full bg-accent-soft py-1 pl-3 pr-1 text-sm">
              {t(`places.categories.${m.category}`, { defaultValue: m.category })} · {t('places.walkMinutes', { count: m.maxWalkMin })}
              <button
                className="grid h-7 w-7 place-items-center rounded-full hover:bg-white"
                aria-label={t('places.removeAnchor', { label: t(`places.categories.${m.category}`) })}
                onClick={() => setFilters({ mustHave: filters.mustHave.filter((_, j) => j !== i) })}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <select className="h-11 rounded-xl border border-line bg-surface px-3" value={mhCat} onChange={(e) => setMhCat(e.target.value)} aria-label={t('places.mustHave')}>
            {categories.map((c) => (
              <option key={c} value={c}>
                {t(`places.categories.${c}`, { defaultValue: c })}
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

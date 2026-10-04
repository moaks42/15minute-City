import { latLngToCell } from 'h3-js'
import { ChevronDown, Plus, Search, X } from 'lucide-react'
import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import type { CityId, Filters } from '@/api/types'
import { GeoSearch } from '@/components/common/GeoSearch'
import { Button } from '@/components/ui/button'
import { MUST_HAVE } from '@/content/defaults'
import { STATIC_FALLBACK } from '@/lib/env'
import { fmtPricePerM2 } from '@/lib/format'
import { L, cn } from '@/lib/utils'
import { CITY_IDS, EMPTY_FILTERS, searchState, useApp, type ExpatHome } from '@/state/store'
import { usePersonas } from './shared'

// "My needs" are the existing hard limits (README §3.5): a must-have within N minutes' walk,
// the local price per m² and the noise level. Keys: "m:<category>", "price", "noise".
const WALK_MIN: Record<string, number> = { tram_stop: 5, supermarket: 5 } // other categories: 10
const PRICE_LIMIT: Record<CityId, number> = { krakow: 15_000, praha: 350 } // zł/m² to buy · Kč/m²/month rent
const NOISE_LIMIT = 55 // dB
/** Offered as one-tap chips; everything else is under "Add a need". */
const SUGGESTED = ['m:tram_stop', 'm:park', 'm:supermarket', 'price']

type Need = { key: string; emoji: string; label: string }

function useNeedOptions(city: CityId): Need[] {
  const { t } = useTranslation()
  const lang = useApp((s) => s.lang)
  const { data: meta } = useMeta(city)
  const cats = meta?.mustHaveCategories?.length ? meta.mustHaveCategories.filter((c) => c.available) : MUST_HAVE.map((id) => ({ id, emoji: '', label: null }))
  return [
    ...cats.map((c) => ({
      key: `m:${c.id}`,
      emoji: c.emoji,
      label: t('welcome.needWalk', { what: c.label ? L(c.label, lang) : t(`places.categories.${c.id}`, { defaultValue: c.id }), min: WALK_MIN[c.id] ?? 10 }),
    })),
    { key: 'price', emoji: '💰', label: t('welcome.needPrice', { price: fmtPricePerM2(PRICE_LIMIT[city], lang, city) }) },
    { key: 'noise', emoji: '🔇', label: t('welcome.needNoise', { db: NOISE_LIMIT }) },
  ]
}

const needsOf = (f: Filters) => [
  ...f.mustHave.map((m) => `m:${m.category}`),
  ...(f.maxPricePerM2 || f.maxRentPerM2 ? ['price'] : []),
  ...(f.maxNoiseDb ? ['noise'] : []),
]

function toFilters(city: CityId, keys: string[]): Filters {
  const price = keys.includes('price') ? PRICE_LIMIT[city] : null
  return {
    ...EMPTY_FILTERS,
    maxPricePerM2: city === 'krakow' ? price : null,
    maxRentPerM2: city === 'praha' ? price : null,
    maxNoiseDb: keys.includes('noise') ? NOISE_LIMIT : null,
    mustHave: keys.filter((k) => k.startsWith('m:')).map((k) => ({ category: k.slice(2), maxWalkMin: WALK_MIN[k.slice(2)] ?? 10 })),
  }
}

/** One labelled box of the search bar; the control inside fills it, so the whole box is clickable. */
function Field({ label, htmlFor, className, children }: { label: string; htmlFor?: string; className?: string; children: ReactNode }) {
  return (
    <div className={cn('relative h-16 min-w-0 rounded-2xl border border-line bg-surface transition-colors hover:border-line-strong focus-within:border-accent', className)}>
      <label htmlFor={htmlFor} className="pointer-events-none absolute left-4 top-2.5 z-10 text-xs font-semibold text-ink">
        {label}
      </label>
      {children}
    </div>
  )
}

const selectCls = 'absolute inset-0 w-full cursor-pointer appearance-none truncate rounded-2xl bg-transparent pb-2 pl-4 pr-10 pt-6 text-[15px] text-ink'
const Chevron = () => <ChevronDown size={18} aria-hidden className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-ink-3" />

/** Airbnb-style search: city, who you are, (relocating: where you live now) and your needs → results. */
export function SearchBox({ city, onCity, persona, onPersona }: { city: CityId; onCity: (c: CityId) => void; persona: string; onPersona: (id: string) => void }) {
  const { t } = useTranslation()
  const { set, filters, expatHome } = useApp()
  const ids = { city: useId(), persona: useId() }
  const personas = usePersonas(city)
  const options = useNeedOptions(city)
  const [needs, setNeeds] = useState<string[]>(() => needsOf(filters))
  const other: CityId = city === 'krakow' ? 'praha' : 'krakow'
  const [home, setHome] = useState<ExpatHome | null>(expatHome)
  const relocating = persona === 'expat' && !STATIC_FALLBACK // twins need the live engine
  const homeHere = home?.city === other ? home : null

  // Needs a city does not have (metro in Kraków) stay chosen but hidden, and are not sent.
  const chosen = options.filter((o) => needs.includes(o.key))
  const suggested = options.filter((o) => SUGGESTED.includes(o.key) && !needs.includes(o.key))
  const rest = options.filter((o) => !needs.includes(o.key))
  const add = (key: string) => key && setNeeds((n) => [...n, key])
  const remove = (key: string) => setNeeds((n) => n.filter((k) => k !== key))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const p = personas.find((x) => x.id === persona) ?? personas[0]
    set(searchState(city, p.id, p.weights, toFilters(city, chosen.map((o) => o.key)), relocating ? homeHere : null))
  }
  const homeLabel = t('welcome.liveNow', { in: t(`cities.in.${other}`) })

  return (
    <form
      role="search"
      aria-label={t('welcome.search')}
      onSubmit={submit}
      className="rounded-[28px] bg-surface p-3 shadow-[0_12px_48px_rgb(31_29_26/0.16)] sm:p-4"
      data-testid="welcome-search"
    >
      <div className={cn('grid gap-2 sm:gap-3', relocating ? 'sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1.3fr_auto]' : 'sm:grid-cols-[1fr_1fr_auto]')}>
        <Field label={t('nav.city')} htmlFor={ids.city}>
          <select id={ids.city} value={city} onChange={(e) => onCity(e.target.value as CityId)} className={selectCls} data-testid="search-city">
            {CITY_IDS.map((c) => (
              <option key={c} value={c}>
                {t(`cities.${c}`)}
              </option>
            ))}
          </select>
          <Chevron />
        </Field>
        <Field label={t('steps.persona.title')} htmlFor={ids.persona}>
          <select id={ids.persona} value={persona} onChange={(e) => onPersona(e.target.value)} className={selectCls} data-testid="search-persona">
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.emoji} {t(`personas.${p.id}`, { defaultValue: p.id })}
              </option>
            ))}
          </select>
          <Chevron />
        </Field>
        {relocating && (
          <Field label={homeLabel}>
            {homeHere ? (
              <div className="absolute inset-x-0 bottom-0 flex items-center gap-1 pb-1.5 pl-4 pr-2">
                <span className="min-w-0 flex-1 truncate text-[15px]" data-testid="search-home-value">
                  {homeHere.label}
                </span>
                <button
                  type="button"
                  onClick={() => setHome(null)}
                  aria-label={t('expat.change')}
                  title={t('expat.change')}
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-sunken hover:text-ink"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <GeoSearch
                city={other}
                icon={false}
                placeholder={t('expat.placeholder')}
                ariaLabel={homeLabel}
                className="absolute inset-0"
                inputClassName="h-16 rounded-2xl border-0 bg-transparent px-4 pb-2 pt-6"
                testId="search-home"
                onPick={(h) => setHome({ city: other, label: h.label, h3: h.h3 ?? latLngToCell(h.lat, h.lon, 9) })}
              />
            )}
          </Field>
        )}
        <Button type="submit" size="lg" className="h-16 rounded-2xl px-7 font-semibold" data-testid="search-submit">
          <Search size={18} aria-hidden /> {t('welcome.show')}
        </Button>
      </div>

      <div role="group" aria-label={t('welcome.needs')} className="mt-3 flex flex-wrap items-center gap-2 px-1 sm:mt-4">
        <span aria-hidden className="mr-1 text-sm font-semibold text-ink-2">
          {t('welcome.needs')}
        </span>
        {chosen.map((o) => (
          <span key={o.key} className="inline-flex h-8 items-center gap-1 rounded-full bg-accent-soft pl-3 pr-1 text-[13px] font-semibold text-accent-strong" data-testid="need-chip">
            <span aria-hidden>{o.emoji}</span> {o.label}
            <button
              type="button"
              onClick={() => remove(o.key)}
              aria-label={t('places.removeAnchor', { label: o.label })}
              className="grid h-6 w-6 place-items-center rounded-full hover:bg-surface"
            >
              <X size={14} />
            </button>
          </span>
        ))}
        {suggested.map((o) => (
          <button
            key={o.key}
            type="button"
            onClick={() => add(o.key)}
            aria-label={`${t('welcome.addNeed')}: ${o.label}`}
            className="inline-flex h-8 items-center gap-1 rounded-full border border-line px-2.5 text-[13px] font-medium text-ink-2 hover:border-accent hover:text-ink"
            data-testid={`need-${o.key}`}
          >
            <Plus size={14} aria-hidden />
            <span aria-hidden>{o.emoji}</span> {o.label}
          </button>
        ))}
        {rest.length > 0 && (
          <span className="relative inline-flex h-8 items-center gap-1 rounded-full border border-dashed border-line-strong px-2.5 text-[13px] font-medium text-ink-2 hover:border-accent hover:text-ink has-[select:focus-visible]:outline-3 has-[select:focus-visible]:outline-offset-2 has-[select:focus-visible]:outline-accent">
            <Plus size={14} aria-hidden /> {t('welcome.addNeed')}
            <select
              value=""
              onChange={(e) => add(e.target.value)}
              aria-label={t('welcome.addNeed')}
              className="absolute inset-0 cursor-pointer appearance-none rounded-full opacity-0"
              data-testid="add-need"
            >
              <option value="" disabled>
                {t('welcome.addNeed')}
              </option>
              {rest.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.emoji} {o.label}
                </option>
              ))}
            </select>
          </span>
        )}
      </div>
    </form>
  )
}

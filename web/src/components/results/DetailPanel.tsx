import { AlertTriangle, ArrowRight, Check, Info, Wind } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Legend as RLegend } from 'recharts'
import { useAir, useMatchBreaks, useMeta, useNoEffectiveWeights, usePlace, useSimilar, useTwins } from '@/api/hooks'
import type { CityId, CriterionId, Place } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { CRITERION_EMOJI } from '@/content/defaults'
import { STATIC_FALLBACK } from '@/lib/env'
import { archetypeInfo, fmtNum, fmtPricePerM2 } from '@/lib/format'
import { CATEGORICAL, seqColor } from '@/lib/palette'
import { MODE_ICON } from '@/components/onboarding/icons'
import { activeAnchor, useApp } from '@/state/store'
import { L } from '@/lib/utils'
import { SaveButton, ScoreBadge } from './RankingPanel'

export function Section({ title, children, hint }: { title: string; children: React.ReactNode; hint?: string }) {
  return (
    <section className="border-t border-line px-5 py-4">
      <h3 className="mb-3 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wide text-ink-3">
        {title}
        {hint && (
          <Tip content={hint}>
            <button aria-label={hint} className="grid h-6 w-6 place-items-center rounded-full hover:bg-sunken">
              <Info size={14} />
            </button>
          </Tip>
        )}
      </h3>
      {children}
    </section>
  )
}

export function CriteriaRadar({ series }: { series: { name: string; color: string; values: Partial<Record<CriterionId, number>>; dashed?: boolean }[] }) {
  const { t } = useTranslation()
  const weights = useApp((s) => s.weights)
  const keys = (Object.keys(CRITERION_EMOJI) as CriterionId[]).filter((k) => (weights[k] ?? 0) > 0 && series.some((s) => s.values[k] != null))
  const data = keys.map((k) => ({ k: `${CRITERION_EMOJI[k]}`, full: t(`criteria.${k}`), ...Object.fromEntries(series.map((s, i) => [`s${i}`, s.values[k] ?? 0])) }))
  if (keys.length < 3) return null
  return (
    <figure>
      <div className="h-64 w-full" role="img" aria-label={series.map((s) => `${s.name}: ${keys.map((k) => `${t(`criteria.${k}`)} ${s.values[k] ?? '–'}`).join(', ')}`).join('; ')}>
        <ResponsiveContainer>
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke="#e3ded6" />
            <PolarAngleAxis dataKey="k" tick={{ fontSize: 16 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            {series.map((s, i) => (
              <Radar key={i} name={s.name} dataKey={`s${i}`} stroke={s.color} fill={s.color} fillOpacity={s.dashed ? 0 : 0.18} strokeWidth={2} strokeDasharray={s.dashed ? '4 3' : undefined} isAnimationActive={false} />
            ))}
            <RLegend wrapperStyle={{ fontSize: 12 }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

function Scale({ score }: { score: number | null }) {
  if (score == null) return <span className="h-2 flex-1 rounded-full bg-[repeating-linear-gradient(135deg,#e3ded6_0_4px,transparent_4px_7px)]" />
  return (
    <span className="relative h-2 flex-1 rounded-full" style={{ background: 'linear-gradient(90deg,#f6f1df,#a3d6b4,#2f979c,#1d4e6e)' }}>
      <span className="absolute top-1/2 h-4 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink shadow" style={{ left: `${score}%` }} />
    </span>
  )
}

function Twins({ place, city }: { place: Place; city: CityId }) {
  const { t } = useTranslation()
  const { lang, setCity, select } = useApp()
  const other: CityId = city === 'krakow' ? 'praha' : 'krakow'
  const twins = useTwins(place.id)
  if (STATIC_FALLBACK) return null
  return (
    <Section title={t('detail.twins')}>
      <p className="mb-3 text-sm text-ink-2">{t('detail.twinsLead', { city: t(`cities.in.${other}`) })}</p>
      {twins.isPending && <div className="h-24 animate-pulse rounded-xl bg-sunken" />}
      {twins.isError && <p className="text-sm text-ink-3">{t('states.error')}</p>}
      <ul className="space-y-2" data-testid="twins">
        {twins.data?.items.map((tw) => {
          const a = tw.archetype ? archetypeInfo(tw.archetype.id, lang) : null
          return (
            <li key={tw.id}>
              <button
                className="flex w-full items-center gap-3 rounded-xl border border-line p-3 text-left hover:border-accent hover:bg-accent-soft"
                onClick={() => {
                  setCity(other)
                  select(tw.id)
                }}
                data-testid="twin"
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sunken text-sm font-bold tabular-nums">{Math.round(tw.similarity * 100)}%</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{tw.name}</span>
                  <span className="block truncate text-xs text-ink-3">
                    {tw.district?.name}
                    {a && ` · ${a.label}`}
                  </span>
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-accent">
                  {t('detail.twinsOpen', { city: t(`cities.${other}`) })} <ArrowRight size={14} />
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

const AIR_LEVELS = ['very_good', 'good', 'moderate', 'sufficient', 'bad', 'very_bad']

function Air({ lat, lon }: { lat: number; lon: number }) {
  const { t } = useTranslation()
  const air = useAir(lat, lon)
  const lang = useApp((s) => s.lang)
  if (STATIC_FALLBACK) return null
  const d = air.data
  return (
    <div className="flex items-start gap-2 text-sm" aria-live="polite">
      <Wind size={18} className="mt-0.5 shrink-0 text-ink-3" />
      <p>
      <span className="font-medium">{t('detail.air')}: </span>
      {d && d.status !== 'unavailable' && d.level != null ? (
        <span>
          {t(`detail.airLevels.${AIR_LEVELS[d.level] ?? 'moderate'}`)}
          {d.pollutants?.pm25 != null && ` · ${t('detail.pm25')} ${fmtNum(d.pollutants.pm25, lang, 1)} µg/m³`}
          {d.station && (
            <span className="text-ink-3">
              {' '}
              ({d.station.name}, {d.source})
            </span>
          )}
        </span>
      ) : (
        <span className="text-ink-3">{air.isPending ? t('states.loading') : t('detail.airUnavailable')}</span>
      )}
      </p>
    </div>
  )
}

export function DetailPanel({ h3 }: { h3: string }) {
  const { t } = useTranslation()
  const { city, lang, anchors, budget, select, set, mapMode, commuteAnchor } = useApp()
  const q = usePlace(h3)
  const { data: meta } = useMeta(city)
  const similar = useSimilar(h3)
  const breaks = useMatchBreaks()
  const neutral = useNoEffectiveWeights() // nothing rated: no match % to show
  const p = q.data
  if (q.isPending) return <p className="p-5 text-ink-3">{t('detail.loading')}</p>
  if (q.isError || !p || !city)
    return (
      <div className="p-5" role="alert">
        <p className="mb-3">{t('detail.error')}</p>
        <Button variant="secondary" size="sm" onClick={() => q.refetch()}>
          {t('states.retry')}
        </Button>
      </div>
    )
  const arch = p.archetype ? archetypeInfo(p.archetype.id, lang) : null
  // What the map lens shows, for this place.
  const lensCrit = mapMode !== 'match' && mapMode !== 'commute' && p.criteria[mapMode] != null ? mapMode : null
  const lensAnchor = mapMode === 'commute' ? activeAnchor({ anchors, commuteAnchor }) : undefined
  const lensTime = lensAnchor && p.anchors.find((a) => a.id === lensAnchor.id)
  const LensIcon = lensAnchor ? MODE_ICON[lensAnchor.mode] : null
  const catLabel = (id: string) => {
    const c = meta?.mustHaveCategories.find((x) => x.id === id)
    return c ? `${c.emoji} ${L(c.label, lang)}` : t(`places.categories.${id}`, { defaultValue: id.replace(/_/g, ' ') })
  }
  const indMeta = new Map(meta?.criteria.flatMap((c) => c.indicators.map((i) => [i.column, i] as const)) ?? [])
  const byCrit = new Map<CriterionId, typeof p.indicators>()
  for (const i of p.indicators) byCrit.set(i.criterion, [...(byCrit.get(i.criterion) ?? []), i])

  return (
    <div data-testid="detail">
      <div className="flex items-center gap-4 px-5 py-4">
        {!neutral && <ScoreBadge score={p.score ?? 0} size="lg" breaks={breaks} />}
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-2xl font-semibold leading-tight" data-testid="detail-name">
            {p.name}
          </h2>
          <p className="text-sm text-ink-3">{p.district?.name}</p>
          {!neutral && <p className="text-sm text-ink-2">{t('results.matchPct', { pct: p.score ?? 0 })}</p>}
          {lensAnchor && lensTime && LensIcon && (
            <p className="flex items-center gap-1.5 text-sm font-semibold text-accent" data-testid="detail-lens">
              <LensIcon size={15} aria-hidden />
              {t('mapUi.hover.commute', {
                time: lensTime.minutes != null ? t('map.minutes', { count: lensTime.minutes }) : t('map.over60'),
                place: lensAnchor.label || t('map.legend.anchor'),
              })}
            </p>
          )}
          {lensCrit && (
            <p className="text-sm font-semibold text-accent" data-testid="detail-lens">
              <span aria-hidden>{CRITERION_EMOJI[lensCrit]}</span> {t('mapUi.hover.criterion', { criterion: t(`criteria.${lensCrit}`), value: p.criteria[lensCrit] })}
            </p>
          )}
          {arch && (
            <Tip content={`${arch.desc} ${t('detail.archetypeHint')}`}>
              <span tabIndex={0} className="mt-1 inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-medium" data-testid="archetype">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORICAL[arch.color] }} />
                {arch.label} · {t('detail.probability', { pct: Math.round((p.archetype!.p ?? 0) * 100) })}
              </span>
            </Tip>
          )}
        </div>
        <SaveButton className="self-start" item={{ city, id: p.id, kind: 'hex', name: p.name, lat: p.centroid.lat, lon: p.centroid.lon }} />
      </div>
      <div className="space-y-1 px-5 pb-4 text-sm">
        {(p.highlights ?? []).map((h, i) => (
          <p key={i} className="flex gap-1.5">
            <Check size={16} className="mt-0.5 shrink-0 text-good" /> {h.text}
          </p>
        ))}
        {(p.warnings ?? []).map((h, i) => (
          <p key={i} className="flex gap-1.5 text-ink-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" /> {h.text}
          </p>
        ))}
        <div className="pt-2">
          <Air lat={p.centroid.lat} lon={p.centroid.lon} />
        </div>
      </div>

      <Section title={t('detail.radar')}>
        <CriteriaRadar
          series={[
            { name: t('detail.thisPlace'), color: '#0e6e6c', values: p.criteria },
            { name: t('detail.cityMedian'), color: '#8a8378', values: p.cityMedian, dashed: true },
          ]}
        />
      </Section>

      <Section title={t('detail.budget')}>
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          {p.price?.value != null && (
            <div>
              <p className="text-xs text-ink-3">{t('detail.price')}</p>
              <p className="text-lg font-semibold tabular-nums">{fmtPricePerM2(p.price.value, lang, city)}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-ink-3">{t('detail.budget')}</p>
            {budget && p.budgetM2 ? (
              <p className="text-lg font-semibold text-accent" data-testid="budget-m2">
                {t('detail.budgetM2', { m2: fmtNum(p.budgetM2, lang) })}
              </p>
            ) : (
              <button className="text-sm text-accent underline-offset-2 hover:underline" onClick={() => set({ prefsSection: 'limits', prefsOpen: true })}>
                {t('detail.budgetNone')}
              </button>
            )}
          </div>
        </div>
      </Section>

      {p.anchors.length > 0 && (
        <Section title={t('detail.commute')}>
          <ul className="space-y-1 text-sm">
            {p.anchors.map((a) => (
              <li key={a.id} className="flex justify-between">
                <span>{anchors.find((x) => x.id === a.id)?.label ?? a.label ?? a.id}</span>
                <b className="tabular-nums">{a.minutes != null ? t('map.minutes', { count: a.minutes }) : '–'}</b>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={t('detail.indicators')}>
        <div className="space-y-4">
          {[...byCrit.entries()].map(([crit, inds]) => (
            <div key={crit}>
              <p className="mb-1.5 flex items-center gap-2 text-sm font-medium">
                <span aria-hidden>{CRITERION_EMOJI[crit]}</span> {t(`criteria.${crit}`)}
                {p.criteria[crit] != null && (
                  <span className="ml-auto rounded px-1.5 text-xs font-bold tabular-nums" style={{ background: seqColor(p.criteria[crit]!), color: p.criteria[crit]! >= 57 ? '#fff' : '#1f1d1a' }}>
                    {p.criteria[crit]}
                  </span>
                )}
              </p>
              <ul className="space-y-1.5">
                {inds.map((i) => {
                  const im = indMeta.get(i.column)
                  return (
                  <li key={i.column} className="grid grid-cols-[1fr_auto] items-center gap-x-3 text-sm sm:grid-cols-[minmax(0,10rem)_1fr_auto]">
                    <span className="truncate text-ink-2" title={i.text ?? undefined}>{im ? L(im.label, lang) : i.indicator}</span>
                    <span className="col-span-2 row-start-2 flex sm:col-span-1 sm:row-start-auto">
                      <Scale score={i.score} />
                    </span>
                    <span className="text-right tabular-nums">
                      {i.value != null && !i.imputed ? (
                        `${fmtNum(i.value, lang, im?.decimals ?? 1)} ${im ? L(im.unitLabel, lang) : i.unit}`
                      ) : (
                        <Tip content={t('detail.imputed')}>
                          <span tabIndex={0} className="text-ink-3 italic">
                            {t('criteria.noData')}
                          </span>
                        </Tip>
                      )}
                    </span>
                  </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {p.nearest.length > 0 && (
        <Section title={t('detail.nearest')}>
          <ul className="grid grid-cols-1 gap-1.5 text-sm sm:grid-cols-2">
            {p.nearest.map((n) => (
              <li key={n.category} title={catLabel(n.category)} className="flex justify-between gap-2 rounded-lg bg-sunken px-3 py-2">
                <span className="truncate">{n.name ?? catLabel(n.category)}</span>
                <span className="shrink-0 tabular-nums text-ink-2">{t('detail.walk', { count: Math.round(n.walkMin) })}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {!!similar.data?.items.length && (
        <Section title={t('detail.similar')}>
          <div className="flex flex-wrap gap-2">
            {similar.data.items.map((s) => (
              <Button key={s.id} variant="secondary" size="sm" onClick={() => select(s.id)}>
                {s.name}
                {s.similarity != null && <span className="text-xs text-ink-3">{t('detail.similarity', { pct: Math.round(s.similarity * 100) })}</span>}
              </Button>
            ))}
          </div>
        </Section>
      )}

      <Twins place={p} city={city} />
    </div>
  )
}

import { AlertTriangle, Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { noEffectiveWeights, useDistrictShapes, useLens, useRanking, useScore } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { archetypeInfo, fmtNum, fmtPricePerM2 } from '@/lib/format'
import { CATEGORICAL } from '@/lib/palette'
import { geoBounds } from '@/lib/utils'
import { useApp } from '@/state/store'
import { CriteriaRadar, Section } from './DetailPanel'
import { LensBadge, PlaceCard, SaveButton } from './RankingPanel'

/** A whole district: the population-weighted mean of all its habitable places, in the map's lens. */
export function DistrictDetail({ id }: { id: string }) {
  const { t } = useTranslation()
  const { city, lang, anchors, budget, set } = useApp()
  const lens = useLens()
  const q = useRanking('district')
  const shapes = useDistrictShapes(city)
  const best = useScore('hex', true, { rankBy: lens.rankBy, district: id })
  const p = q.data?.top.find((x) => x.id === id)
  const shape = shapes.data?.features.find((f) => String(f.properties?.id) === id)
  const name = p?.name ?? (shape?.properties?.name as string | undefined) ?? id
  const unrated = noEffectiveWeights(q.data)
  const neutral = unrated && !lens.rankBy
  if (q.isPending) return <p className="p-5 text-ink-3">{t('detail.loading')}</p>
  if (q.isError && !q.data)
    return (
      <div className="p-5" role="alert">
        <p className="mb-3">{t('detail.error')}</p>
        <Button variant="secondary" size="sm" onClick={() => q.refetch()}>
          {t('states.retry')}
        </Button>
      </div>
    )
  const arch = p?.archetype ? archetypeInfo(p.archetype.id, lang) : null
  const [[w, s], [e, n]] = shape ? geoBounds(shape.geometry) : [[0, 0], [0, 0]]
  const centre = p?.centroid ?? { lat: (s + n) / 2, lon: (w + e) / 2 }
  const places = best.data?.top.slice(0, 5) ?? []

  return (
    <div data-testid="district-detail">
      <div className="flex items-center gap-4 px-5 py-4">
        {p && !neutral && <LensBadge p={p} lens={lens} size="lg" />}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t('saved.district')}</p>
          <h2 className="font-display text-2xl font-semibold leading-tight" data-testid="detail-name">
            {name}
          </h2>
          {p && lens.rankBy && !unrated && <p className="text-sm text-ink-2">{t('results.matchPct', { pct: p.score })}</p>}
          {p?.sharePassing != null && p.sharePassing < 1 && <p className="text-sm text-ink-2">{t('results.sharePassing', { pct: Math.round(p.sharePassing * 100) })}</p>}
          {arch && (
            <Tip content={`${arch.desc} ${t('detail.archetypeHint')}`}>
              <span tabIndex={0} className="mt-1 inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-medium">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORICAL[arch.color] }} />
                {arch.label}
              </span>
            </Tip>
          )}
        </div>
        <SaveButton className="self-start" item={{ city, id, kind: 'district', name, lat: centre.lat, lon: centre.lon }} />
      </div>

      {!p ? (
        <p className="mx-5 mb-4 rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2" role="status" data-testid="district-no-match">
          {t('detail.districtNoMatch')}
        </p>
      ) : (
        <>
          <div className="space-y-1 px-5 pb-4 text-sm">
            {p.highlights.map((h, i) => (
              <p key={i} className="flex gap-1.5">
                <Check size={16} className="mt-0.5 shrink-0 text-good" /> {h.text}
              </p>
            ))}
            {p.warnings.map((h, i) => (
              <p key={i} className="flex gap-1.5 text-ink-2">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" /> {h.text}
              </p>
            ))}
            <p className="pt-1 text-xs text-ink-3">{t('detail.districtAvgNote')}</p>
          </div>

          <Section title={t('detail.radar')}>
            <CriteriaRadar
              series={[
                { name: t('detail.thisDistrict'), color: '#0e6e6c', values: p.criteria },
                { name: t('detail.cityMedian'), color: '#8a8378', values: q.data?.cityMedian ?? {}, dashed: true },
              ]}
            />
          </Section>

          {(p.price?.value != null || budget) && city && (
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
                    <p className="text-lg font-semibold text-accent">{t('detail.budgetM2', { m2: fmtNum(p.budgetM2, lang) })}</p>
                  ) : (
                    <button className="text-sm text-accent underline-offset-2 hover:underline" onClick={() => set({ prefsSection: 'limits', prefsOpen: true })}>
                      {t('detail.budgetNone')}
                    </button>
                  )}
                </div>
              </div>
            </Section>
          )}

          {p.anchors.length > 0 && (
            <Section title={t('detail.commute')} hint={t('detail.districtMedian')}>
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
        </>
      )}

      {!neutral && (
        <Section title={t('detail.districtBest')}>
          {best.isPending ? (
            <div className="h-32 animate-pulse rounded-2xl bg-sunken" />
          ) : places.length ? (
            <ol className="space-y-3" aria-label={t('detail.districtBest')} data-testid="district-best">
              {places.map((x) => (
                <PlaceCard key={x.id} p={x} lens={lens} showMatch={!!lens.rankBy && !unrated} />
              ))}
            </ol>
          ) : (
            <p className="text-sm text-ink-3">{t('detail.districtNoMatch')}</p>
          )}
        </Section>
      )}
    </div>
  )
}

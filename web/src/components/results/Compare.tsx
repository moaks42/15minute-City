import { useQueries } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { useScoreRequest } from '@/api/hooks'
import { CRITERIA } from '@/api/types'
import { Button } from '@/components/ui/button'
import { CRITERION_EMOJI } from '@/content/defaults'
import { fmtPricePerM2 } from '@/lib/format'
import { CATEGORICAL } from '@/lib/palette'
import { useApp } from '@/state/store'
import { CriteriaRadar } from './DetailPanel'

const COLORS = [CATEGORICAL[4], CATEGORICAL[5], CATEGORICAL[6]]

export function Compare() {
  const { t } = useTranslation()
  const { city, compare, set, lang, weights } = useApp()
  const req = useScoreRequest('hex')
  const qs = useQueries({
    queries: compare.map((id) => ({ queryKey: ['place', city, id, req], queryFn: () => api.place(city!, id, req), enabled: !!city })),
  })
  const places = qs.map((q) => q.data).filter((p): p is NonNullable<typeof p> => !!p)
  if (compare.length < 2) return <p className="p-5 text-ink-3">{t('compare.empty')}</p>
  const crits = CRITERIA.filter((c) => (weights[c] ?? 0) > 0)
  return (
    <div className="p-5" data-testid="compare">
      <CriteriaRadar series={places.map((p, i) => ({ name: p.name, color: COLORS[i], values: p.criteria }))} />
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="py-2 pr-2 font-medium text-ink-3">{t('compare.criterion')}</th>
              {places.map((p, i) => (
                <th key={p.id} className="px-2 py-2 text-right font-semibold" style={{ color: COLORS[i] }}>
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line font-semibold">
              <td className="py-2 pr-2">{t('map.modes.match')}</td>
              {places.map((p) => (
                <td key={p.id} className="px-2 text-right tabular-nums">
                  {p.score}%
                </td>
              ))}
            </tr>
            {crits.map((c) => {
              const vals = places.map((p) => p.criteria[c] ?? null)
              const best = Math.max(...vals.map((v) => v ?? -1))
              return (
                <tr key={c} className="border-b border-line">
                  <td className="py-2 pr-2">
                    <span aria-hidden>{CRITERION_EMOJI[c]}</span> {t(`criteria.${c}`)}
                  </td>
                  {vals.map((v, i) => (
                    <td key={i} className={`px-2 text-right tabular-nums ${v === best ? 'font-bold text-accent' : ''}`}>
                      {v ?? '–'}
                    </td>
                  ))}
                </tr>
              )
            })}
            <tr>
              <td className="py-2 pr-2">💰 {t('detail.price')}</td>
              {places.map((p) => (
                <td key={p.id} className="px-2 text-right tabular-nums">
                  {p.price?.value != null && city ? fmtPricePerM2(p.price.value, lang, city) : '–'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <Button variant="ghost" size="sm" className="mt-4" onClick={() => set({ compare: [] })}>
        {t('compare.clear')}
      </Button>
    </div>
  )
}

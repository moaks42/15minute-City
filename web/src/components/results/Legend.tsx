import { useTranslation } from 'react-i18next'
import { COMMUTE, COMMUTE_BANDS, FAILING, SEQ, UNINHABITED } from '@/lib/palette'
import { useApp } from '@/state/store'

/** Always-visible legend (README §3.6, §3.8). */
export function Legend({ commuteLabel, breaks }: { commuteLabel?: string; breaks: number[] }) {
  const { t } = useTranslation()
  const mapMode = useApp((s) => s.mapMode)
  const title =
    mapMode === 'match'
      ? t('map.legend.match')
      : mapMode === 'commute'
        ? t('map.legend.commute', { place: commuteLabel || t('map.legend.anchor') })
        : t('map.legend.criterion', { criterion: t(`criteria.${mapMode}`) })

  return (
    <div className="pointer-events-auto absolute bottom-[calc(38%+0.75rem)] left-3 z-10 w-[min(260px,calc(100%-1.5rem))] lg:bottom-8 rounded-xl border border-line bg-surface/95 p-2 text-xs sm:p-3 shadow-[var(--shadow-card)] backdrop-blur" role="group" aria-label={t('map.legend.title')} data-testid="legend">
      <p className="mb-1.5 font-semibold text-ink sm:mb-2">{title}</p>
      {mapMode === 'commute' ? (
        <>
          <div className="flex overflow-hidden rounded">
            {COMMUTE.map((c) => (
              <span key={c} className="h-3 flex-1" style={{ background: c }} />
            ))}
          </div>
          <div className="mt-1 flex text-[11px] text-ink-3">
            {COMMUTE_BANDS.map((b) => (
              <span key={b} className="flex-1 text-center">
                ≤{b}
              </span>
            ))}
            <span className="flex-1 text-center">60+</span>
          </div>
        </>
      ) : (
        <>
          <div className="flex overflow-hidden rounded">
            {SEQ.map((c) => (
              <span key={c} className="h-3 flex-1" style={{ background: c }} />
            ))}
          </div>
          <div className="relative mt-1 h-3.5 text-[10px] tabular-nums text-ink-3">
            {breaks.map((b, i) => (
              <span key={i} className="absolute -translate-x-1/2" style={{ left: `${((i + 1) / SEQ.length) * 100}%` }}>
                {Math.round(b)}
              </span>
            ))}
          </div>
          <div className="mt-0.5 flex justify-between text-[11px] text-ink-3">
            <span>← {t('map.legend.low')}</span>
            <span>{t('map.legend.high')} →</span>
          </div>
        </>
      )}
      <ul className="mt-2 hidden space-y-1 text-ink-2 sm:block">
        {mapMode === 'match' && (
          <li className="flex items-center gap-2">
            <span className="h-3 w-5 rounded-sm" style={{ background: `repeating-linear-gradient(135deg, ${FAILING} 0 3px, #8a8378 3px 4.5px)` }} />
            {t('map.legend.failing')}
          </li>
        )}
        <li className="flex items-center gap-2">
          <span className="h-3 w-5 rounded-sm border border-line" style={{ background: UNINHABITED }} />
          {t('map.legend.uninhabited')}
        </li>
        {mapMode === 'match' && (
          <li className="flex items-center gap-2">
            <span className="grid h-4 w-4 place-items-center rounded-full bg-accent text-[9px] font-bold text-white">1</span>
            {t('map.legend.top')}
          </li>
        )}
      </ul>
    </div>
  )
}

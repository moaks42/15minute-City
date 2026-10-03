import { ArrowRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { CityId } from '@/api/types'
import { LangSwitch, Logo } from '@/components/layout/Header'
import { CITY_IDS, useApp } from '@/state/store'

const CITY_STYLE: Record<CityId, { bg: string; dot: string }> = {
  krakow: { bg: 'linear-gradient(135deg,#0e6e6c 0%,#1d4e6e 100%)', dot: '#f2b84b' },
  praha: { bg: 'linear-gradient(135deg,#7b2d43 0%,#3f2a5c 100%)', dot: '#f6d58e' },
}

function HexMotif({ color }: { color: string }) {
  const hexes = []
  for (let r = 0; r < 4; r++)
    for (let c = 0; c < 6; c++) {
      const x = c * 26 + (r % 2) * 13
      const y = r * 22
      const o = ((r * 7 + c * 13) % 10) / 14 + 0.12
      hexes.push(<polygon key={`${r}-${c}`} points="13,0 26,7.5 26,22.5 13,30 0,22.5 0,7.5" transform={`translate(${x} ${y}) scale(.8)`} fill={color} opacity={o} />)
    }
  return (
    <svg viewBox="0 0 170 100" className="absolute -right-4 -bottom-3 h-28 w-48" aria-hidden>
      {hexes}
    </svg>
  )
}

export function CityPicker() {
  const { t } = useTranslation()
  const setCity = useApp((s) => s.setCity)
  return (
    <div className="h-full overflow-y-auto bg-bg">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
        <Logo />
        <LangSwitch />
      </div>
      <main className="mx-auto max-w-4xl px-4 pb-16 pt-6 sm:px-6 sm:pt-14">
        <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-accent">Kraków · Praha</p>
        <h1 className="max-w-2xl font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl">{t('app.tagline')}</h1>
        <p className="mt-5 max-w-xl text-lg text-ink-2">{t('app.privacy')}</p>

        <h2 className="mt-12 font-display text-2xl font-semibold">{t('steps.city.title')}</h2>
        <p className="mt-1 text-ink-3">{t('steps.city.lead')}</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {CITY_IDS.map((c) => (
            <button
              key={c}
              data-testid={`city-${c}`}
              onClick={() => setCity(c)}
              className="group relative min-h-44 overflow-hidden rounded-2xl p-6 text-left text-white shadow-[var(--shadow-card)] transition-transform hover:-translate-y-0.5"
              style={{ background: CITY_STYLE[c].bg }}
            >
              <HexMotif color={CITY_STYLE[c].dot} />
              <span className="relative block font-display text-4xl font-bold">{t(`cities.${c}`)}</span>
              <span className="relative mt-2 block max-w-[16rem] text-sm text-white/85">{t(`cities.cardHint.${c}`)}</span>
              <span className="relative mt-6 inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-2 text-sm font-semibold backdrop-blur transition-colors group-hover:bg-white/25">
                {t('nav.next')} <ArrowRight size={16} />
              </span>
            </button>
          ))}
        </div>
      </main>
    </div>
  )
}

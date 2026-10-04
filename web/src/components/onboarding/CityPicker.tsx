import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CityId } from '@/api/types'
import { LangSwitch, Logo } from '@/components/layout/Header'
import { Collections } from '@/components/welcome/Collections'
import { HeroGrid } from '@/components/welcome/HeroGrid'
import { SearchBox } from '@/components/welcome/SearchBox'
import { usePersonas } from '@/components/welcome/shared'
import { EMPTY_FILTERS, searchState, useApp } from '@/state/store'

// Teal → indigo, a gold glow top right, and a soft shade on the left so the
// gold and white text keep AA contrast (gold #E8C46A ≥ 4.5:1 on the shaded teal).
const HERO_BG = [
  'radial-gradient(circle at 92% -10%, rgb(212 168 75 / 0.42), transparent 42%)',
  'linear-gradient(90deg, rgb(6 32 36 / 0.32) 0%, rgb(6 32 36 / 0.12) 45%, transparent 70%)',
  'linear-gradient(120deg, #17766F 0%, #1D5F70 48%, #3D3A6B 100%)',
].join(',')

/** Welcome screen: hero with the city's hex grid, the search bar and curated collections. */
export function CityPicker() {
  const { t } = useTranslation()
  const { persona: lastPersona, set } = useApp()
  const [city, setCity] = useState<CityId>('krakow')
  const [persona, setPersona] = useState(lastPersona ?? 'working')
  const personas = usePersonas(city)
  const p = personas.find((x) => x.id === persona) ?? personas[0]

  return (
    <div className="h-full overflow-y-auto overflow-x-hidden bg-bg">
      <section className="relative isolate overflow-hidden text-white" style={{ background: HERO_BG }}>
        <HeroGrid city={city} persona={p} className="pointer-events-none absolute inset-y-0 right-0 -z-10 h-full w-full opacity-50 md:w-[68%] md:opacity-100" />
        <header className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-5 sm:px-6 [&_button:focus-visible]:outline-white">
          <Logo light />
          <nav className="flex items-center gap-1 sm:gap-2">
            {/* "Back to the map" there opens the results for what is picked here. */}
            <button
              onClick={() => set({ ...searchState(city, p.id, p.weights, EMPTY_FILTERS), view: 'about' })}
              className="rounded-full px-3 py-2 text-sm font-semibold hover:bg-white/10"
            >
              {t('nav.about')}
            </button>
            <LangSwitch dark />
          </nav>
        </header>
        <div className="mx-auto max-w-6xl px-4 pb-32 pt-6 sm:px-6 sm:pb-36 sm:pt-12">
          <h1 className="max-w-3xl font-display text-[2.5rem] font-bold leading-[1.05] tracking-tight sm:text-6xl">{t('app.tagline')}</h1>
          <p className="mt-3 font-display text-2xl font-semibold text-[#E8C46A] sm:text-3xl">{t('welcome.everything')}</p>
        </div>
      </section>

      <main className="relative mx-auto -mt-20 max-w-6xl px-4 pb-20 sm:-mt-24 sm:px-6">
        <SearchBox city={city} onCity={setCity} persona={p.id} onPersona={setPersona} />
        <Collections />
      </main>
    </div>
  )
}

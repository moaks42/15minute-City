import { ArrowLeft, ChevronUp, Info, MapPin, SlidersHorizontal } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import { CitySwitch, Header } from '@/components/layout/Header'
import { CriteriaList } from '@/components/onboarding/CriteriaList'
import { Compare } from '@/components/results/Compare'
import { DetailPanel } from '@/components/results/DetailPanel'
import { MapModeSwitch } from '@/components/results/MapModeSwitch'
import { RankingPanel } from '@/components/results/RankingPanel'
import { Button } from '@/components/ui/button'
import { Sheet } from '@/components/ui/sheet'
import { DEFAULT_PERSONAS } from '@/content/defaults'
import { Attribution } from '@/components/layout/Attribution'
import { cn } from '@/lib/utils'
import { useApp } from '@/state/store'

const MapView = lazy(() => import('@/components/results/MapView'))

function useIsDesktop() {
  const q = '(min-width: 1024px)'
  const [d, setD] = useState(() => window.matchMedia(q).matches)
  useEffect(() => {
    const m = window.matchMedia(q)
    const on = () => setD(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return d
}

function Preferences() {
  const { t } = useTranslation()
  const { city, persona, pickPersona, set, anchors } = useApp()
  const { data: meta } = useMeta(city)
  const personas = meta?.personas?.length ? meta.personas : DEFAULT_PERSONAS
  return (
    <div className="px-4 py-3">
      <h2 className="sr-only">{t('nav.filters')}</h2>
      <div role="radiogroup" aria-label={t('steps.persona.title')} className="mb-2 flex flex-wrap gap-1.5">
        {personas.map((p) => (
          <button
            key={p.id}
            role="radio"
            aria-checked={persona === p.id}
            onClick={() => pickPersona(p.id, p.weights)}
            className={cn('inline-flex min-h-9 items-center gap-1 rounded-full border px-2.5 text-sm', persona === p.id ? 'border-accent bg-accent-soft font-medium' : 'border-line hover:bg-sunken')}
            data-testid={`pref-persona-${p.id}`}
          >
            <span aria-hidden>{p.emoji}</span> {t(`personas.${p.id}`)}
          </button>
        ))}
      </div>
      <CriteriaList compact />
      <Button variant="secondary" className="mt-3 w-full" onClick={() => set({ step: 'places' })}>
        <MapPin size={16} /> {t('steps.places.title')}
        {anchors.length > 0 && <span className="rounded-full bg-accent px-1.5 text-xs text-white">{anchors.length}</span>}
      </Button>
    </div>
  )
}

export function ResultsPage() {
  const { t } = useTranslation()
  const desktop = useIsDesktop()
  const { sel, select, compare, set, city } = useApp()
  const [compareOpen, setCompareOpen] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [sheetUp, setSheetUp] = useState(false)

  const compareBtn = compare.length >= 2 && (
    <Button size="sm" onClick={() => setCompareOpen(true)} data-testid="open-compare">
      {t('results.compareN', { count: compare.length })}
    </Button>
  )

  const right = sel ? (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <Button variant="ghost" size="sm" onClick={() => select(null)} data-testid="detail-back">
          <ArrowLeft size={16} /> {t('nav.back')}
        </Button>
        <h2 className="truncate font-display text-lg font-semibold">{t('detail.title')}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <DetailPanel h3={sel} />
      </div>
    </div>
  ) : (
    <RankingPanel />
  )

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="relative flex min-h-0 flex-1">
        {desktop && (
          <aside className="flex w-[340px] shrink-0 flex-col border-r border-line bg-surface xl:w-[380px]" aria-label={t('nav.filters')}>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <Preferences />
            </div>
            <Attribution compact />
          </aside>
        )}
        <main className="relative min-w-0 flex-1" aria-label={t('nav.map')}>
          <Suspense fallback={<div className="grid h-full place-items-center text-ink-3">{t('map.loading')}</div>}>
            <MapView />
          </Suspense>
          <MapModeSwitch />
          {desktop && compareBtn && <div className="absolute bottom-8 right-3 z-10">{compareBtn}</div>}
        </main>
        {desktop && (
          <aside className="flex w-[400px] shrink-0 flex-col border-l border-line bg-bg xl:w-[440px]" aria-label={t('nav.results')}>
            {right}
          </aside>
        )}

        {!desktop && (
          <>
            <div className="absolute right-3 top-14 z-20 flex flex-col items-end gap-2">
              <Button variant="secondary" size="icon" onClick={() => setFiltersOpen(true)} aria-label={t('nav.filters')} data-testid="open-filters">
                <SlidersHorizontal size={18} />
              </Button>
            </div>
            <section
              className={cn(
                'absolute inset-x-0 bottom-0 z-20 flex flex-col rounded-t-2xl border-t border-line bg-bg shadow-[var(--shadow-pop)] transition-[height] duration-200',
                sheetUp ? 'h-[78%]' : 'h-[38%]',
              )}
              aria-label={t('nav.results')}
            >
              <button
                className="flex w-full flex-col items-center gap-1 pb-1 pt-2"
                onClick={() => setSheetUp((u) => !u)}
                aria-expanded={sheetUp}
                aria-label={t('nav.results')}
              >
                <span className="h-1.5 w-10 rounded-full bg-line-strong" />
                <ChevronUp size={16} className={cn('text-ink-3 transition-transform', sheetUp && 'rotate-180')} />
              </button>
              <div className="flex items-center gap-2 px-3 pb-1">
                <CitySwitch />
                <div className="ml-auto flex gap-2">
                  {compareBtn}
                  <Button variant="ghost" size="icon" onClick={() => set({ view: 'about' })} aria-label={t('nav.about')}>
                    <Info size={18} />
                  </Button>
                </div>
              </div>
              <div className="min-h-0 flex-1">
                <RankingPanel />
              </div>
            </section>
            <Sheet open={filtersOpen} onOpenChange={setFiltersOpen} title={t('nav.filters')} side="bottom">
              <Preferences />
              <div className="sticky bottom-0 border-t border-line bg-surface p-3">
                <Button className="w-full" onClick={() => setFiltersOpen(false)}>
                  {t('nav.showResults')}
                </Button>
              </div>
            </Sheet>
            <Sheet open={!!sel} onOpenChange={(o) => !o && select(null)} title={t('detail.title')} side="bottom" className="h-[92dvh]">
              {sel && <DetailPanel h3={sel} />}
            </Sheet>
          </>
        )}
      </div>
      <Sheet open={compareOpen && compare.length >= 2} onOpenChange={setCompareOpen} title={t('compare.title')} side={desktop ? 'right' : 'bottom'} className={desktop ? 'sm:w-[560px]' : 'h-[92dvh]'}>
        <Compare key={city} />
      </Sheet>
    </div>
  )
}

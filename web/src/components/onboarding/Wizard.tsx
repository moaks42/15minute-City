import { ArrowLeft, ArrowRight, Map as MapIcon } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/layout/Header'
import { useApp, type Step } from '@/state/store'
import { CriteriaList } from './CriteriaList'
import { PersonaStep } from './PersonaStep'

const MapView = lazy(() => import('@/components/results/MapView'))

// Two steps; places and limits are set in the results, next to the map.
const ORDER = ['persona', 'criteria'] as const
type WizardStep = (typeof ORDER)[number]

export function Wizard() {
  const { t } = useTranslation()
  const { step, set, city } = useApp()
  const idx = Math.max(0, ORDER.indexOf(step as WizardStep))
  const go = (s: Step) => {
    set({ step: s })
    document.getElementById('wizard-scroll')?.scrollTo({ top: 0 })
  }
  const next = () => go(idx < ORDER.length - 1 ? ORDER[idx + 1] : 'results')
  const back = () => (idx === 0 ? set({ city: null }) : go(ORDER[idx - 1]))
  const n = idx + 1
  const total = ORDER.length

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex min-h-0 flex-1">
        <div id="wizard-scroll" className="flex min-h-0 w-full flex-col overflow-y-auto lg:w-[600px] lg:shrink-0 lg:border-r lg:border-line">
          <div className="flex-1 px-4 pb-6 pt-6 sm:px-8">
            <div className="mb-1 flex items-center gap-3">
              <span className="text-sm font-medium text-accent">{t('steps.progress', { n, total })}</span>
              <div className="flex flex-1 gap-1" aria-hidden>
                {Array.from({ length: total }).map((_, i) => (
                  <span key={i} className={`h-1.5 flex-1 rounded-full ${i < n ? 'bg-accent' : 'bg-line'}`} />
                ))}
              </div>
            </div>
            <h1 className="mt-4 font-display text-3xl font-bold tracking-tight">{t(`steps.${ORDER[idx]}.title`)}</h1>
            <p className="mb-6 mt-1 text-ink-3">{t(`steps.${ORDER[idx]}.lead`)}</p>
            {step === 'persona' && <PersonaStep onPicked={next} />}
            {step === 'criteria' && <CriteriaList />}
          </div>
          <div className="sticky bottom-0 flex items-center gap-2 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:px-8">
            <Button variant="ghost" onClick={back}>
              <ArrowLeft size={18} /> {t('nav.back')}
            </Button>
            <div className="ml-auto flex gap-2">
              {idx < ORDER.length - 1 && (
                <Button variant="secondary" onClick={next} data-testid="wizard-next">
                  {step === 'persona' ? t('nav.skip') : t('nav.next')} <ArrowRight size={18} />
                </Button>
              )}
              <Button onClick={() => go('results')} data-testid="show-results">
                <MapIcon size={18} /> {t('nav.showResults')}
              </Button>
            </div>
          </div>
        </div>
        <div className="relative hidden min-w-0 flex-1 lg:block" aria-hidden>
          {city && (
            <Suspense fallback={null}>
              <MapView preview />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  )
}

import { ArrowLeft, ChevronDown, ChevronUp, Funnel, Heart, Info, MapPin, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, SlidersHorizontal, UserRound, type LucideIcon } from 'lucide-react'
import { lazy, Suspense, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import { CitySwitch, Header } from '@/components/layout/Header'
import { CriteriaList } from '@/components/onboarding/CriteriaList'
import { LimitsForm, PlacesList } from '@/components/onboarding/PlacesStep'
import { Compare } from '@/components/results/Compare'
import { DetailPanel } from '@/components/results/DetailPanel'
import { MapModeSwitch } from '@/components/results/MapModeSwitch'
import { RankingPanel } from '@/components/results/RankingPanel'
import { Button } from '@/components/ui/button'
import { Sheet } from '@/components/ui/sheet'
import { DEFAULT_CRITERIA, DEFAULT_PERSONAS, type CriterionLite, type PersonaLite } from '@/content/defaults'
import { Attribution } from '@/components/layout/Attribution'
import { cn } from '@/lib/utils'
import { useApp, type PrefsSection as PrefsSectionId } from '@/state/store'

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

/** Scrolls the nearest scrollable ancestor (panel or sheet), never the page. */
function scrollToTop(el: HTMLElement) {
  let p = el.parentElement
  while (p && !/(auto|scroll)/.test(getComputedStyle(p).overflowY)) p = p.parentElement
  p?.scrollBy({ top: el.getBoundingClientRect().top - p.getBoundingClientRect().top - 8, behavior: 'smooth' })
}

/** One accordion section of the preferences: a header with a summary, content only while open. */
function PrefsSection({ id, icon: Icon, title, summary, children }: { id: PrefsSectionId; icon: LucideIcon; title: string; summary: string; children: ReactNode }) {
  const open = useApp((s) => s.prefsSection === id)
  const set = useApp((s) => s.set)
  const ref = useRef<HTMLElement>(null)
  const contentId = useId()
  const wasOpen = useRef(open)
  useEffect(() => {
    // A section that just opened comes into view: its focused row (the criterion on the map) or its header.
    if (open && !wasOpen.current && ref.current) {
      const focus = ref.current.querySelector<HTMLElement>('[data-focus]')
      if (focus) focus.scrollIntoView({ block: 'center', behavior: 'smooth' })
      else scrollToTop(ref.current)
    }
    wasOpen.current = open
  }, [open])
  return (
    <section ref={ref} className="border-b border-line" data-testid={`${id}-section`}>
      <button
        className={cn('flex min-h-12 w-full items-center gap-2.5 px-4 py-2 text-left hover:bg-sunken', open && 'sticky top-0 z-10 border-b border-line bg-surface')}
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => set({ prefsSection: open ? null : id })}
        data-testid={`${id}-toggle`}
      >
        <Icon size={18} className="shrink-0 text-accent" aria-hidden />
        <span className="shrink-0 text-[15px] font-semibold">{title}</span>
        <span className="min-w-0 flex-1 truncate text-right text-sm text-ink-3">{summary}</span>
        <ChevronDown size={18} className={cn('shrink-0 text-ink-3 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div id={contentId} className="px-4 pb-4 pt-3">
          {children}
        </div>
      )}
    </section>
  )
}

/** Preferences as an accordion: who you are · what matters · my places · hard limits. */
function Preferences() {
  const { t } = useTranslation()
  const { city, persona, pickPersona, weights, anchors, filters, budget } = useApp()
  const { data: meta } = useMeta(city)
  const personas: PersonaLite[] = meta?.personas?.length ? meta.personas : DEFAULT_PERSONAS
  const current = personas.find((p) => p.id === persona)
  const criteria: CriterionLite[] = (meta?.criteria?.length ? meta.criteria : DEFAULT_CRITERIA).filter((c) => c.coverage > 0)
  const rated = criteria.filter((c) => (weights[c.id] ?? 0) > 0).sort((a, b) => (weights[b.id] ?? 0) - (weights[a.id] ?? 0))
  const limits = (budget ? 1 : 0) + (filters.maxPricePerM2 || filters.maxRentPerM2 ? 1 : 0) + (filters.maxNoiseDb ? 1 : 0) + filters.mustHave.length
  return (
    <div>
      <PrefsSection id="profile" icon={UserRound} title={t('steps.persona.title')} summary={current ? `${current.emoji} ${t(`personas.${current.id}`)}` : t('prefs.none')}>
        <div role="radiogroup" aria-label={t('steps.persona.title')} className="flex flex-wrap gap-1.5">
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
      </PrefsSection>
      <PrefsSection
        id="criteria"
        icon={Heart}
        title={t('steps.criteria.title')}
        summary={rated.length ? `${rated.slice(0, 4).map((c) => c.emoji).join(' ')}${rated.length > 4 ? ` +${rated.length - 4}` : ''}` : t('prefs.none')}
      >
        <CriteriaList compact />
      </PrefsSection>
      <PrefsSection id="places" icon={MapPin} title={t('places.anchors')} summary={anchors.length ? anchors.map((a) => a.label).join(', ') : t('prefs.none')}>
        <PlacesList />
      </PrefsSection>
      <PrefsSection id="limits" icon={Funnel} title={t('places.limits')} summary={limits ? t('places.sectionCount', { count: limits }) : t('prefs.none')}>
        <LimitsForm />
      </PrefsSection>
    </div>
  )
}

/** A collapsed desktop panel: a slim rail that opens it again. */
function Rail({ side, label, action, onOpen }: { side: 'left' | 'right'; label: string; action: string; onOpen: () => void }) {
  const Icon = side === 'left' ? PanelLeftOpen : PanelRightOpen
  return (
    <button
      onClick={onOpen}
      aria-label={action}
      title={action}
      className={cn('flex w-11 shrink-0 flex-col items-center gap-3 border-line bg-surface py-3 text-ink-2 hover:bg-sunken hover:text-ink', side === 'left' ? 'border-r' : 'border-l')}
      data-testid={`rail-${side}`}
    >
      <Icon size={18} />
      <span className="text-sm font-medium [writing-mode:vertical-rl]" aria-hidden>
        {label}
      </span>
    </button>
  )
}

function CollapseButton({ side, label, onClick }: { side: 'left' | 'right'; label: string; onClick: () => void }) {
  const Icon = side === 'left' ? PanelLeftClose : PanelRightClose
  return (
    <Button variant="ghost" size="icon" onClick={onClick} aria-label={label} title={label} className="ml-auto shrink-0" data-testid={`collapse-${side}`}>
      <Icon size={18} />
    </Button>
  )
}

export function ResultsPage() {
  const { t } = useTranslation()
  const desktop = useIsDesktop()
  const { sel, select, compare, set, city, prefsOpen, leftOpen, rightOpen } = useApp()
  const [compareOpen, setCompareOpen] = useState(false)
  const [sheetUp, setSheetUp] = useState(false)

  // On desktop the preferences live in the left panel, which set() already expanded.
  useEffect(() => {
    if (desktop && prefsOpen) set({ prefsOpen: false })
  }, [desktop, prefsOpen, set])

  const compareBtn = compare.length >= 2 && (
    <Button size="sm" onClick={() => setCompareOpen(true)} data-testid="open-compare">
      {t('results.compareN', { count: compare.length })}
    </Button>
  )

  const collapseRight = <CollapseButton side="right" label={t('nav.collapseResults')} onClick={() => set({ rightOpen: false })} />
  const right = sel ? (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <Button variant="ghost" size="sm" onClick={() => select(null)} data-testid="detail-back">
          <ArrowLeft size={16} /> {t('nav.back')}
        </Button>
        <h2 className="truncate font-display text-lg font-semibold">{t('detail.title')}</h2>
        {collapseRight}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <DetailPanel h3={sel} />
      </div>
    </div>
  ) : (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-line py-1 pl-4 pr-3">
        <h2 className="text-sm font-semibold text-ink-2">{t('nav.results')}</h2>
        {collapseRight}
      </div>
      <div className="min-h-0 flex-1">
        <RankingPanel />
      </div>
    </div>
  )

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="relative flex min-h-0 flex-1">
        {desktop &&
          (leftOpen ? (
            <aside className="flex w-[340px] shrink-0 flex-col border-r border-line bg-surface xl:w-[380px]" aria-label={t('nav.filters')}>
              <div className="flex items-center gap-2 border-b border-line py-1 pl-4 pr-3">
                <h2 className="text-sm font-semibold text-ink-2">{t('nav.filters')}</h2>
                <CollapseButton side="left" label={t('nav.collapsePrefs')} onClick={() => set({ leftOpen: false })} />
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <Preferences />
              </div>
              <Attribution compact />
            </aside>
          ) : (
            <Rail side="left" label={t('nav.filters')} action={t('nav.expandPrefs')} onOpen={() => set({ leftOpen: true })} />
          ))}
        <main className="relative min-w-0 flex-1" aria-label={t('nav.map')}>
          <Suspense fallback={<div className="grid h-full place-items-center text-ink-3">{t('map.loading')}</div>}>
            <MapView />
          </Suspense>
          <MapModeSwitch />
          {desktop && compareBtn && <div className="absolute bottom-8 right-3 z-10">{compareBtn}</div>}
        </main>
        {desktop &&
          (rightOpen ? (
            <aside className="flex w-[400px] shrink-0 flex-col border-l border-line bg-bg xl:w-[440px]" aria-label={t('nav.results')}>
              {right}
            </aside>
          ) : (
            <Rail side="right" label={t('nav.results')} action={t('nav.expandResults')} onOpen={() => set({ rightOpen: true })} />
          ))}

        {!desktop && (
          <>
            <div className="absolute right-2.5 top-20 z-20 flex flex-col items-end gap-2">
              <Button variant="secondary" size="icon" onClick={() => set({ prefsOpen: true })} aria-label={t('nav.filters')} data-testid="open-filters">
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
            <Sheet open={prefsOpen} onOpenChange={(o) => set({ prefsOpen: o })} title={t('nav.filters')} side="bottom">
              <Preferences />
              <div className="sticky bottom-0 border-t border-line bg-surface p-3">
                <Button className="w-full" onClick={() => set({ prefsOpen: false })}>
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

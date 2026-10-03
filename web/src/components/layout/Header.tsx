import { Info, Share2, Check } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CityId, Lang } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { DATA_MODE } from '@/lib/env'
import { cn } from '@/lib/utils'
import { CITY_IDS, useApp } from '@/state/store'

export function Logo({ onClick }: { onClick?: () => void }) {
  const { t } = useTranslation()
  return (
    <button onClick={onClick} className="flex items-center gap-2 rounded-lg" aria-label={`${t('app.name')} – ${t('nav.home')}`}>
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <circle cx="16" cy="16" r="15" fill="var(--color-accent)" />
        <path d="M16 5l4 11-4 11-4-11z" fill="#fff" />
        <path d="M16 5l4 11h-8z" fill="var(--color-sun)" />
      </svg>
      <span className="hidden font-display text-xl font-bold tracking-tight min-[400px]:inline">{t('app.name')}</span>
    </button>
  )
}

export function LangSwitch({ className }: { className?: string }) {
  const { t } = useTranslation()
  const { lang, setLang } = useApp()
  return (
    <div role="radiogroup" aria-label={t('nav.language')} className={cn('inline-flex rounded-full bg-sunken p-1', className)}>
      {(['pl', 'cs', 'en'] as Lang[]).map((l) => (
        <button
          key={l}
          role="radio"
          aria-checked={lang === l}
          lang={l}
          onClick={() => setLang(l)}
          className={cn(
            'min-h-9 min-w-10 rounded-full px-2.5 text-xs font-semibold uppercase tracking-wide text-ink-2',
            lang === l && 'bg-surface text-ink shadow-sm',
          )}
        >
          {l}
        </button>
      ))}
    </div>
  )
}

export function CitySwitch({ className }: { className?: string }) {
  const { t } = useTranslation()
  const { city, setCity } = useApp()
  return (
    <div role="radiogroup" aria-label={t('nav.switchCity')} className={cn('inline-flex rounded-full bg-sunken p-1', className)}>
      {CITY_IDS.map((c: CityId) => (
        <button
          key={c}
          role="radio"
          aria-checked={city === c}
          data-testid={`city-switch-${c}`}
          onClick={() => setCity(c)}
          className={cn('min-h-9 rounded-full px-3 text-sm font-medium text-ink-2', city === c && 'bg-accent text-accent-ink shadow-sm')}
        >
          {t(`cities.${c}`)}
        </button>
      ))}
    </div>
  )
}

export function ShareButton({ compact }: { compact?: boolean }) {
  const { t } = useTranslation()
  const [done, setDone] = useState(false)
  const share = async () => {
    const url = window.location.href
    try {
      await navigator.clipboard.writeText(url)
      setDone(true)
      setTimeout(() => setDone(false), 2000)
    } catch {
      window.prompt(t('nav.shareFailed'), url)
    }
  }
  return (
    <Button variant="secondary" size={compact ? 'icon' : 'sm'} onClick={share} aria-label={t('nav.share')} aria-live="polite">
      {done ? <Check size={16} /> : <Share2 size={16} />}
      {!compact && (done ? t('nav.shareCopied') : t('nav.share'))}
    </Button>
  )
}

export function DataModeBadge() {
  const { t } = useTranslation()
  if (DATA_MODE === 'live') return null
  return (
    <Tip content={t(`app.dataMode.${DATA_MODE}Hint`)}>
      <span tabIndex={0} className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-sun bg-[#fdf3dc] px-2 py-1 text-[11px] font-semibold text-[#7a4d00] sm:px-2.5 sm:text-xs">
        {t(`app.dataMode.${DATA_MODE}`)}
      </span>
    </Tip>
  )
}

export function Header() {
  const { t } = useTranslation()
  const { set, city } = useApp()
  return (
    <header className="z-30 flex h-16 shrink-0 items-center gap-2 border-b border-line bg-surface/95 px-3 backdrop-blur sm:gap-3 sm:px-5">
      <Logo onClick={() => set({ city: null, step: 'persona', view: 'app', sel: null })} />
      <DataModeBadge />
      <div className="ml-auto flex items-center gap-2">
        {city && <CitySwitch className="hidden sm:inline-flex" />}
        <LangSwitch />
        {city && (
          <Button variant="ghost" size="sm" onClick={() => set({ view: 'about' })} className="hidden md:inline-flex">
            <Info size={16} /> {t('nav.about')}
          </Button>
        )}
        {city && <ShareButton compact />}
      </div>
    </header>
  )
}

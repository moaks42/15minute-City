import { Info, Share2, Check } from 'lucide-react'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import type { CityId, Lang } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { DATA_MODE } from '@/lib/env'
import { cn } from '@/lib/utils'
import { CITY_IDS, useApp } from '@/state/store'
import { HeaderSearch } from './HeaderSearch'

/** `compact`: in the app header on phones the name gives way to search, language and share. */
export function Logo({ onClick, compact }: { onClick?: () => void; compact?: boolean }) {
  const { t } = useTranslation()
  return (
    <button onClick={onClick} className="flex items-center gap-2 rounded-lg" aria-label={`${t('app.name')} – ${t('nav.home')}`}>
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <circle cx="16" cy="16" r="15" fill="var(--color-accent)" />
        <path d="M16 5l4 11-4 11-4-11z" fill="#fff" />
        <path d="M16 5l4 11h-8z" fill="var(--color-sun)" />
      </svg>
      <span className={cn('hidden font-display text-xl font-bold tracking-tight', compact ? 'sm:inline' : 'min-[400px]:inline')}>{t('app.name')}</span>
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

/** Clipboard API first; outside a secure context (LAN demo over http) fall back to execCommand. */
async function copyText(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      /* fall through */
    }
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.top = '0'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    ta.remove()
  }
}

export function ShareButton({ compact }: { compact?: boolean }) {
  const { t } = useTranslation()
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (!done) return
    const h = setTimeout(() => setDone(false), 2000)
    return () => clearTimeout(h)
  }, [done])
  const share = async () => {
    const url = window.location.href
    if (typeof navigator.share === 'function' && window.matchMedia('(pointer: coarse)').matches) {
      try {
        await navigator.share({ title: document.title, url })
        return
      } catch (e) {
        if ((e as DOMException)?.name === 'AbortError') return
      }
    }
    if (await copyText(url)) setDone(true)
    else window.prompt(t('nav.shareFailed'), url)
  }
  return (
    <>
      <Button variant="secondary" size={compact ? 'icon' : 'sm'} onClick={share} aria-label={t('nav.share')}>
        {done ? <Check size={16} /> : <Share2 size={16} />}
        {!compact && (done ? t('nav.shareCopied') : t('nav.share'))}
      </Button>
      {done &&
        createPortal(
          <div role="status" className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink px-4 py-2 text-sm font-medium text-white shadow-[var(--shadow-pop)]">
            {t('nav.shareCopied')}
          </div>,
          document.body,
        )}
    </>
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
    <header className="relative z-30 flex h-16 shrink-0 items-center gap-2 border-b border-line bg-surface/95 px-3 backdrop-blur sm:gap-3 sm:px-5">
      <Logo compact={!!city} onClick={() => set({ city: null, step: 'persona', view: 'app', sel: null })} />
      <DataModeBadge />
      <HeaderSearch />
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

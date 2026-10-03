import { useTranslation } from 'react-i18next'
import { CREDITS } from '@/content/sources'
import { useApp } from '@/state/store'

export function Attribution({ compact }: { compact?: boolean }) {
  const { t } = useTranslation()
  const { city, set } = useApp()
  if (!city) return null
  return (
    <footer className={compact ? 'border-t border-line px-4 py-2 text-[11px] leading-snug text-ink-3' : 'text-sm text-ink-3'}>
      <p>{t('footer.attribution')}</p>
      <p>
        {t('footer.sources', { sources: CREDITS[city].join(', ') })} ·{' '}
        <button className="underline underline-offset-2 hover:text-ink" onClick={() => set({ view: 'about' })}>
          {t('nav.about')}
        </button>
      </p>
    </footer>
  )
}

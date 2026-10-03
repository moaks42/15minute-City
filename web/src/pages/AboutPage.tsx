import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useMeta } from '@/api/hooks'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { CREDITS, SOURCES } from '@/content/sources'
import { locale } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useApp } from '@/state/store'

const STATUS_CLS = { ok: 'bg-[#e3f3e8] text-good', fallback: 'bg-[#fdf3dc] text-warn', missing: 'bg-[#fbe4e2] text-bad' }

export function AboutPage() {
  const { t } = useTranslation()
  const { city, lang, set } = useApp()
  const { data: meta, isPending, isError, refetch } = useMeta(city)
  const method = t('about.method', { returnObjects: true }) as string[]
  const limits = t('about.limits', { returnObjects: true }) as string[]
  const date = (s?: string) => (s ? new Date(s).toLocaleDateString(locale(lang)) : '–')

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="min-h-0 flex-1 overflow-y-auto">
        <article className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
          <Button variant="ghost" size="sm" onClick={() => set({ view: 'app' })} className="-ml-2 mb-4">
            <ArrowLeft size={16} /> {t('about.back')}
          </Button>
          <h1 className="font-display text-4xl font-bold tracking-tight">{t('about.title')}</h1>
          <p className="mt-3 text-lg text-ink-2">{t('about.lead')}</p>

          <h2 className="mt-10 font-display text-2xl font-semibold">{t('about.sources', { city: t(`cities.${city}`) })}</h2>
          {isPending && <p className="mt-3 text-ink-3">{t('states.loading')}</p>}
          {isError && (
            <p className="mt-3" role="alert">
              {t('states.error')}{' '}
              <button className="underline" onClick={() => refetch()}>
                {t('states.retry')}
              </button>
            </p>
          )}
          {meta && (
            <div className="mt-4 overflow-x-auto rounded-2xl border border-line bg-surface">
              <table className="w-full text-sm" data-testid="manifest">
                <thead className="bg-sunken text-left text-ink-2">
                  <tr>
                    <th className="px-3 py-2 font-medium">{t('about.table.source')}</th>
                    <th className="px-3 py-2 font-medium">{t('about.table.licence')}</th>
                    <th className="px-3 py-2 font-medium">{t('about.table.fetched')}</th>
                    <th className="px-3 py-2 font-medium">{t('about.table.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {meta.manifest.map((m) => {
                    const s = SOURCES[m.key]
                    const url = m.url ?? s?.url
                    return (
                      <tr key={m.key} className="border-t border-line align-top">
                        <td className="px-3 py-2">
                          {url ? (
                            <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
                              {s?.name ?? m.key} <ExternalLink size={12} />
                            </a>
                          ) : (
                            <span className="font-medium">{s?.name ?? m.key}</span>
                          )}
                          {m.note && <p className="text-xs text-ink-3">{m.note}</p>}
                        </td>
                        <td className="px-3 py-2 text-ink-2">{m.licence ?? s?.licence ?? '–'}</td>
                        <td className="px-3 py-2 tabular-nums text-ink-2">{date(m.fetchedAt)}</td>
                        <td className="px-3 py-2">
                          <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', STATUS_CLS[m.status])}>{t(`about.status.${m.status}`)}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="mt-10 font-display text-2xl font-semibold">{t('about.methodTitle')}</h2>
          <div className="mt-3 space-y-3 leading-relaxed text-ink-2">
            {method.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>

          <h2 className="mt-10 font-display text-2xl font-semibold">{t('about.safetyTitle')}</h2>
          <p className="mt-3 rounded-2xl border-l-4 border-sun bg-surface p-4 leading-relaxed text-ink-2" data-testid="safety-caveat">
            {t('about.safety')}
          </p>

          <h2 className="mt-10 font-display text-2xl font-semibold">{t('about.limitsTitle')}</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed text-ink-2">
            {limits.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>

          <h2 className="mt-10 font-display text-2xl font-semibold">{t('about.attribution')}</h2>
          <p className="mt-3 text-ink-2">{t('footer.attribution')}</p>
          <p className="mt-1 text-ink-2">{t('footer.sources', { sources: [...new Set([...CREDITS.krakow, ...CREDITS.praha])].join(', ') })}</p>
          <p className="mt-6 text-sm text-ink-3">
            {t('app.privacy')} · {t('footer.team')}
          </p>
        </article>
      </main>
    </div>
  )
}

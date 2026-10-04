import { useQuery } from '@tanstack/react-query'
import { useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { CityId } from '@/api/types'
import { fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'
import { EMPTY_FILTERS, searchState, urlFromState, useApp } from '@/state/store'
import { personaRequest, usePersonas } from './shared'

/** `pos`: CSS object-position, so the crop keeps the landmark in view. */
type Photo = { file: string; key: string; pos?: string }
type Collection = { id: 'family' | 'student' | 'senior'; city: CityId; persona: string; photos: [Photo, Photo, Photo] }

// Photos live in web/public/images/collections/ (big photo first, then the two small ones),
// resized from the originals to at most 1400 px (big) / 900 px (small) on the long edge.
// TODO(photo credits): before going public, every file below needs its author, licence and
// source URL filled in here, and the credits shown on the About page. Use only photos whose
// licence allows reuse (your own, CC0, CC BY, CC BY-SA with attribution).
const COLLECTIONS: Collection[] = [
  {
    id: 'family',
    city: 'krakow',
    persona: 'parent',
    photos: [
      { file: 'krakow-wawel-boulevards.jpg', key: 'wawel', pos: '70% 55%' }, // TODO credit: author · licence · source URL
      { file: 'krakow-tram-greenery.jpg', key: 'tramGreenery' }, // TODO credit: author · licence · source URL
      { file: 'krakow-tram-street.jpg', key: 'tramStreet', pos: '45% 50%' }, // TODO credit: author · licence · source URL
    ],
  },
  {
    id: 'student',
    city: 'krakow',
    persona: 'student',
    photos: [
      { file: 'krakow-main-square.jpg', key: 'mainSquare' }, // TODO credit: author · licence · source URL
      { file: 'krakow-town-hall-sunset.jpg', key: 'townHall', pos: '45% 50%' }, // TODO credit: author · licence · source URL
      { file: 'krakow-cafe-terrace.jpg', key: 'cafeTerrace', pos: '50% 80%' }, // TODO credit: author · licence · source URL
    ],
  },
  {
    id: 'senior',
    city: 'praha',
    persona: 'senior',
    photos: [
      { file: 'praha-charles-bridge.jpg', key: 'charlesBridge', pos: '70% 50%' }, // TODO credit: author · licence · source URL
      { file: 'praha-park-museum-view.jpg', key: 'parkView', pos: '50% 70%' }, // TODO credit: author · licence · source URL
      { file: 'praha-cafe.jpg', key: 'cafe', pos: '50% 45%' }, // TODO credit: author · licence · source URL
    ],
  },
]

/** Shown behind each photo, and instead of it until the file exists. */
const PLACEHOLDER: Record<CityId, string> = {
  krakow: 'linear-gradient(135deg,#17766F 0%,#1D5F70 100%)',
  praha: 'linear-gradient(135deg,#7b2d43 0%,#3D3A6B 100%)',
}

function PhotoTile({ photo, city, className }: { photo: Photo; city: CityId; className?: string }) {
  const { t } = useTranslation()
  const [ok, setOk] = useState(true)
  const caption = t(`welcome.photo.${photo.key}`)
  return (
    <figure className={cn('relative overflow-hidden', className)} style={{ background: PLACEHOLDER[city] }}>
      {ok && (
        <img
          src={`/images/collections/${photo.file}`}
          alt={caption}
          loading="lazy"
          onError={() => setOk(false)}
          style={{ objectPosition: photo.pos }}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
        />
      )}
      <figcaption aria-hidden className="absolute bottom-2 left-2 max-w-[calc(100%-1rem)] rounded-lg bg-black/60 px-2 py-1 text-[11px] font-medium leading-tight text-white backdrop-blur-sm line-clamp-2">
        {caption}
      </figcaption>
    </figure>
  )
}

function CollectionCard({ c }: { c: Collection }) {
  const { t } = useTranslation()
  const app = useApp()
  const persona = usePersonas(c.city).find((p) => p.id === c.persona)
  // Live ranking for the persona alone: the same numbers the results open with.
  const top = useQuery({
    queryKey: ['collection', c.city, c.persona],
    queryFn: () => api.score(c.city, personaRequest(app.lang, persona!, 3, false)),
    enabled: !!persona,
    staleTime: Infinity,
  })
  const target = persona && searchState(c.city, persona.id, persona.weights, EMPTY_FILTERS)
  const open = (e: MouseEvent) => {
    if (!target || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return // new tab etc.
    e.preventDefault()
    app.set(target)
  }
  const [big, ...small] = c.photos

  return (
    <article className="group relative flex flex-col overflow-hidden rounded-3xl border border-line bg-surface shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-pop)] has-[a:focus-visible]:outline-3 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-accent">
      <div className="grid h-52 grid-cols-[1.7fr_1fr] grid-rows-2 gap-1 sm:h-56">
        <PhotoTile photo={big} city={c.city} className="row-span-2" />
        {small.map((p) => (
          <PhotoTile key={p.key} photo={p} city={c.city} />
        ))}
      </div>
      <span className="absolute left-3 top-3 rounded-full bg-white px-3 py-1 text-xs font-semibold text-ink shadow-sm">{t(`cities.${c.city}`)}</span>
      <div className="flex flex-1 flex-col p-5">
        <h3 className="font-display text-xl font-bold tracking-tight">
          {/* The title is the link; it stretches over the whole card. */}
          <a
            href={target ? urlFromState({ ...app, ...target }) : undefined}
            onClick={open}
            className="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
            data-testid={`collection-${c.id}`}
          >
            {t(`welcome.collection.${c.id}.title`)}
          </a>
        </h3>
        <p className="mt-1 text-sm text-ink-3">{t(`welcome.collection.${c.id}.desc`)}</p>
        <ol className="mt-4 space-y-1.5" aria-label={t('welcome.topPlaces')} aria-busy={top.isPending}>
          {top.data
            ? top.data.top.slice(0, 3).map((p) => (
                <li key={p.id} className="flex items-baseline justify-between gap-3 text-[15px]">
                  <span className="truncate">{p.name}</span>
                  <span className="shrink-0 font-semibold tabular-nums text-accent">{fmtPct(p.score, app.lang)}</span>
                </li>
              ))
            : top.isError
              ? <li className="text-sm text-ink-3">{t('states.error')}</li>
              : [0, 1, 2].map((i) => <li key={i} className="h-[22px] animate-pulse rounded-md bg-sunken" />)}
        </ol>
      </div>
    </article>
  )
}

export function Collections() {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="collections-title" className="mt-12 sm:mt-16">
      <h2 id="collections-title" className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
        {t('welcome.collections')}
      </h2>
      <div className="mt-5 grid gap-5 md:grid-cols-3 md:gap-6">
        {COLLECTIONS.map((c) => (
          <CollectionCard key={c.id} c={c} />
        ))}
      </div>
    </section>
  )
}

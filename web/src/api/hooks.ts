import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api } from './client'
import type { CityId, CriterionId, Mode, ScoreRequest } from './types'
import { CRITERIA } from './types'
import { useApp } from '@/state/store'
import { STATIC_FALLBACK } from '@/lib/env'

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export const useCities = () => useQuery({ queryKey: ['cities'], queryFn: api.cities, staleTime: Infinity })

/** /meta labels are {pl,cs,en}, so a language switch needs no refetch. */
export function useMeta(city: CityId | null) {
  return useQuery({ queryKey: ['meta', city], queryFn: () => api.meta(city!, 'en'), enabled: !!city, staleTime: Infinity, placeholderData: keepPreviousData })
}

export const useGrid = (city: CityId | null) =>
  useQuery({ queryKey: ['grid', city], queryFn: () => api.grid(city!), enabled: !!city, staleTime: Infinity })

/** The /score request built from the current state. */
export function useScoreRequest(aggregate: ScoreRequest['aggregate'] = 'hex'): ScoreRequest {
  const { lang, persona, weights, anchors, filters, budget, city } = useApp()
  return useMemo(
    () => ({
      v: 1 as const,
      lang,
      persona: persona ?? 'custom',
      weights,
      anchors,
      filters,
      budget: city === 'krakow' ? { total: budget } : { monthlyRent: budget },
      aggregate,
      limit: 20,
      includeCells: aggregate === 'hex',
    }),
    [lang, persona, weights, anchors, filters, budget, city, aggregate],
  )
}

export function useScore(aggregate: ScoreRequest['aggregate'] = 'hex', enabled = true) {
  const city = useApp((s) => s.city)
  const req = useDebounced(useScoreRequest(aggregate), 250)
  return useQuery({
    queryKey: ['score', city, req],
    queryFn: () => api.score(city!, req),
    enabled: !!city && enabled,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

/** Single-criterion map mode: /score with only that criterion weighted
 *  returns exactly its 0–100 score per cell. */
export function useCriterionScore(criterion: CriterionId | null) {
  const { city, lang, persona } = useApp()
  const req: ScoreRequest | null = criterion
    ? {
        v: 1,
        lang,
        persona: persona ?? 'custom',
        weights: Object.fromEntries(CRITERIA.map((c) => [c, c === criterion ? 5 : 0])),
        anchors: [],
        filters: { mustHave: [] },
        aggregate: 'hex',
        limit: 1,
        includeCells: true,
      }
    : null
  return useQuery({
    queryKey: ['critScore', city, req],
    queryFn: () => api.score(city!, req!),
    enabled: !!city && !!req,
    staleTime: Infinity,
  })
}

export function usePlace(h3: string | null) {
  const city = useApp((s) => s.city)
  const req = useDebounced(useScoreRequest('hex'), 250)
  return useQuery({
    queryKey: ['place', city, h3, req],
    queryFn: () => api.place(city!, h3!, { ...req, includeCells: false }),
    enabled: !!city && !!h3,
    placeholderData: (prev, q) => (q?.queryKey[2] === h3 ? prev : undefined),
  })
}

export function useSimilar(h3: string | null) {
  const city = useApp((s) => s.city)
  return useQuery({ queryKey: ['similar', city, h3], queryFn: () => api.similar(city!, h3!), enabled: !!city && !!h3 && !STATIC_FALLBACK, staleTime: Infinity })
}

export function useCommute(lat?: number, lon?: number, mode?: Mode) {
  const city = useApp((s) => s.city)
  return useQuery({
    queryKey: ['commute', city, lat, lon, mode],
    queryFn: () => api.commute(city!, lat!, lon!, mode!),
    enabled: !!city && lat != null && lon != null && !!mode && !STATIC_FALLBACK,
    staleTime: Infinity,
  })
}

export function useTwins(h3: string | null) {
  const { city, lang } = useApp()
  const to: CityId = city === 'krakow' ? 'praha' : 'krakow'
  return useQuery({
    queryKey: ['twins', city, h3, to, lang],
    queryFn: () => api.twins(city!, h3!, to, lang),
    enabled: !!city && !!h3 && !STATIC_FALLBACK,
    staleTime: Infinity,
  })
}

export function useAir(lat?: number, lon?: number) {
  const city = useApp((s) => s.city)
  return useQuery({
    queryKey: ['air', city, lat?.toFixed(2), lon?.toFixed(2)],
    queryFn: () => api.air(city!, lat!, lon!),
    enabled: !!city && lat != null && !STATIC_FALLBACK,
    staleTime: 10 * 60_000,
    retry: false,
  })
}

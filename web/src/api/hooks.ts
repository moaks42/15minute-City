import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api } from './client'
import type { CityId, Mode, ScoreRequest } from './types'
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

export function useMeta(city: CityId | null) {
  const lang = useApp((s) => s.lang)
  return useQuery({ queryKey: ['meta', city, lang], queryFn: () => api.meta(city!, lang), enabled: !!city, staleTime: Infinity, placeholderData: keepPreviousData })
}

export const useGrid = (city: CityId | null) =>
  useQuery({ queryKey: ['grid', city], queryFn: () => api.grid(city!), enabled: !!city, staleTime: Infinity })

/** The /score request built from the current state. */
export function useScoreRequest(aggregate: 'hex' | 'district' = 'hex'): ScoreRequest {
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
    }),
    [lang, persona, weights, anchors, filters, budget, city, aggregate],
  )
}

export function useScore(aggregate: 'hex' | 'district' = 'hex', enabled = true) {
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

export function usePlace(h3: string | null) {
  const city = useApp((s) => s.city)
  const req = useDebounced(useScoreRequest('hex'), 250)
  return useQuery({
    queryKey: ['place', city, h3, req],
    queryFn: () => api.place(city!, h3!, req),
    enabled: !!city && !!h3,
    placeholderData: (prev, q) => (q?.queryKey[2] === h3 ? prev : undefined),
  })
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

export const useCriteriaScores = (city: CityId | null) =>
  useQuery({ queryKey: ['critScores', city], queryFn: () => api.criteriaScores(city!), enabled: !!city, staleTime: Infinity })

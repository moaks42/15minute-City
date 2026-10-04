import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { api } from './client'
import type { CityId, CriterionId, Mode, ScoreRequest, ScoreResponse } from './types'
import { CRITERIA } from './types'
import { activeAnchor, useApp } from '@/state/store'
import { STATIC_FALLBACK } from '@/lib/env'
import { quantileBreaks } from '@/lib/palette'

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

/** How `top` is ordered (null = match %) and, for places, the one district they must lie in. */
export type RankOpts = { rankBy?: string | null; district?: string | null }

/** The /score request built from the current state. Without opts it is exactly
 *  the map's request, so the map and the match ranking share one query. */
export function useScoreRequest(aggregate: ScoreRequest['aggregate'] = 'hex', { rankBy, district }: RankOpts = {}): ScoreRequest {
  const { lang, persona, weights, anchors, filters, budget, city } = useApp()
  return useMemo(
    () => ({
      v: 1 as const,
      lang,
      persona: persona ?? 'custom',
      weights,
      anchors: anchors.map(({ address: _address, ...a }) => a), // the address is UI-only
      filters,
      budget: city === 'krakow' ? { total: budget } : { monthlyRent: budget },
      aggregate,
      limit: aggregate === 'hex' ? 20 : 100, // every district, so any of them can open its detail
      includeCells: aggregate === 'hex' && !rankBy && !district,
      ...(rankBy ? { rankBy } : {}),
      ...(district ? { district } : {}),
    }),
    [lang, persona, weights, anchors, filters, budget, city, aggregate, rankBy, district],
  )
}

export function useScore(aggregate: ScoreRequest['aggregate'] = 'hex', enabled = true, opts: RankOpts = {}) {
  const city = useApp((s) => s.city)
  const req = useDebounced(useScoreRequest(aggregate, opts), 250)
  return useQuery({
    queryKey: ['score', city, req],
    queryFn: () => api.score(city!, req),
    enabled: !!city && enabled,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

/** Nothing the ranking can use is rated: every topic skipped, or only the
 *  commute without places. The engine then falls back to equal weights, which
 *  is not the user's ranking, so the UI shows a neutral state instead. */
export function noEffectiveWeights(res: ScoreResponse | undefined): boolean {
  if (!res) return false
  return !Object.entries(res.weightsUsed).some(([c, level]) => level > 0 && !res.excludedCriteria.includes(c as CriterionId))
}

export function useNoEffectiveWeights(): boolean {
  return noEffectiveWeights(useScore('hex').data)
}

/** What the results are ordered by: the map lens. null = match % (also for the commute lens without a place). */
export function useRankBy(): string | null {
  const mapMode = useApp((s) => s.mapMode)
  const anchorId = useApp((s) => activeAnchor(s)?.id)
  if (mapMode === 'match') return null
  if (mapMode === 'commute') return anchorId ? `anchor:${anchorId}` : null
  return mapMode
}

/** The ranking the results list, its map markers and the district detail show. */
export function useRanking(aggregate: 'hex' | 'district', enabled = true) {
  return useScore(aggregate, enabled, { rankBy: useRankBy() })
}

/** Quantile classes of the match map; the score badges use them too, so a
 *  place's badge has the same colour as its hexagon. */
export function useMatchBreaks(): number[] {
  const score = useScore('hex')
  return useMemo(() => quantileBreaks((score.data?.cells ?? []).filter((c) => c[2] === 1).map((c) => c[1])), [score.data])
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

/** Colour classes of what the map shows (match % or one criterion), so a badge
 *  has the colour of its hexagon in every lens. */
export function useLensBreaks(): number[] {
  const mapMode = useApp((s) => s.mapMode)
  const crit = mapMode !== 'match' && mapMode !== 'commute' ? mapMode : null
  const match = useMatchBreaks()
  const critScores = useCriterionScore(crit)
  return useMemo(() => {
    if (mapMode === 'match') return match
    // A criterion-only request has no filters, so "passes" means habitable.
    if (crit && critScores.data) return quantileBreaks(critScores.data.cells.filter((c) => c[2] === 1).map((c) => c[1]))
    return quantileBreaks([])
  }, [mapMode, crit, match, critScores.data])
}

/** The lens the results follow: what orders them and the colour classes of their badges. */
export function useLens() {
  const rankBy = useRankBy()
  const breaks = useLensBreaks()
  return useMemo(() => ({ rankBy, breaks }), [rankBy, breaks])
}
export type Lens = ReturnType<typeof useLens>

/** District outlines (static file in every mode; ids = grid district_id). */
export const useDistrictShapes = (city: CityId | null) =>
  useQuery({ queryKey: ['districtShapes', city], queryFn: () => api.districtShapes(city!), enabled: !!city, staleTime: Infinity })

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

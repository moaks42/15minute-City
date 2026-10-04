import { useMeta } from '@/api/hooks'
import type { CityId, Lang, ScoreRequest } from '@/api/types'
import { DEFAULT_PERSONAS, type PersonaLite } from '@/content/defaults'
import { EMPTY_FILTERS } from '@/state/store'

/** Personas with their weights: /meta once loaded, the built-in copy until then (same values). */
export function usePersonas(city: CityId): PersonaLite[] {
  const { data: meta } = useMeta(city)
  return meta?.personas?.length ? meta.personas : DEFAULT_PERSONAS
}

/** /score for a persona alone (no places, no limits): what the welcome screen previews. */
export function personaRequest(lang: Lang, p: PersonaLite, limit: number, includeCells: boolean): ScoreRequest {
  return { v: 1, lang, persona: p.id, weights: p.weights, anchors: [], filters: EMPTY_FILTERS, aggregate: 'hex', limit, includeCells }
}

// UI fallbacks used until /meta has loaded (README §3.3, §3.4).
// The engine's /meta is the source of truth once available.
import type { Criterion, CriterionId, Persona, Weights } from '@/api/types'
import { CRITERIA } from '@/api/types'

export const CRITERION_EMOJI: Record<CriterionId, string> = {
  commute: '🧭',
  transit: '🚋',
  active: '🚲',
  green: '🌳',
  education: '🎓',
  family: '🧸',
  safety: '🛡️',
  price: '💰',
  shops: '🛒',
  health: '🏥',
  environment: '🌬️',
  leisure: '🎭',
  accessibility: '♿',
}

export const DEFAULT_CRITERIA: Criterion[] = CRITERIA.map((id) => ({ id, emoji: CRITERION_EMOJI[id], label: {}, indicators: [], coverage: 1 }))

const w = (a: number[]): Weights => Object.fromEntries(CRITERIA.map((c, i) => [c, a[i]])) as Weights

export const DEFAULT_PERSONAS: Persona[] = [
  { id: 'student', emoji: '🎒', label: {}, weights: w([5, 5, 3, 2, 1, 0, 3, 5, 3, 1, 2, 5, 0]) },
  { id: 'working', emoji: '💼', label: {}, weights: w([5, 4, 4, 3, 0, 0, 3, 4, 4, 2, 3, 4, 0]) },
  { id: 'parent', emoji: '👨‍👩‍👧', label: {}, weights: w([3, 3, 2, 5, 5, 5, 5, 3, 4, 4, 4, 1, 2]) },
  { id: 'expecting', emoji: '🤰', label: {}, weights: w([3, 4, 2, 4, 3, 4, 4, 3, 4, 5, 5, 1, 4]) },
  { id: 'senior', emoji: '🧓', label: {}, weights: w([1, 4, 3, 4, 0, 0, 5, 3, 5, 5, 4, 3, 5]) },
  { id: 'custom', emoji: '✏️', label: {}, weights: w([3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]) },
]

export const MUST_HAVE = ['nursery', 'kindergarten', 'primary_school', 'tram_stop', 'metro_station', 'park', 'pharmacy', 'gp_clinic', 'supermarket', 'maternity_ward']

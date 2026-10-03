// Colour-blind-safe palettes (README §3.8). Sequential ramps vary
// monotonically in lightness so they read in greyscale and for all CVD types.

/** Match % / criterion score, low → high (YlGnBu-like). */
export const SEQ = ['#f6f1df', '#d6ebc8', '#a3d6b4', '#64b9a9', '#2f979c', '#1b7389', '#1d4e6e']

/** Commute bands ≤10/20/30/45/60/>60 min, short = dark (BuPu reversed). */
export const COMMUTE_BANDS = [10, 20, 30, 45, 60] as const
export const COMMUTE = ['#6e1670', '#8856a7', '#8c96c6', '#9ebcda', '#c6d9ea', '#f1f4f8']

/** Archetypes: Okabe–Ito categorical. */
export const CATEGORICAL = ['#E69F00', '#56B4E9', '#009E73', '#D4C21F', '#0072B2', '#D55E00', '#CC79A7', '#7f7f7f']

export const FAILING = '#b8b2a8'
export const UNINHABITED = '#e9e5df'

export function seqColor(score: number) {
  const i = Math.max(0, Math.min(SEQ.length - 1, Math.floor((score / 100) * SEQ.length)))
  return SEQ[i]
}

/** Quantile class breaks (SEQ.length − 1 thresholds) so the map differentiates
 *  even when scores cluster; the legend prints the real values. */
export function quantileBreaks(values: number[]): number[] {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b)
  const fallback = SEQ.slice(1).map((_, i) => Math.round(((i + 1) * 100) / SEQ.length))
  if (v.length < SEQ.length * 3) return fallback
  const out: number[] = []
  for (let i = 1; i < SEQ.length; i++) {
    const q = v[Math.floor((i / SEQ.length) * (v.length - 1))]
    out.push(Math.max(q, (out[out.length - 1] ?? -1) + 0.5))
  }
  return out
}

/** MapLibre step expression over a feature-state value 0–100. */
export function seqExpression(stateKey: string, breaks: number[]): unknown[] {
  const stops: unknown[] = []
  SEQ.forEach((c, i) => {
    if (i > 0) stops.push(breaks[i - 1])
    stops.push(c)
  })
  return ['step', ['coalesce', ['feature-state', stateKey], -1], UNINHABITED, 0, ...stops]
}

export function commuteExpression(stateKey: string): unknown[] {
  return [
    'step',
    ['coalesce', ['feature-state', stateKey], 999],
    COMMUTE[0],
    COMMUTE_BANDS[0] + 0.5, COMMUTE[1],
    COMMUTE_BANDS[1] + 0.5, COMMUTE[2],
    COMMUTE_BANDS[2] + 0.5, COMMUTE[3],
    COMMUTE_BANDS[3] + 0.5, COMMUTE[4],
    COMMUTE_BANDS[4] + 0.5, COMMUTE[5],
    998, UNINHABITED,
  ]
}

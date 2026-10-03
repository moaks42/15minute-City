// App types = the shared contract (contracts/types.ts, generated from
// contracts/openapi.yaml by B) plus a few UI-side helpers.
import type * as C from '@contracts/types'

export type {
  AnchorTime,
  City,
  CityId,
  CommuteResponse,
  CriterionId,
  CriterionMeta,
  Explanation,
  Filters,
  I18nText,
  IndicatorMeta,
  IndicatorValue,
  Lang,
  LiveAir,
  Meta,
  Mode,
  MustHave,
  Persona,
  Place,
  RankedPlace,
  RelaxHint,
  ScoreRequest,
  ScoreResponse,
  SimilarPlace,
  SimilarResponse,
  StaticCriteriaScores,
  TwinsResponse,
  GeocodeResponse,
} from '@contracts/types'

/** App anchors always carry a label and a mode. */
export type Anchor = C.Anchor & { label: string; mode: C.Mode }

export type GeocodeHit = C.GeocodeResponse['items'][number]

export const CRITERIA = [
  'commute',
  'transit',
  'active',
  'green',
  'education',
  'family',
  'safety',
  'price',
  'shops',
  'health',
  'environment',
  'leisure',
  'accessibility',
] as const satisfies readonly C.CriterionId[]

/** Importance level 0–5 per criterion. */
export type Weights = Record<C.CriterionId, number>
export type Localized = string | Partial<Record<C.Lang, string>>

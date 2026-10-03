// Locale formatting (README §3.8): UI locale + city currency.
import type { CityId, Lang } from '@/api/types'
import archetypes from '@/content/archetypes.json'

const LOCALE: Record<Lang, string> = { pl: 'pl-PL', cs: 'cs-CZ', en: 'en-GB' }
export const locale = (l: Lang) => LOCALE[l]
export const CURRENCY: Record<CityId, 'PLN' | 'CZK'> = { krakow: 'PLN', praha: 'CZK' }

export const fmtNum = (v: number, lang: Lang, digits = 0) =>
  new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: digits }).format(v)

export function fmtMoney(v: number, lang: Lang, city: CityId) {
  return new Intl.NumberFormat(LOCALE[lang], {
    style: 'currency',
    currency: CURRENCY[city],
    maximumFractionDigits: 0,
    currencyDisplay: lang === 'en' ? 'code' : 'symbol',
  }).format(v)
}

const PER: Record<Lang, { buy: string; rent: string }> = {
  pl: { buy: '/m²', rent: '/m²/mies.' },
  cs: { buy: '/m²', rent: '/m²/měs.' },
  en: { buy: '/m²', rent: '/m²/month' },
}
/** "12 450 zł/m²" · "385 Kč/m²/měs." · "PLN 12,450/m²" */
export function fmtPricePerM2(v: number, lang: Lang, city: CityId) {
  return fmtMoney(v, lang, city) + PER[lang][city === 'krakow' ? 'buy' : 'rent']
}

export const collator = (l: Lang) => new Intl.Collator(LOCALE[l], { sensitivity: 'base' })
export const fold = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

type ArchetypeEntry = { color: number; label: Record<Lang, string>; desc: Record<Lang, string> }
const ARCH = archetypes as unknown as Record<string, ArchetypeEntry>
export function archetypeInfo(id: string, lang: Lang, fallback?: string) {
  const a = ARCH[id]
  return {
    label: a?.label[lang] ?? fallback ?? id,
    desc: a?.desc[lang] ?? '',
    color: a ? a.color : Math.abs([...id].reduce((h, c) => h * 31 + c.charCodeAt(0), 7)) % 8,
  }
}

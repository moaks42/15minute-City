import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Lang, Localized } from '@/api/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Resolve a label that may be a plain string or a {pl,cs,en} map. */
export function L(label: Localized | undefined, lang: Lang): string {
  if (!label) return ''
  if (typeof label === 'string') return label
  return label[lang] ?? label.en ?? label.pl ?? Object.values(label)[0] ?? ''
}

export function debounce<A extends unknown[]>(fn: (...a: A) => void, ms: number) {
  let t: ReturnType<typeof setTimeout> | undefined
  return (...a: A) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...a), ms)
  }
}

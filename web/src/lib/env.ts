const e = import.meta.env

export const API_URL: string = (e.VITE_API_URL ?? '').replace(/\/$/, '')
export const USE_FIXTURES = e.VITE_USE_FIXTURES === '1' || (!e.VITE_API_URL && e.VITE_STATIC_FALLBACK !== '1')
export const STATIC_FALLBACK = e.VITE_STATIC_FALLBACK === '1'

/** Data that isn't from the live engine is labelled in the UI. */
export const DATA_MODE: 'live' | 'fixtures' | 'static' = STATIC_FALLBACK ? 'static' : USE_FIXTURES ? 'fixtures' : 'live'

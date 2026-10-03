// Bookmarked places ("Saved" like in Google Maps), persisted in localStorage.
import { create } from 'zustand'
import type { CityId } from '@/api/types'

export interface SavedItem {
  city: CityId
  id: string
  kind: 'hex' | 'district'
  name: string
  lat: number
  lon: number
  savedAt: number
}

const KEY = 'kompas.saved.v1'

function load(): SavedItem[] {
  try {
    const raw = localStorage.getItem(KEY)
    const v = raw ? JSON.parse(raw) : []
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

function persist(items: SavedItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items))
  } catch {
    // storage unavailable (private mode, quota) – keep in memory only
  }
}

interface SavedState {
  items: SavedItem[]
  toggle: (item: Omit<SavedItem, 'savedAt'> & { savedAt?: number }) => void
  remove: (city: CityId, id: string) => void
}

export const useSaved = create<SavedState>((set, get) => ({
  items: load(),
  toggle: (item) => {
    const items = get().items
    const exists = items.some((x) => x.city === item.city && x.id === item.id)
    const next = exists ? items.filter((x) => !(x.city === item.city && x.id === item.id)) : [{ ...item, savedAt: item.savedAt ?? Date.now() }, ...items]
    persist(next)
    set({ items: next })
  },
  remove: (city, id) => {
    const next = get().items.filter((x) => !(x.city === city && x.id === id))
    persist(next)
    set({ items: next })
  },
}))

export const isSaved = (items: SavedItem[], city: CityId | null, id: string) => !!city && items.some((x) => x.city === city && x.id === id)

/** Reactive hook variant of isSaved. */
export const useIsSaved = (city: CityId | null, id: string) => useSaved((s) => isSaved(s.items, city, id))

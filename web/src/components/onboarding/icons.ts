import { Bike, Footprints, TramFront } from 'lucide-react'
import type { Mode } from '@/api/types'

export const LEVEL_EMOJI = ['', '😐', '🙂', '😊', '😍', '🤩']

export const MODE_ICON: Record<Mode, typeof TramFront> = { transit: TramFront, bike: Bike, walk: Footprints }

import { Popup } from 'react-map-gl/maplibre'

export type HoverInfo = { h3: string; lng: number; lat: number; name: string | null; district: string | null; districtId?: string | null; habitable: boolean }

/** Desktop-only card that follows the mouse over the hex map (pointer-events disabled, never steals hover). */
export function HoverCard({ info, value, note }: { info: HoverInfo; value?: string | null; note?: string | null }) {
  const title = info.name || info.district
  return (
    <Popup longitude={info.lng} latitude={info.lat} closeButton={false} closeOnClick={false} offset={12} maxWidth="260px" className="hover-card">
      <div className="text-xs leading-snug" data-testid="hover-card">
        {title && <p className="text-sm font-semibold text-ink">{title}</p>}
        {info.name && info.district && info.district !== info.name && <p className="text-ink-3">{info.district}</p>}
        {value && <p className="mt-1 font-semibold text-accent">{value}</p>}
        {note && <p className="text-ink-3">{note}</p>}
      </div>
    </Popup>
  )
}

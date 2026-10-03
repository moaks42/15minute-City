import { MapPin } from 'lucide-react'
import type { MapLayerMouseEvent, MapRef } from 'react-map-gl/maplibre'
import Map, { Layer, Marker, NavigationControl, Source } from 'react-map-gl/maplibre'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useCommute, useCriterionScore, useGrid, useScore } from '@/api/hooks'
import type { CityId } from '@/api/types'
import { commuteExpression, FAILING, quantileBreaks, seqExpression, UNINHABITED } from '@/lib/palette'
import { useApp } from '@/state/store'
import { HoverCard, type HoverInfo } from './HoverCard'
import { Legend } from './Legend'

const NOT_HAB = ['!', ['to-boolean', ['get', 'habitable']]]
const STYLE = 'https://tiles.openfreemap.org/styles/positron'
export const CITY_VIEW: Record<CityId, { lat: number; lon: number; zoom: number }> = {
  krakow: { lat: 50.06, lon: 19.94, zoom: 11.5 },
  praha: { lat: 50.08, lon: 14.44, zoom: 11 },
}

function hatchImage(): ImageData {
  const s = 8
  const c = document.createElement('canvas')
  c.width = c.height = s
  const g = c.getContext('2d')!
  g.strokeStyle = 'rgba(80,72,64,0.55)'
  g.lineWidth = 1.2
  g.beginPath()
  g.moveTo(0, s)
  g.lineTo(s, 0)
  g.moveTo(-2, 2)
  g.lineTo(2, -2)
  g.moveTo(s - 2, s + 2)
  g.lineTo(s + 2, s - 2)
  g.stroke()
  return g.getImageData(0, 0, s, s)
}

export default function MapView({ preview = false }: { preview?: boolean }) {
  const { t } = useTranslation()
  const { city, mapMode, anchors, commuteAnchor, sel, select, hover, set } = useApp()
  const mapRef = useRef<MapRef>(null)
  const [ready, setReady] = useState(false)
  const [beforeId, setBeforeId] = useState<string | undefined>()
  const [failed, setFailed] = useState(false)
  // Feature state can only be set once react-map-gl has added the source.
  const [srcLoaded, setSrcLoaded] = useState(false)
  const grid = useGrid(city)
  const score = useScore('hex')
  const anchor = anchors.find((a) => a.id === commuteAnchor) ?? anchors[0]
  const commute = useCommute(mapMode === 'commute' ? anchor?.lat : undefined, anchor?.lon, anchor?.mode)
  const critMode = mapMode !== 'match' && mapMode !== 'commute' ? mapMode : null
  const critScores = useCriterionScore(critMode)
  // Hover card: desktop pointers only (touch devices get no hover).
  const [canHover] = useState(() => window.matchMedia('(hover: hover)').matches)
  const [pointer, setPointer] = useState<HoverInfo | null>(null)

  const habitable = useMemo(() => {
    const s = new Set<string>()
    for (const f of grid.data?.features ?? []) {
      const p = f.properties as { h3: string; habitable?: number | boolean }
      if (p.habitable) s.add(p.h3)
    }
    return s
  }, [grid.data])

  // Per-cell values for the hover card (`Map` is the map component here, hence globalThis.Map).
  const scoreByCell = useMemo(() => new globalThis.Map((score.data?.cells ?? []).map(([id, s, pass]) => [id, { s, pass }] as const)), [score.data])
  const commuteByCell = useMemo(() => new globalThis.Map((commute.data?.cells ?? []).map(([id, m]) => [id, m] as const)), [commute.data])
  const critByCell = useMemo(() => new globalThis.Map((critScores.data?.cells ?? []).map(([id, v]) => [id, v] as const)), [critScores.data])
  const hoverText = useMemo((): { value: string; note: string | null } | null => {
    if (!pointer) return null
    if (!pointer.habitable) return { value: t('mapUi.hover.uninhabited'), note: null }
    const noData = { value: t('mapUi.hover.noData'), note: null }
    if (mapMode === 'match') {
      const v = scoreByCell.get(pointer.h3)
      return v ? { value: t('mapUi.hover.match', { value: v.s }), note: v.pass === 0 ? t('mapUi.hover.failing') : null } : noData
    }
    if (mapMode === 'commute') {
      if (!commute.data) return noData
      const m = commuteByCell.get(pointer.h3)
      return { value: m === undefined || m >= 255 ? t('map.over60') : t('map.minutes', { count: m }), note: null }
    }
    const v = critByCell.get(pointer.h3)
    return v == null || !critMode ? noData : { value: t('mapUi.hover.criterion', { criterion: t(`criteria.${critMode}`), value: Math.round(v) }), note: null }
  }, [pointer, mapMode, critMode, scoreByCell, commuteByCell, critByCell, commute.data, t])

  // Fly to the city when it changes.
  useEffect(() => {
    if (!city || !mapRef.current) return
    const v = CITY_VIEW[city]
    mapRef.current.flyTo({ center: [v.lon, v.lat], zoom: v.zoom, duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1400 })
  }, [city, ready])

  // Fly to a selected place.
  useEffect(() => {
    if (!sel || !mapRef.current || preview) return
    const f = grid.data?.features.find((x) => (x.properties as { h3: string }).h3 === sel)
    if (!f) return
    const ring = (f.geometry as GeoJSON.Polygon).coordinates[0]
    const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length
    const m = mapRef.current
    if (!m.getBounds().contains([lon, lat]) || m.getZoom() < 12.5) m.flyTo({ center: [lon, lat], zoom: Math.max(m.getZoom(), 13.2), duration: 900 })
  }, [sel, grid.data, preview])

  // Push scores into feature-state.
  useEffect(() => {
    const m = mapRef.current?.getMap()
    if (!ready || !srcLoaded || !m || !m.getSource('grid') || !grid.data) return
    for (const f of grid.data.features) {
      const id = (f.properties as { h3: string }).h3
      m.setFeatureState({ source: 'grid', id }, { score: null, pass: 1, minutes: null })
    }
    if (mapMode === 'match' && score.data) {
      for (const [id, s, pass] of score.data.cells) {
        if (!habitable.has(id)) continue
        m.setFeatureState({ source: 'grid', id }, { score: s, pass })
      }
    } else if (mapMode === 'commute' && commute.data) {
      for (const [id, minutes] of commute.data.cells) m.setFeatureState({ source: 'grid', id }, { minutes: minutes >= 255 ? 997 : minutes })
    } else if (critMode && critScores.data) {
      for (const [id, v] of critScores.data.cells) if (habitable.has(id)) m.setFeatureState({ source: 'grid', id }, { score: v })
    }
  }, [ready, srcLoaded, grid.data, score.data, commute.data, critScores.data, mapMode, critMode, habitable])

  // Hover highlight (shared with the ranking cards).
  const lastHover = useRef<string | null>(null)
  useEffect(() => {
    const m = mapRef.current?.getMap()
    if (!ready || !srcLoaded || !m?.getSource('grid')) return
    if (lastHover.current) m.setFeatureState({ source: 'grid', id: lastHover.current }, { hover: false })
    if (hover) m.setFeatureState({ source: 'grid', id: hover }, { hover: true })
    lastHover.current = hover
  }, [hover, ready, srcLoaded])

  const onLoad = useCallback(() => {
    const m = mapRef.current?.getMap()
    if (!m) return
    if (import.meta.env.DEV) (window as unknown as { __map: unknown }).__map = m
    m.on('sourcedata', (e) => {
      if (e.sourceId === 'grid' && e.isSourceLoaded) setSrcLoaded(true)
    })
    if (!m.hasImage('hatch')) m.addImage('hatch', hatchImage(), { pixelRatio: 1 })
    const firstSymbol = m.getStyle().layers?.find((l) => l.type === 'symbol')?.id
    setBeforeId(firstSymbol)
    setReady(true)
  }, [])

  const onClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const f = e.features?.[0]
      const id = f?.properties?.h3 as string | undefined
      if (id && habitable.has(id)) select(id)
    },
    [habitable, select],
  )

  const breaks = useMemo(() => {
    if (mapMode === 'match') return quantileBreaks((score.data?.cells ?? []).filter((c) => c[2] === 1).map((c) => c[1]))
    if (critMode && critScores.data) return quantileBreaks(critScores.data.cells.filter(([id]) => habitable.has(id)).map((c) => c[1]))
    return quantileBreaks([])
  }, [mapMode, critMode, score.data, critScores.data, habitable])

  const fillColor = useMemo(() => {
    if (mapMode === 'commute') return commuteExpression('minutes')
    const seq = seqExpression('score', breaks)
    if (mapMode === 'match') return ['case', ['==', ['feature-state', 'pass'], 0], FAILING, seq]
    return seq
  }, [mapMode, breaks])

  if (!city) return null
  const v = CITY_VIEW[city]
  const top = mapMode === 'match' && !preview ? (score.data?.top ?? []).slice(0, 10) : []

  return (
    <div className="absolute inset-0" data-testid="map">
      {failed && <div className="absolute inset-0 z-10 grid place-items-center bg-sunken text-ink-3">{t('map.error')}</div>}
      <Map
        ref={mapRef}
        initialViewState={{ latitude: v.lat, longitude: v.lon, zoom: v.zoom }}
        mapStyle={STYLE}
        onLoad={onLoad}
        onError={(e) => {
          if (!ready && String(e.error?.message ?? '').includes('style')) setFailed(true)
        }}
        interactiveLayerIds={preview ? [] : ['hex-fill']}
        onClick={preview ? undefined : onClick}
        onMouseMove={
          preview
            ? undefined
            : (e) => {
                const p = e.features?.[0]?.properties
                const id = (p?.h3 as string | undefined) ?? null
                set({ hover: id })
                if (!canHover) return
                setPointer(
                  id && p
                    ? { h3: id, lng: e.lngLat.lng, lat: e.lngLat.lat, name: (p.neighborhood as string) || null, district: (p.district_name as string) || null, habitable: !!p.habitable }
                    : null,
                )
              }
        }
        onMouseLeave={() => {
          set({ hover: null })
          setPointer(null)
        }}
        cursor={hover ? 'pointer' : 'grab'}
        attributionControl={{ compact: true }}
        style={{ width: '100%', height: '100%' }}
        dragRotate={false}
        touchPitch={false}
      >
        {!preview && <NavigationControl position="top-right" showCompass={false} />}
        {ready && grid.data && (
          <Source id="grid" type="geojson" data={grid.data} promoteId="h3">
            <Layer
              id="hex-fill"
              type="fill"
              beforeId={beforeId}
              paint={{
                'fill-color': ['case', NOT_HAB, UNINHABITED, fillColor] as never,
                'fill-opacity': ['case', NOT_HAB, 0.35, ['boolean', ['feature-state', 'hover'], false], 0.95, 0.72] as never,
              }}
            />
            <Layer
              id="hex-hatch"
              type="fill"
              beforeId={beforeId}
              paint={{
                'fill-pattern': 'hatch',
                'fill-opacity': (mapMode === 'match' ? ['case', ['==', ['feature-state', 'pass'], 0], 1, 0] : 0) as never,
              }}
            />
            <Layer
              id="hex-line"
              type="line"
              beforeId={beforeId}
              paint={{ 'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0, 13, 0.4, 15, 1] as never, 'line-opacity': 0.6 }}
            />
            <Layer id="hex-sel" type="line" filter={['==', ['get', 'h3'], sel ?? '']} paint={{ 'line-color': '#1f1d1a', 'line-width': 3 }} />
          </Source>
        )}
        {top.map((p) => (
          <Marker key={p.id} latitude={p.centroid.lat} longitude={p.centroid.lon} anchor="center">
            <button
              onClick={() => select(p.id)}
              onMouseEnter={() => set({ hover: p.id })}
              onMouseLeave={() => set({ hover: null })}
              aria-label={t('results.openDetail', { name: p.name })}
              className={`grid h-7 w-7 place-items-center rounded-full border-2 border-white text-xs font-bold shadow-md ${sel === p.id ? 'bg-ink text-white' : 'bg-accent text-white'}`}
            >
              {p.rank}
            </button>
          </Marker>
        ))}
        {!preview && canHover && pointer && hoverText && <HoverCard info={pointer} value={hoverText.value} note={hoverText.note} />}
        {!preview &&
          anchors.map((a) => (
            <Marker key={a.id} latitude={a.lat} longitude={a.lon} anchor="bottom">
              <div className="flex flex-col items-center" title={a.label}>
                <span className="mb-0.5 max-w-32 truncate rounded-full bg-ink px-2 py-0.5 text-[11px] font-semibold text-white shadow">{a.label}</span>
                <MapPin size={30} className="fill-sun text-ink drop-shadow" />
              </div>
            </Marker>
          ))}
      </Map>
      {!preview && <Legend commuteLabel={anchor?.label} breaks={breaks} />}
    </div>
  )
}

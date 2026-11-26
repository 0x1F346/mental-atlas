import { select } from 'd3-selection'
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from 'd3-zoom'
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, MouseEvent, RefObject } from 'react'

import { Icon, typeIcon } from '../icons'
import {
  AREA_COLOURS,
  fadeOf,
  labelColour,
  landmarkDiameter,
  landmarkLabel,
  newestMention,
  orbOpacity,
  prominentIds,
  typeColour,
} from './appearance'
import { insetPolygon, myceliumPaths, namePosition, outlinePath, softenPolygon, strand } from './tissue'
import type { Landmark, MapRendererProps, RelationshipLine } from './types'

type Point = [number, number]

/** At or above this zoom no landmark is drawn as a dot. */
export const DETAIL_ZOOM = 1.8
/** Labels shown at the fitted view; the number doubles with every √2 of zoom. */
const BASE_LABELS = 12

/** How many of the largest landmarks carry a label at this zoom. */
export function labelLimit(zoomLevel: number): number {
  const steps = Math.max(0, Math.floor(Math.log2(Math.max(zoomLevel, 1)) * 2 + 1e-9))
  return BASE_LABELS * 2 ** steps
}
const MIN_ZOOM = 0.6
const MAX_ZOOM = 6
const ZOOM_STEP = 1.4
/** Room left around the map when it fits the frame: the filters sit on top, the legend below. */
const FIT_PADDING = { top: 120, bottom: 72, side: 24 }
/** Before the frame has been measured (and in tests). */
const FALLBACK_SIZE = { width: 1000, height: 800 }
const SELF_DIAMETER = 44
/** Membrane insets, as a share of the map size. */
const OUTER_INSET = 0.006
const INNER_INSET = 0.014
/** Relationship types drawn as tension: dashed coral, no glow. */
const TENSION_TYPES = new Set(['CONFLICTS_WITH'])
const BREATHS = ['7s', '9s', '11s']

export function relationshipName(from: Landmark, line: RelationshipLine, to: Landmark): string {
  const verb = line.type.replaceAll('_', ' ').toLowerCase()
  return `Relationship: ${from.name} ${verb} ${to.name}${line.isHypothesis ? ' (hypothesis)' : ''}`
}

function useFrameSize(ref: RefObject<HTMLDivElement | null>) {
  const [size, setSize] = useState(FALLBACK_SIZE)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () => {
      const width = element.clientWidth
      const height = element.clientHeight
      if (width > 0 && height > 0) {
        setSize((previous) =>
          previous.width === width && previous.height === height ? previous : { width, height },
        )
      }
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return size
}

interface LandmarkProps {
  mark: Landmark
  scale: number
  selected: boolean
  labelled: boolean
  /** Zoomed out, landmarks without a label are drawn as small dots. */
  compact: boolean
  fade: number
  index: number
  onSelect: (id: string) => void
}

/** One landmark: an orb with its type icon, outlined by status, sized by evidence, faded by age. */
const LandmarkButton = memo(function LandmarkButton({
  mark,
  scale,
  selected,
  labelled,
  compact,
  fade,
  index,
  onSelect,
}: LandmarkProps) {
  const full = mark.is_self ? SELF_DIAMETER : landmarkDiameter(mark.evidence_count)
  const diameter = compact ? Math.round(10 + (full - 28) * 0.2) : full
  const style = {
    left: `${mark.x * scale}px`,
    top: `${mark.y * scale}px`,
    '--d': `${diameter}px`,
    '--c': mark.is_self ? 'var(--accent)' : typeColour(mark.type),
    '--o': mark.is_self ? 1 : orbOpacity(fade),
    '--label': mark.is_self ? 'var(--text)' : labelColour(fade),
    '--breath': BREATHS[index % BREATHS.length],
    '--delay': `${-((index * 1.7) % 11).toFixed(1)}s`,
  } as CSSProperties
  const label = landmarkLabel(mark)
  return (
    <button
      type="button"
      className={`lm status-${mark.status}${selected ? ' selected' : ''}${mark.is_self ? ' self' : ''}${compact ? ' compact' : ''}`}
      style={style}
      aria-label={label}
      aria-pressed={selected}
      title={label}
      data-x={mark.x}
      data-y={mark.y}
      data-area={mark.life_area}
      onClick={() => onSelect(mark.id)}
    >
      {selected && <span className="halo" aria-hidden="true" />}
      <span className="orb" aria-hidden="true">
        {!compact && <Icon name={typeIcon(mark.type)} size={Math.round(diameter * 0.42)} />}
      </span>
      {labelled && (
        <span className="lm-label" aria-hidden="true">
          {mark.name}
          {selected && mark.is_hypothesis && <span className="lm-hypothesis">Hypothesis</span>}
        </span>
      )}
    </button>
  )
})

/**
 * The map in SVG and HTML (D-024): six life-area regions drawn from the stored polygons as
 * membranes, landmarks as buttons at their saved positions, and the selected landmark's
 * relationships as glowing strands. d3-zoom pans and zooms; landmarks keep their size.
 */
export default function SvgMapRenderer({
  document: map,
  hiddenIds,
  selectedNodeId,
  selectedEdgeId,
  lines,
  onSelectNode,
  onSelectEdge,
}: MapRendererProps) {
  const frameRef = useRef<HTMLDivElement>(null)
  const regionsRef = useRef<SVGGElement>(null)
  const strandsRef = useRef<SVGGElement>(null)
  const layerRef = useRef<HTMLDivElement>(null)
  const zoomRef = useRef<ZoomBehavior<HTMLDivElement, unknown> | null>(null)
  const transformRef = useRef<ZoomTransform>(zoomIdentity)
  const [zoomLevel, setZoomLevel] = useState(1)
  const frame = useFrameSize(frameRef)

  // Map units to layer pixels, and where the map sits when it fits the frame.
  const roomWide = Math.max(frame.width - 2 * FIT_PADDING.side, 200)
  const roomHigh = Math.max(frame.height - FIT_PADDING.top - FIT_PADDING.bottom, 200)
  const scale = Math.min(roomWide, roomHigh) / map.size
  const fit = useMemo(
    () =>
      zoomIdentity.translate(
        (frame.width - map.size * scale) / 2,
        FIT_PADDING.top + Math.max(0, (roomHigh - map.size * scale) / 2),
      ),
    [frame.width, roomHigh, map.size, scale],
  )

  const apply = useCallback(
    (transform: ZoomTransform) => {
      transformRef.current = transform
      const svgTransform = `translate(${transform.x},${transform.y}) scale(${transform.k * scale})`
      regionsRef.current?.setAttribute('transform', svgTransform)
      strandsRef.current?.setAttribute('transform', svgTransform)
      const layer = layerRef.current
      if (layer) {
        layer.style.transform = `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`
        layer.style.setProperty('--k', String(transform.k))
      }
      setZoomLevel(Math.round(transform.k * 100) / 100)
    },
    [scale],
  )

  useEffect(() => {
    const element = frameRef.current
    if (!element) return
    const behaviour = zoom<HTMLDivElement, unknown>()
      .scaleExtent([MIN_ZOOM, MAX_ZOOM])
      .on('zoom', (event: { transform: ZoomTransform }) => apply(event.transform))
    zoomRef.current = behaviour
    select(element).call(behaviour).on('dblclick.zoom', null)
    select(element).call(behaviour.transform, fit)
    return () => {
      select(element).on('.zoom', null)
    }
  }, [apply, fit])

  const zoomBy = (factor: number) => {
    const element = frameRef.current
    if (element && zoomRef.current) zoomRef.current.scaleBy(select(element), factor)
  }
  const fitView = () => {
    const element = frameRef.current
    if (element && zoomRef.current) select(element).call(zoomRef.current.transform, fit)
  }

  const visible = useMemo(() => map.landmarks.filter((mark) => !hiddenIds.has(mark.id)), [map.landmarks, hiddenIds])
  const byId = useMemo(() => new Map(map.landmarks.map((mark) => [mark.id, mark])), [map.landmarks])
  const selected = selectedNodeId ? byId.get(selectedNodeId) : undefined
  const shownLines = useMemo(
    () =>
      selected
        ? lines.flatMap((line) => {
            const other = byId.get(line.otherId)
            return other && !hiddenIds.has(other.id) ? [{ line, other }] : []
          })
        : [],
    [selected, lines, byId, hiddenIds],
  )
  const newest = useMemo(() => newestMention(map.landmarks), [map.landmarks])
  const limit = labelLimit(zoomLevel)
  const prominent = useMemo(() => prominentIds(visible.filter((mark) => !mark.is_self), limit), [visible, limit])
  const detailed = zoomLevel >= DETAIL_ZOOM
  const neighbours = useMemo(() => new Set(shownLines.map(({ other }) => other.id)), [shownLines])

  // Bring a landmark chosen elsewhere (the panel, the keyboard) into view if it is off-screen.
  useEffect(() => {
    const element = frameRef.current
    if (!selected || !element || !zoomRef.current) return
    const [x, y] = transformRef.current.apply([selected.x * scale, selected.y * scale])
    const margin = 60
    if (x < margin || y < margin || x > frame.width - margin || y > frame.height - margin) {
      zoomRef.current.translateTo(select(element), selected.x * scale, selected.y * scale)
    }
  }, [selected, scale, frame.width, frame.height])

  const regions = useMemo(
    () =>
      map.regions.map((region) => {
        const points = softenPolygon(region.polygon as Point[])
        return {
          region,
          colour: AREA_COLOURS[region.key],
          outer: outlinePath(insetPolygon(points, map.size * OUTER_INSET)),
          inner: outlinePath(insetPolygon(points, map.size * INNER_INSET)),
          name: namePosition(region, map.size),
        }
      }),
    [map.regions, map.size],
  )
  const mycelium = useMemo(() => myceliumPaths(map.regions, map.size), [map.regions, map.size])

  function clearOnBackground(event: MouseEvent<HTMLDivElement>) {
    const target = event.target as Element
    if (!target.closest('button, [role="button"]')) onSelectNode(null)
  }

  function onFrameKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape' && selectedNodeId) onSelectNode(null)
  }

  return (
    <div
      ref={frameRef}
      className="map-frame tissue"
      role="group"
      aria-label="Map of your atlas"
      onClick={clearOnBackground}
      onKeyDown={onFrameKey}
    >
      <svg className="map-svg" aria-hidden="true">
        <g ref={regionsRef}>
          <g>
            {mycelium.map((d, index) => (
              <path key={index} d={d} className="myc" />
            ))}
          </g>
          {regions.map(({ region, colour, outer, inner }) => (
            <g key={region.key} className="region" data-area={region.key} style={{ color: colour }}>
              <path d={outer} className="region-glow" />
              <path d={outer} className="region-fill" />
              <path d={outer} className="memb" />
              <path d={inner} className="memb2" />
            </g>
          ))}
        </g>
      </svg>

      <svg className="map-svg strands">
        <g ref={strandsRef}>
          {selected &&
            shownLines.map(({ line, other }) => {
              const shape = strand([selected.x, selected.y], [other.x, other.y], line.edgeId)
              const tension = TENSION_TYPES.has(line.type)
              const active = line.edgeId === selectedEdgeId
              const classes = ['strand', tension && 'tension', line.isHypothesis && 'hypothesis', active && 'active']
              return (
                <g key={line.edgeId} className={classes.filter(Boolean).join(' ')}>
                  {!tension && <path d={shape.path} className="cxg" />}
                  <path d={shape.path} className="cx" />
                  {!tension && shape.branches.map((branch, index) => <path key={index} d={branch} className="cxb" />)}
                  <path
                    d={shape.path}
                    className="strand-hit"
                    role="button"
                    tabIndex={0}
                    aria-label={relationshipName(selected, line, other)}
                    aria-pressed={active}
                    onClick={() => onSelectEdge(line.edgeId)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        onSelectEdge(line.edgeId)
                      }
                    }}
                  />
                </g>
              )
            })}
        </g>
      </svg>

      <div ref={layerRef} className="map-layer">
        {regions.map(({ region, name }) => (
          <span
            key={region.key}
            className="region-name"
            style={{ left: `${name[0] * scale}px`, top: `${name[1] * scale}px` }}
            aria-hidden="true"
          >
            {region.name}
          </span>
        ))}
        {selected &&
          shownLines
            .filter(({ line }) => line.isHypothesis)
            .map(({ line, other }) => {
              const { middle } = strand([selected.x, selected.y], [other.x, other.y], line.edgeId)
              return (
                <span
                  key={line.edgeId}
                  className="strand-tag"
                  style={{ left: `${middle[0] * scale}px`, top: `${middle[1] * scale}px` }}
                  aria-hidden="true"
                >
                  Hypothesis
                </span>
              )
            })}
        {visible.map((mark, index) => {
          const labelled =
            mark.is_self || mark.id === selectedNodeId || prominent.has(mark.id) || neighbours.has(mark.id)
          return (
            <LandmarkButton
              key={mark.id}
              mark={mark}
              scale={scale}
              selected={mark.id === selectedNodeId}
              labelled={labelled}
              compact={!labelled && !detailed}
              fade={fadeOf(mark.last_seen_at, newest)}
              index={index}
              onSelect={onSelectNode}
            />
          )
        })}
      </div>

      <svg className="grain" aria-hidden="true">
        <filter id="atlas-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#atlas-grain)" />
      </svg>

      <div className="map-controls glass" role="group" aria-label="Zoom">
        <button type="button" className="icon-button" aria-label="Zoom out" onClick={() => zoomBy(1 / ZOOM_STEP)}>
          <Icon name="minus" size={18} />
        </button>
        <span className="zoom-level">{Math.round(zoomLevel * 100)}%</span>
        <button type="button" className="icon-button" aria-label="Zoom in" onClick={() => zoomBy(ZOOM_STEP)}>
          <Icon name="plus" size={18} />
        </button>
        <button type="button" className="icon-button" aria-label="Fit the whole map" onClick={fitView}>
          <Icon name="fit" size={18} />
        </button>
      </div>
    </div>
  )
}

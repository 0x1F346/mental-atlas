import { select } from 'd3-selection'
import { curveCatmullRomClosed, line } from 'd3-shape'
import { zoom, zoomIdentity, type ZoomBehavior } from 'd3-zoom'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

import {
  landmarkLabel,
  landmarkOpacity,
  landmarkRadius,
  prominentIds,
  REGION_COLOURS,
  TYPE_ICONS,
} from './appearance'
import type { Landmark, MapRendererProps } from './types'

/** Above this zoom, every landmark is drawn with its label. */
const DETAIL_ZOOM = 1.7
const MAX_ZOOM = 8

const outline = line<[number, number]>()
  .x((point) => point[0])
  .y((point) => point[1])
  .curve(curveCatmullRomClosed.alpha(0.5))

const DOT_RADIUS = 5

function LandmarkShape({ mark, selected, full }: { mark: Landmark; selected: boolean; full: boolean }) {
  // Zoomed out, lesser landmarks are small dots; the outline still shows their status.
  if (!full) return <circle r={DOT_RADIUS} className={`landmark-disc landmark-dot status-${mark.status}`} />
  const radius = landmarkRadius(mark.evidence_count)
  const scale = (radius * 1.15) / 12
  return (
    <>
      {selected && <circle r={radius + 7} className="landmark-halo" />}
      {/* Outline shows status: solid for stated, ringed for observed, dashed for hypothesis. */}
      {mark.status === 'observed' && <circle r={radius + 3.5} className="landmark-ring" />}
      <circle r={radius} className={`landmark-disc status-${mark.status}`} />
      <path
        d={TYPE_ICONS[mark.type]}
        transform={`translate(${-12 * scale} ${-12 * scale}) scale(${scale})`}
        className="landmark-icon"
      />
    </>
  )
}

/** The map drawn in SVG, with d3 handling pan, zoom and region outlines. */
export default function SvgMapRenderer({
  document: map,
  hiddenIds,
  selectedNodeId,
  selectedEdgeId,
  lines,
  onSelectNode,
  onSelectEdge,
}: MapRendererProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const behaviour = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.8, MAX_ZOOM])
      .on('zoom', (event) => setView({ x: event.transform.x, y: event.transform.y, k: event.transform.k }))
    zoomRef.current = behaviour
    select(svg).call(behaviour).on('dblclick.zoom', null)
    return () => {
      select(svg).on('.zoom', null)
    }
  }, [])

  function zoomBy(factor: number) {
    const svg = svgRef.current
    if (svg && zoomRef.current) zoomRef.current.scaleBy(select(svg), factor)
  }

  function resetView() {
    const svg = svgRef.current
    if (svg && zoomRef.current) zoomRef.current.transform(select(svg), zoomIdentity)
  }

  const visible = useMemo(
    () => map.landmarks.filter((mark) => !hiddenIds.has(mark.id)),
    [map.landmarks, hiddenIds],
  )
  const prominent = useMemo(() => prominentIds(visible), [visible])
  const byId = useMemo(() => new Map(map.landmarks.map((mark) => [mark.id, mark])), [map.landmarks])
  const detailed = view.k >= DETAIL_ZOOM
  const selected = selectedNodeId ? byId.get(selectedNodeId) : undefined
  const linked = new Set(lines.map((item) => item.otherId))
  // Keep labels and outlines a steady size on screen while the map scales.
  const inverse = 1 / Math.pow(view.k, 0.7)

  function onKey(event: KeyboardEvent, id: string) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectNode(id)
    }
  }

  return (
    <div className="map-frame">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${map.size} ${map.size}`}
        className="map-svg"
        role="group"
        aria-label="Map of your atlas"
        onClick={() => onSelectNode(null)}
      >
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g className="regions">
            {map.regions.map((region) => (
              <path
                key={region.key}
                d={outline(region.polygon as [number, number][]) ?? ''}
                fill={REGION_COLOURS[region.key]}
                className="region"
              />
            ))}
            {map.regions.map((region) => (
              <text
                key={region.key}
                x={region.anchor[0] ?? 0}
                y={(region.anchor[1] ?? 0) - (region.key === 'self' ? 120 : 0)}
                className="region-name"
                style={{ fontSize: 26 * inverse, opacity: detailed ? 0.35 : 0.75 }}
              >
                {region.name}
              </text>
            ))}
          </g>

          {selected && (
            <g className="relationships">
              {lines.map((item) => {
                const other = byId.get(item.otherId)
                if (!other || hiddenIds.has(other.id)) return null
                const active = item.edgeId === selectedEdgeId
                return (
                  <g key={item.edgeId}>
                    <line
                      x1={selected.x}
                      y1={selected.y}
                      x2={other.x}
                      y2={other.y}
                      className={`relationship${item.isHypothesis ? ' hypothesis' : ''}${active ? ' active' : ''}`}
                      style={{ strokeWidth: (active ? 4 : 2.5) * inverse }}
                    />
                    {/* A wide invisible line makes the relationship easy to pick. */}
                    <line
                      x1={selected.x}
                      y1={selected.y}
                      x2={other.x}
                      y2={other.y}
                      className="relationship-hit"
                      role="button"
                      tabIndex={0}
                      aria-label={`Relationship: ${selected.name} ${item.type.replaceAll('_', ' ').toLowerCase()} ${other.name}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelectEdge(item.edgeId)
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') onSelectEdge(item.edgeId)
                      }}
                    />
                  </g>
                )
              })}
            </g>
          )}

          <g className="landmarks">
            {visible.map((mark) => {
              const isSelected = mark.id === selectedNodeId
              const dimmed = selected !== undefined && !isSelected && !linked.has(mark.id)
              const full =
                detailed || mark.is_self || prominent.has(mark.id) || isSelected || linked.has(mark.id)
              const labelled = full && !dimmed
              const radius = landmarkRadius(mark.evidence_count)
              return (
                <g
                  key={mark.id}
                  transform={`translate(${mark.x} ${mark.y}) scale(${inverse})`}
                  className={`landmark type-${mark.type}${isSelected ? ' selected' : ''}`}
                  style={{ opacity: landmarkOpacity(mark.last_seen_at) * (dimmed ? 0.45 : 1) }}
                  role="button"
                  tabIndex={0}
                  aria-label={landmarkLabel(mark)}
                  aria-pressed={isSelected}
                  data-status={mark.status}
                  data-detail={full ? 'full' : 'dot'}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectNode(mark.id)
                  }}
                  onKeyDown={(event) => onKey(event, mark.id)}
                >
                  <LandmarkShape mark={mark} selected={isSelected} full={full} />
                  {labelled && (
                    <text y={radius + 18} className="landmark-label">
                      {mark.name.length > 30 ? `${mark.name.slice(0, 28)}…` : mark.name}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        </g>
      </svg>
      <div className="map-controls">
        <button type="button" className="quiet" onClick={() => zoomBy(1.5)} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="quiet" onClick={() => zoomBy(1 / 1.5)} aria-label="Zoom out">
          −
        </button>
        <button type="button" className="quiet" onClick={resetView} aria-label="Reset the view">
          ⟲
        </button>
      </div>
    </div>
  )
}

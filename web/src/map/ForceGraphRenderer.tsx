import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D, { type ForceGraphMethods } from 'react-force-graph-3d'

import { landmarkLabel, prominentIds } from './appearance'
import {
  animateStar,
  AREA_COLOURS,
  makeStar,
  makeStarfield,
  recentIds,
  seeded,
  SPACE_BACKGROUND,
  textSprite,
  toSpace,
  type Star,
} from './space'
import type { Landmark, MapRendererProps } from './types'

interface GraphNode {
  id: string
  mark: Landmark
  // Where the layout placed it: the force simulation starts here and is drawn back here.
  home: { x: number; y: number; z: number }
  well: { x: number; y: number }
  x?: number
  y?: number
  z?: number
  vx?: number
  vy?: number
  vz?: number
  fx?: number
  fy?: number
  fz?: number
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  edgeId: string
  isHypothesis: boolean
}

type Graph = ForceGraphMethods<GraphNode, GraphLink>

const OVERVIEW = { x: 0, y: 0, z: 780 }
const FOCUS_DISTANCE = 430
const EASE_MS = 1200
const WELL_PULL = 0.035
const HOME_PULL = 0.05
const DEPTH = 70
const NEIGHBOUR_DISTANCE = 95

/** Each life area is a gravity well; each landmark is also drawn back to its own place. */
function wellForce() {
  let nodes: GraphNode[] = []
  const force = (alpha: number) => {
    for (const node of nodes) {
      if (node.fx !== undefined) continue
      node.vx = (node.vx ?? 0) + ((node.well.x - (node.x ?? 0)) * WELL_PULL + (node.home.x - (node.x ?? 0)) * HOME_PULL) * alpha
      node.vy = (node.vy ?? 0) + ((node.well.y - (node.y ?? 0)) * WELL_PULL + (node.home.y - (node.y ?? 0)) * HOME_PULL) * alpha
      node.vz = (node.vz ?? 0) + (node.home.z - (node.z ?? 0)) * HOME_PULL * alpha
    }
  }
  force.initialize = (initial: GraphNode[]) => {
    nodes = initial
  }
  return force
}

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

function endId(end: string | GraphNode): string {
  return typeof end === 'string' ? end : end.id
}

/**
 * The map as a WebGL force-directed graph in a dark space theme. Landmarks are glowing
 * points sized by evidence and coloured by life area. Relationships appear only for
 * the selected landmark. A hidden list of buttons mirrors the landmarks, so the map
 * can be used from the keyboard and by screen readers.
 */
export default function ForceGraphRenderer({
  document: map,
  hiddenIds,
  selectedNodeId,
  selectedEdgeId,
  lines,
  onSelectNode,
  onSelectEdge,
}: MapRendererProps) {
  const frame = useRef<HTMLDivElement>(null)
  const graph = useRef<Graph | undefined>(undefined)
  // Held for the life of the component: the simulation and the animation loop mutate them.
  const [nodeCache] = useState(() => new Map<string, GraphNode>())
  const [stars] = useState(() => new Map<string, Star>())
  const [size, setSize] = useState({ width: 800, height: 600 })
  const [webgl] = useState(hasWebGL)
  const still = useMemo(
    () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  const wells = useMemo(
    () => new Map(map.regions.map((region) => [region.key, toSpace(region.anchor[0] ?? 500, region.anchor[1] ?? 500)])),
    [map.regions],
  )
  const visible = useMemo(() => map.landmarks.filter((mark) => !hiddenIds.has(mark.id)), [map.landmarks, hiddenIds])
  const prominent = useMemo(() => prominentIds(visible), [visible])
  const recent = useMemo(() => recentIds(map.landmarks), [map.landmarks])
  const linked = useMemo(() => new Set(lines.map((line) => line.otherId)), [lines])
  const byId = useMemo(() => new Map(map.landmarks.map((mark) => [mark.id, mark])), [map.landmarks])

  // Node objects are kept between renders so the simulation keeps their positions.
  const graphData = useMemo(() => {
    const nodes = visible.map((mark) => {
      const place = toSpace(mark.x, mark.y)
      const home = { ...place, z: mark.is_self ? 0 : (seeded(mark.id, 7) - 0.5) * DEPTH }
      let node = nodeCache.get(mark.id)
      if (!node) {
        // Seeded from map_positions.
        node = { id: mark.id, mark, home, well: place, ...home }
        nodeCache.set(mark.id, node)
      }
      node.mark = mark
      node.home = home
      node.well = wells.get(mark.life_area) ?? { x: 0, y: 0 }
      if (mark.is_self) Object.assign(node, { fx: 0, fy: 0, fz: 0 })
      return node
    })
    const shown = new Set(nodes.map((node) => node.id))
    const links: GraphLink[] =
      selectedNodeId && shown.has(selectedNodeId)
        ? lines
            .filter((line) => shown.has(line.otherId))
            .map((line) => ({
              source: selectedNodeId,
              target: line.otherId,
              edgeId: line.edgeId,
              isHypothesis: line.isHypothesis,
            }))
        : []
    return { nodes, links }
  }, [visible, wells, lines, selectedNodeId, nodeCache])

  useEffect(() => {
    const element = frame.current
    if (!element || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Forces, the starfield and the names of the wells are set up once the graph exists.
  useEffect(() => {
    const instance = graph.current
    if (!instance) return
    instance.d3Force('center', null)
    instance.d3Force('well', wellForce() as never)
    const charge = instance.d3Force('charge') as unknown as { strength?: (value: number) => unknown } | undefined
    charge?.strength?.(-22)
    const link = instance.d3Force('link') as unknown as
      | { distance?: (value: number) => { strength?: (value: number) => unknown } }
      | undefined
    link?.distance?.(NEIGHBOUR_DISTANCE)?.strength?.(0.09)
    const scene = instance.scene()
    const backdrop = makeStarfield()
    scene.add(backdrop)
    const names = map.regions.map((region) => {
      const place = toSpace(region.anchor[0] ?? 500, region.anchor[1] ?? 500)
      const sprite = textSprite(region.name.toUpperCase(), AREA_COLOURS[region.key], 64, 22)
      sprite.material.opacity = 0.45
      sprite.position.set(place.x * 1.42, place.y * 1.42 + (region.key === 'self' ? 62 : 0), -DEPTH)
      sprite.raycast = () => undefined
      scene.add(sprite)
      return sprite
    })
    instance.cameraPosition(OVERVIEW, { x: 0, y: 0, z: 0 }, 0)
    return () => {
      scene.remove(backdrop, ...names)
    }
  }, [map.regions, webgl])

  // The animation loop: drift, pulse, flicker and dimming, independent of the physics.
  const selection = useRef({ selectedNodeId, linked, prominent })
  useEffect(() => {
    selection.current = { selectedNodeId, linked, prominent }
  }, [selectedNodeId, linked, prominent])
  useEffect(() => {
    if (!webgl) return
    let request = 0
    const started = performance.now()
    const tick = (now: number) => {
      const { selectedNodeId: selected, linked: near, prominent: major } = selection.current
      for (const [id, star] of stars) {
        const isSelected = id === selected
        const isLinked = near.has(id)
        const mark = nodeCache.get(id)?.mark
        animateStar(
          star,
          {
            selected: isSelected,
            linked: isLinked,
            dimmed: selected !== null && !isSelected && !isLinked,
            labelled: isSelected || isLinked || major.has(id) || Boolean(mark?.is_self),
          },
          (now - started) / 1000,
          still,
        )
      }
      request = requestAnimationFrame(tick)
    }
    request = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(request)
  }, [webgl, still, nodeCache, stars])

  // Ease the camera to the selected landmark, and back out when nothing is selected.
  useEffect(() => {
    const instance = graph.current
    if (!instance) return
    const node = selectedNodeId ? nodeCache.get(selectedNodeId) : undefined
    if (!node) {
      instance.cameraPosition(OVERVIEW, { x: 0, y: 0, z: 0 }, still ? 0 : EASE_MS)
      return
    }
    const at = { x: node.x ?? node.home.x, y: node.y ?? node.home.y, z: node.z ?? node.home.z }
    instance.cameraPosition({ x: at.x, y: at.y, z: at.z + FOCUS_DISTANCE }, at, still ? 0 : EASE_MS)
  }, [selectedNodeId, still, nodeCache])

  const nodeObject = useCallback(
    (node: GraphNode) => {
      let star = stars.get(node.id)
      if (!star) {
        star = makeStar(node.mark, recent.has(node.id))
        stars.set(node.id, star)
      }
      return star.group
    },
    [recent, stars],
  )

  const selected = selectedNodeId ? byId.get(selectedNodeId) : undefined
  return (
    <div className="map-frame space" ref={frame}>
      {webgl ? (
        <ForceGraph3D<GraphNode, GraphLink>
          ref={graph}
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor={SPACE_BACKGROUND}
          showNavInfo={false}
          nodeLabel={(node) => node.mark.name}
          nodeThreeObject={nodeObject}
          enableNodeDrag={false}
          warmupTicks={still ? 60 : 0}
          cooldownTime={still ? 0 : 6000}
          d3AlphaDecay={0.03}
          d3VelocityDecay={0.5}
          linkColor={(link) => (link.isHypothesis ? 'rgba(232,236,245,0.35)' : 'rgba(232,236,245,0.8)')}
          linkWidth={(link) => (link.edgeId === selectedEdgeId ? 1.6 : 0.6)}
          linkOpacity={0.55}
          linkDirectionalParticles={(link) => (still ? 0 : link.isHypothesis ? 1 : 3)}
          linkDirectionalParticleWidth={2.2}
          linkDirectionalParticleSpeed={0.007}
          linkDirectionalParticleColor={(link) => AREA_COLOURS[byId.get(endId(link.target))?.life_area ?? 'self']}
          onNodeClick={(node) => onSelectNode(node.id)}
          onLinkClick={(link) => onSelectEdge(link.edgeId)}
          onBackgroundClick={() => onSelectNode(null)}
        />
      ) : (
        <p className="map-empty">This browser cannot draw the map (WebGL is unavailable). Use the list below.</p>
      )}

      {/* The same landmarks as plain buttons, for keyboards, screen readers and tests. */}
      <div className={webgl ? 'visually-hidden' : 'landmark-list'} role="group" aria-label="Map of your atlas">
        <ul>
          {visible.map((mark) => (
            <li key={mark.id}>
              <button
                type="button"
                aria-label={landmarkLabel(mark)}
                aria-pressed={mark.id === selectedNodeId}
                data-area={mark.life_area}
                onClick={() => onSelectNode(mark.id)}
              >
                {mark.name}
              </button>
            </li>
          ))}
        </ul>
        {selected && (
          <ul>
            {lines.map((line) => {
              const other = byId.get(line.otherId)
              if (!other || hiddenIds.has(other.id)) return null
              const verb = line.type.replaceAll('_', ' ').toLowerCase()
              return (
                <li key={line.edgeId}>
                  <button
                    type="button"
                    aria-label={`Relationship: ${selected.name} ${verb} ${other.name}`}
                    data-hypothesis={line.isHypothesis}
                    onClick={() => onSelectEdge(line.edgeId)}
                  >
                    {selected.name} {verb} {other.name}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="map-controls">
        <button type="button" onClick={() => onSelectNode(null)} aria-label="Reset the view">
          ⟲
        </button>
      </div>
    </div>
  )
}

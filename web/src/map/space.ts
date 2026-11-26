// Look and motion of the space map: colours by life area, size by evidence, and the
// three.js objects each landmark is drawn with.
import {
  AdditiveBlending,
  Color,
  DoubleSide,
  BufferGeometry,
  CanvasTexture,
  Float32BufferAttribute,
  Group,
  Mesh,
  MeshBasicMaterial,
  Points,
  PointsMaterial,
  Sprite,
  SpriteMaterial,
  type Texture,
} from 'three'

import type { LifeArea, NodeType } from '../api/generated/vocabulary'
import type { Landmark } from './types'

export const SPACE_BACKGROUND = '#04050c'

export const AREA_COLOURS: Record<LifeArea, string> = {
  love: '#ff6f91',
  family: '#ffb454',
  friendships: '#8ee06b',
  work: '#4fc3f7',
  body_health: '#b39dff',
  self: '#f5f1e6',
}

const MAP_CENTRE = 500
const RECENT_DAYS = 30

/** Map units (0 to 1000, y down) to graph space (centred, y up). */
export function toSpace(x: number, y: number): { x: number; y: number } {
  return { x: x - MAP_CENTRE, y: MAP_CENTRE - y }
}

/** A stable number in [0, 1) from an id, so depth and animation phase never change. */
export function seeded(id: string, salt = 0): number {
  let hash = 2166136261 ^ salt
  for (let i = 0; i < id.length; i += 1) {
    hash ^= id.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return ((hash >>> 0) % 100_000) / 100_000
}

/** Glow size grows with evidence count. */
export function glowSize(evidenceCount: number): number {
  return Math.min(24 + 10 * Math.sqrt(Math.max(evidenceCount, 0)), 90)
}

/** Landmarks last seen within a month of the newest appearance in the atlas. */
export function recentIds(landmarks: Landmark[]): Set<string> {
  const times = landmarks.flatMap((mark) => (mark.last_seen_at ? [Date.parse(mark.last_seen_at)] : []))
  if (times.length === 0) return new Set()
  const cutoff = Math.max(...times) - RECENT_DAYS * 86_400_000
  return new Set(
    landmarks
      .filter((mark) => !mark.is_self && mark.last_seen_at && Date.parse(mark.last_seen_at) >= cutoff)
      .map((mark) => mark.id),
  )
}

/** The shape a landmark is drawn with. Types not listed here are round points. */
export type StarShape = 'point' | 'star' | 'heart'
export const TYPE_SHAPES: Partial<Record<NodeType, StarShape>> = { person: 'star' }

export function shapeOf(type: NodeType): StarShape {
  return TYPE_SHAPES[type] ?? 'point'
}

function tracePath(context: CanvasRenderingContext2D, shape: 'star' | 'heart') {
  context.beginPath()
  if (shape === 'heart') {
    context.moveTo(64, 96)
    context.bezierCurveTo(20, 66, 28, 34, 48, 34)
    context.bezierCurveTo(57, 34, 62, 40, 64, 46)
    context.bezierCurveTo(66, 40, 71, 34, 80, 34)
    context.bezierCurveTo(100, 34, 108, 66, 64, 96)
  } else {
    // A five-pointed star, point up.
    for (let i = 0; i < 10; i += 1) {
      const radius = i % 2 === 0 ? 36 : 15
      const angle = -Math.PI / 2 + (i * Math.PI) / 5
      const x = 64 + radius * Math.cos(angle)
      const y = 66 + radius * Math.sin(angle)
      if (i === 0) context.moveTo(x, y)
      else context.lineTo(x, y)
    }
  }
  context.closePath()
}

const shapeTextures = new Map<string, Texture>()

/** A glowing shape, white so the material's colour tints it like the round glow. */
function shaped(shape: 'star' | 'heart'): Texture {
  const cached = shapeTextures.get(shape)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 128
  const context = canvas.getContext('2d')
  if (context) {
    context.lineJoin = 'round'
    // A soft halo first, then the solid shape on top.
    context.shadowColor = 'rgba(255,255,255,0.9)'
    context.shadowBlur = 22
    context.fillStyle = 'rgba(255,255,255,0.55)'
    tracePath(context, shape)
    context.fill()
    context.shadowBlur = 6
    context.fillStyle = 'rgba(255,255,255,1)'
    tracePath(context, shape)
    context.fill()
  }
  const texture = new CanvasTexture(canvas)
  shapeTextures.set(shape, texture)
  return texture
}

let glowTexture: Texture | null = null

function glow(): Texture {
  if (glowTexture) return glowTexture
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 128
  const context = canvas.getContext('2d')
  if (context) {
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64)
    gradient.addColorStop(0, 'rgba(255,255,255,1)')
    gradient.addColorStop(0.12, 'rgba(255,255,255,0.95)')
    gradient.addColorStop(0.3, 'rgba(255,255,255,0.35)')
    gradient.addColorStop(0.6, 'rgba(255,255,255,0.08)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
    context.fillStyle = gradient
    context.fillRect(0, 0, 128, 128)
  }
  glowTexture = new CanvasTexture(canvas)
  return glowTexture
}

export function textSprite(text: string, colour: string, fontPx: number, height: number): Sprite {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  const font = `500 ${fontPx}px system-ui, sans-serif`
  let width = fontPx * text.length * 0.6
  if (context) {
    context.font = font
    width = context.measureText(text).width
  }
  canvas.width = Math.ceil(width) + 16
  canvas.height = Math.ceil(fontPx * 1.4)
  if (context) {
    context.font = font
    context.fillStyle = colour
    context.textBaseline = 'middle'
    context.fillText(text, 8, canvas.height / 2)
  }
  const material = new SpriteMaterial({ map: new CanvasTexture(canvas), transparent: true, depthWrite: false })
  const sprite = new Sprite(material)
  sprite.scale.set((height * canvas.width) / canvas.height, height, 1)
  return sprite
}

/** What the animation loop needs to know about one landmark's objects. */
export interface Star {
  group: Group
  glow: Sprite
  label: Sprite
  size: number
  phase: number
  recent: boolean
  hypothesis: boolean
}

export function makeStar(mark: Landmark, recent: boolean): Star {
  const shape = shapeOf(mark.type)
  // A drawn shape fills less of its texture than a round glow, so it is drawn a little larger.
  const size = glowSize(mark.evidence_count) * (shape === 'point' ? 1 : 1.25)
  const material = new SpriteMaterial({
    map: shape === 'point' ? glow() : shaped(shape),
    color: AREA_COLOURS[mark.life_area],
    blending: AdditiveBlending,
    transparent: true,
    depthWrite: false,
  })
  const sprite = new Sprite(material)
  sprite.scale.set(size, size, 1)
  const name = mark.name.length > 30 ? `${mark.name.slice(0, 28)}…` : mark.name
  const label = textSprite(name, '#e8ecf5', 44, 14)
  label.position.set(0, -(size * 0.26 + 8), 0)
  label.raycast = () => undefined // Labels never intercept a click meant for a star.
  const group = new Group()
  group.add(sprite, label)
  return {
    group,
    glow: sprite,
    label,
    size,
    phase: seeded(mark.id) * Math.PI * 2,
    recent,
    hypothesis: mark.is_hypothesis,
  }
}

export interface StarState {
  selected: boolean
  linked: boolean
  dimmed: boolean
  labelled: boolean
}

/** One animation frame for one landmark: ambient drift, pulse, flicker and dimming. */
export function animateStar(star: Star, state: StarState, seconds: number, still: boolean): void {
  const t = still ? 0 : seconds
  const { phase } = star
  // Ambient drift: a slow wander around the landmark's place, within the plane.
  star.glow.position.set(Math.sin(t * 0.41 + phase) * 2.4, Math.cos(t * 0.33 + phase * 1.7) * 2.4, 0)
  // Recently seen landmarks pulse.
  let scale = star.recent && !still ? 1 + 0.2 * Math.sin(t * 2.3 + phase) : 1
  if (state.selected) scale *= 1.45
  else if (state.linked) scale *= 1.15
  star.glow.scale.set(star.size * scale, star.size * scale, 1)

  // A hypothesis is dimmer and flickers, so it never reads as settled.
  let opacity = 1
  if (star.hypothesis) {
    const flicker = still ? 0 : Math.sin(t * 7.3 + phase) * Math.sin(t * 3.1 + phase * 2.3)
    opacity = 0.5 + 0.22 * flicker
  }
  if (state.dimmed) opacity *= 0.13
  star.glow.material.opacity = opacity
  star.label.visible = state.labelled && !state.dimmed
  star.label.material.opacity = state.selected || state.linked ? 1 : 0.7
}

const LINK_WIDTH = 1.6 // In map units; the graph is flat, so a ribbon in its plane is a line.
const SELECTED_LINK_WIDTH = 3.2

/**
 * A relationship line whose colour runs from the origin's life-area colour to the
 * connecting point's. A hypothesis is fainter.
 */
export function makeLink(from: LifeArea, to: LifeArea, hypothesis: boolean): Mesh {
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new Float32BufferAttribute(new Array<number>(12).fill(0), 3))
  const start = new Color(AREA_COLOURS[from])
  const end = new Color(AREA_COLOURS[to])
  // Two corners at the origin's colour, two at the connecting point's.
  const colours = [start, start, end, end].flatMap((colour) => [colour.r, colour.g, colour.b])
  geometry.setAttribute('color', new Float32BufferAttribute(colours, 3))
  geometry.setIndex([0, 1, 2, 2, 1, 3])
  const material = new MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: hypothesis ? 0.4 : 0.9,
    side: DoubleSide,
    depthWrite: false,
  })
  const line = new Mesh(geometry, material)
  // Its ends move every frame, so the bounds it was created with must not hide it.
  line.frustumCulled = false
  return line
}

interface Point2 {
  x: number
  y: number
}

/** Stretch a relationship line between its two ends as they move. */
export function placeLink(line: Mesh, start: Point2, end: Point2, selected: boolean): void {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const length = Math.hypot(dx, dy) || 1
  const half = (selected ? SELECTED_LINK_WIDTH : LINK_WIDTH) / 2
  const ox = (-dy / length) * half
  const oy = (dx / length) * half
  const position = line.geometry.getAttribute('position')
  // Just behind the landmarks, which sit at depth 0. A flat simulation gives no depth.
  const z = -0.5
  position.setXYZ(0, start.x + ox, start.y + oy, z)
  position.setXYZ(1, start.x - ox, start.y - oy, z)
  position.setXYZ(2, end.x + ox, end.y + oy, z)
  position.setXYZ(3, end.x - ox, end.y - oy, z)
  position.needsUpdate = true
  line.geometry.computeBoundingSphere()
}

/** A field of distant stars behind the atlas. */
export function makeStarfield(count = 1600): Points {
  const positions: number[] = []
  for (let i = 0; i < count; i += 1) {
    const radius = 1700 + seeded(`r${i}`) * 1800
    const theta = seeded(`t${i}`) * Math.PI * 2
    const phi = Math.acos(2 * seeded(`p${i}`) - 1)
    positions.push(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
    )
  }
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new Float32BufferAttribute(positions, 3))
  const material = new PointsMaterial({ color: '#9fb0d8', size: 2.2, sizeAttenuation: false, transparent: true, opacity: 0.55 })
  return new Points(geometry, material)
}

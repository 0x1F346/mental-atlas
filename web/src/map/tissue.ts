// Geometry for the SVG map (D-024). All coordinates are map units (0 to MapDocument.size).
import { curveCatmullRomClosed, line } from 'd3-shape'

import type { Region } from './types'

type Point = [number, number]

const smoothClosed = line<Point>()
  .x((point) => point[0])
  .y((point) => point[1])
  .curve(curveCatmullRomClosed.alpha(0.5))

/** A smooth closed outline through the points. */
export function outlinePath(points: Point[]): string {
  return smoothClosed(points) ?? ''
}

function signedArea(points: Point[]): number {
  let sum = 0
  points.forEach(([x1, y1], index) => {
    const [x2, y2] = points[(index + 1) % points.length] ?? [x1, y1]
    sum += x1 * y2 - x2 * y1
  })
  return sum / 2
}

/**
 * The outline moved inwards by `distance`, so neighbouring regions, which share borders in
 * the stored layout, are drawn as separate cells. The stored polygon stays the record.
 */
export function insetPolygon(points: Point[], distance: number): Point[] {
  const count = points.length
  if (count < 3) return points
  // With y pointing down, a positive signed area runs clockwise on screen, and then the
  // normal computed below points outwards.
  const inward = signedArea(points) > 0 ? -1 : 1
  return points.map(([x, y], index) => {
    const [px, py] = points[(index - 1 + count) % count] ?? [x, y]
    const [nx, ny] = points[(index + 1) % count] ?? [x, y]
    // The average of the two edge normals at this point.
    const ax = y - py + (ny - y)
    const ay = -(x - px) - (nx - x)
    const length = Math.hypot(ax, ay) || 1
    return [x + (inward * distance * ax) / length, y + (inward * distance * ay) / length]
  })
}

/**
 * The outline as drawn: near-duplicate points dropped, then softened with a moving average.
 * The stored coastline is sampled more coarsely than its wobble, which reads as a sawtooth.
 */
export function softenPolygon(points: Point[], passes = 2, minGap = 1): Point[] {
  let result = points.filter((point, index) => {
    const next = points[(index + 1) % points.length] ?? point
    return Math.hypot(next[0] - point[0], next[1] - point[1]) >= minGap
  })
  for (let pass = 0; pass < passes; pass++) {
    const count = result.length
    result = result.map(([x, y], index) => {
      const [px, py] = result[(index - 1 + count) % count] ?? [x, y]
      const [nx, ny] = result[(index + 1) % count] ?? [x, y]
      return [(px + 2 * x + nx) / 4, (py + 2 * y + ny) / 4]
    })
  }
  return result
}

/** Where a region's name sits: towards the outer coast of a wedge, at the top of the centre. */
export function namePosition(region: Region, size: number): Point {
  const centre = size / 2
  const [ax, ay] = region.anchor as Point
  if (Math.hypot(ax - centre, ay - centre) < 1) {
    const top = Math.min(...region.polygon.map((point) => point[1] ?? centre))
    return [ax, top + size * 0.035]
  }
  return [centre + (ax - centre) * 1.36, centre + (ay - centre) * 1.36]
}

/** A small seeded random generator, so decoration never changes between loads. */
export function seededRandom(seed: string): () => number {
  let state = 2166136261
  for (const char of seed) state = Math.imul(state ^ char.charCodeAt(0), 16777619)
  return () => {
    state = Math.imul(state ^ (state >>> 15), 2246822507)
    state = Math.imul(state ^ (state >>> 13), 3266489909)
    state ^= state >>> 16
    return (state >>> 0) / 4294967296
  }
}

/** Faint branching threads from each region's heart. Decoration only; they mean nothing. */
export function myceliumPaths(regions: Region[], size: number): string[] {
  const paths: string[] = []
  for (const region of regions) {
    const random = seededRandom(`mycelium:${region.key}`)
    const [ax, ay] = region.anchor as Point
    for (let strand = 0; strand < 6; strand++) {
      let angle = random() * Math.PI * 2
      let [x, y] = [ax, ay]
      let d = `M${x.toFixed(1)} ${y.toFixed(1)}`
      const steps = 5 + Math.floor(random() * 5)
      for (let step = 0; step < steps; step++) {
        angle += (random() - 0.5) * 0.9
        const reach = size * (0.02 + random() * 0.03)
        const nx = x + Math.cos(angle) * reach
        const ny = y + Math.sin(angle) * reach
        d += ` Q${(x + Math.cos(angle + 0.6) * reach * 0.5).toFixed(1)} ${(y + Math.sin(angle + 0.6) * reach * 0.5).toFixed(1)} ${nx.toFixed(1)} ${ny.toFixed(1)}`
        if (random() < 0.3) {
          const side = angle + (random() < 0.5 ? 1 : -1) * (0.8 + random() * 0.6)
          const length = reach * 0.8
          paths.push(
            `M${nx.toFixed(1)} ${ny.toFixed(1)} L${(nx + Math.cos(side) * length).toFixed(1)} ${(ny + Math.sin(side) * length).toFixed(1)}`,
          )
        }
        x = nx
        y = ny
      }
      paths.push(d)
    }
  }
  return paths
}

export interface Strand {
  path: string
  branches: string[]
  middle: Point
}

/**
 * A relationship drawn as a gently curved, slightly irregular line with a few short side
 * branches. The bend is seeded by the edge, so it is the same on every load.
 */
export function strand(from: Point, to: Point, seed: string): Strand {
  const random = seededRandom(`strand:${seed}`)
  const [x1, y1] = from
  const [x2, y2] = to
  const dx = x2 - x1
  const dy = y2 - y1
  const length = Math.hypot(dx, dy) || 1
  const [nx, ny] = [-dy / length, dx / length]
  const bend = (random() < 0.5 ? -1 : 1) * length * (0.08 + random() * 0.1)
  const wobble = length * (random() - 0.5) * 0.08
  const c1: Point = [x1 + dx * 0.33 + nx * (bend + wobble), y1 + dy * 0.33 + ny * (bend + wobble)]
  const c2: Point = [x1 + dx * 0.67 + nx * (bend - wobble), y1 + dy * 0.67 + ny * (bend - wobble)]
  const at = (t: number): Point => {
    const u = 1 - t
    return [
      u * u * u * x1 + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * x2,
      u * u * u * y1 + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * y2,
    ]
  }
  const branches = [0.3, 0.55, 0.78].map((t) => {
    const [bx, by] = at(t)
    const [qx, qy] = at(t + 0.02)
    const side = random() < 0.5 ? -1 : 1
    const reach = Math.min(length * 0.06, 14) * (0.6 + random() * 0.6)
    const tx = (qx - bx) / (Math.hypot(qx - bx, qy - by) || 1)
    const ty = (qy - by) / (Math.hypot(qx - bx, qy - by) || 1)
    // Angled forward along the strand, like a root hair.
    const ex = bx + (tx * 0.6 + -ty * side) * reach
    const ey = by + (ty * 0.6 + tx * side) * reach
    return `M${bx.toFixed(1)} ${by.toFixed(1)} L${ex.toFixed(1)} ${ey.toFixed(1)}`
  })
  const fmt = (point: Point) => `${point[0].toFixed(1)} ${point[1].toFixed(1)}`
  return { path: `M${fmt(from)} C${fmt(c1)} ${fmt(c2)} ${fmt(to)}`, branches, middle: at(0.5) }
}

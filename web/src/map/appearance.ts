// Names for concept types and statuses, and which landmarks are prominent enough to label.
import type { LifeArea, NodeType, Status } from '../api/generated/vocabulary'
import type { Landmark } from './types'

export const TYPE_LABELS: Record<NodeType, string> = {
  person: 'Person',
  group: 'Group',
  situation: 'Situation',
  event: 'Event',
  feeling: 'Feeling',
  sensation: 'Sensation',
  belief: 'Belief',
  behaviour: 'Behaviour',
  need: 'Need',
  value: 'Value',
  goal: 'Goal',
  trait: 'Trait',
  role: 'Role',
  pattern: 'Pattern',
  tension: 'Tension',
  blind_spot: 'Blind spot',
  unsorted: 'Unsorted',
}

export const STATUS_LABELS: Record<Status, string> = {
  stated: 'Stated',
  observed: 'Observed',
  hypothesis: 'Hypothesis',
}

/** The six types with their own colour and their own filter chip; the rest sit under "More". */
export const MAIN_TYPES: NodeType[] = ['person', 'situation', 'event', 'feeling', 'belief', 'behaviour']

/** Colours for concept types (docs/design/DESIGN_BRIEF.md). Other types share a neutral one (D-024). */
const TYPE_COLOURS: Partial<Record<NodeType, string>> = {
  person: '#FF9B85',
  situation: '#F2C36B',
  event: '#6FD6E8',
  feeling: '#B9A2FF',
  belief: '#8CEBB0',
  behaviour: '#F08FC0',
}
const OTHER_TYPE_COLOUR = '#A9C2BE'

export function typeColour(type: NodeType): string {
  return TYPE_COLOURS[type] ?? OTHER_TYPE_COLOUR
}

export const NOTICED_LABELS ={ self: 'Me', therapist: 'My therapist', ai: 'Inferred' } as const

/** Only the largest landmarks carry a label until one is selected. */
export function prominentIds(landmarks: Landmark[], limit = 12): Set<string> {
  const ranked = [...landmarks].sort((a, b) => b.evidence_count - a.evidence_count || a.name.localeCompare(b.name))
  return new Set(ranked.slice(0, limit).map((mark) => mark.id))
}

export function landmarkLabel(mark: Pick<Landmark, 'type' | 'name' | 'status'>): string {
  return `${TYPE_LABELS[mark.type]}: ${mark.name} (${STATUS_LABELS[mark.status].toLowerCase()})`
}

/** Region tints, one per life area, from the design mockup. */
export const AREA_COLOURS: Record<LifeArea, string> = {
  family: '#2C8F78',
  love: '#8A62B8',
  work: '#2A86A6',
  self: '#4FB389',
  body_health: '#3C78B8',
  friendships: '#B8735C',
}

const MIN_DIAMETER = 28
const MAX_DIAMETER = 66

/** Orb diameter in pixels: grows with evidence, from 28 for one mention to 66 at 32 or more. */
export function landmarkDiameter(evidenceCount: number): number {
  const share = Math.min(1, Math.log2(Math.max(1, evidenceCount)) / 5)
  return Math.round(MIN_DIAMETER + (MAX_DIAMETER - MIN_DIAMETER) * share)
}

const FADE_DAYS = 120
const DAY_MS = 86_400_000

/**
 * How far a landmark has faded, 0 (just mentioned) to 1 (unmentioned for four months or
 * more), counted back from the newest mention on the map rather than from today.
 */
export function fadeOf(lastSeenAt: string | null, newest: number): number {
  if (!lastSeenAt) return 1
  return Math.min(1, Math.max(0, (newest - Date.parse(lastSeenAt)) / DAY_MS / FADE_DAYS))
}

export function newestMention(landmarks: Landmark[]): number {
  return Math.max(0, ...landmarks.map((mark) => (mark.last_seen_at ? Date.parse(mark.last_seen_at) : 0)))
}

/** The orb fades from 1.0 to 0.4; its label only from the main text colour to #93AEAB. */
export function orbOpacity(fade: number): number {
  return Number((1 - 0.6 * fade).toFixed(3))
}

export function labelColour(fade: number): string {
  const from = [0xf2, 0xf7, 0xf3]
  const to = [0x93, 0xae, 0xab]
  const mixed = from.map((value, index) => Math.round(value + ((to[index] ?? value) - value) * fade))
  return `#${mixed.map((value) => value.toString(16).padStart(2, '0')).join('')}`
}

// Names for concept types and statuses, and which landmarks are prominent enough to label.
import type { NodeType, Status } from '../api/generated/vocabulary'
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

/** Colours for concept types (docs/design/DESIGN_BRIEF.md). Other types share a neutral one. */
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

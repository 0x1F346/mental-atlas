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

export const NOTICED_LABELS = { self: 'Me', therapist: 'My therapist', ai: 'Inferred' } as const

/** Only the largest landmarks carry a label until one is selected. */
export function prominentIds(landmarks: Landmark[], limit = 12): Set<string> {
  const ranked = [...landmarks].sort((a, b) => b.evidence_count - a.evidence_count || a.name.localeCompare(b.name))
  return new Set(ranked.slice(0, limit).map((mark) => mark.id))
}

export function landmarkLabel(mark: Pick<Landmark, 'type' | 'name' | 'status'>): string {
  return `${TYPE_LABELS[mark.type]}: ${mark.name} (${STATUS_LABELS[mark.status].toLowerCase()})`
}

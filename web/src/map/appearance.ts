// How a landmark looks: icon by type, size by evidence, fade by age, outline by status.
import type { NodeType, Status } from '../api/generated/vocabulary'
import type { Landmark } from './types'

/** One 24x24 path per concept type, drawn centred on the landmark. */
export const TYPE_ICONS: Record<NodeType, string> = {
  person: 'M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8zm-7 16c0-3.9 3.1-6 7-6s7 2.1 7 6z',
  group: 'M8 6a3 3 0 1 1 0 6 3 3 0 0 1 0-6zm8 0a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM2 20c0-3 2.7-5 6-5s6 2 6 5zm12.5 0c0-1.9-.7-3.4-1.9-4.5 4-.9 9.4.8 9.4 4.5z',
  situation: 'M4 6h16v12H4zm3 3v6h10V9z',
  event: 'M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.3l6.1-.7z',
  feeling: 'M12 20.5 4.6 13a4.7 4.7 0 0 1 6.7-6.6l.7.7.7-.7A4.7 4.7 0 0 1 19.4 13z',
  sensation: 'M3 12c2-5 4-5 6 0s4 5 6 0 4-5 6 0v3c-2-5-4-5-6 0s-4 5-6 0-4-5-6 0z',
  belief: 'M4 5h16v11H10l-4 4v-4H4z',
  behaviour: 'M5 12h10.2l-3.6-3.6L13 7l6 6-6 6-1.4-1.4 3.6-3.6H5z',
  need: 'M12 3l8 5v8l-8 5-8-5V8zm0 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  value: 'M12 3l7 9-7 9-7-9z',
  goal: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4z',
  trait: 'M12 3l2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z',
  role: 'M6 4h12l2 5-8 11L4 9zm2.5 2L7 9h10l-1.5-3z',
  pattern: 'M4 18l5-8 4 5 3-6 4 9z',
  tension: 'M4 12l5-5v3h6V7l5 5-5 5v-3H9v3z',
  blind_spot: 'M12 5c5 0 8.5 4.5 9.5 7-1 2.5-4.5 7-9.5 7s-8.5-4.5-9.5-7c1-2.5 4.5-7 9.5-7zM5 5l14 14',
  unsorted: 'M5 5h14v14H5z',
}

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

export const REGION_COLOURS: Record<string, string> = {
  love: '#f3d9d4',
  family: '#f4e3c3',
  friendships: '#dfeacb',
  work: '#cfe3e6',
  body_health: '#dcd8ee',
  self: '#f2efe6',
}

const MIN_RADIUS = 12
const MAX_RADIUS = 26
const FADE_AFTER_DAYS = 30
const FADE_OVER_DAYS = 335
const MIN_OPACITY = 0.45

/** Size grows with evidence count. */
export function landmarkRadius(evidenceCount: number): number {
  return Math.min(MIN_RADIUS + 2.6 * Math.sqrt(Math.max(evidenceCount, 0)), MAX_RADIUS)
}

/** A landmark fades as its last appearance gets older. */
export function landmarkOpacity(lastSeenAt: string | null | undefined, now: Date = new Date()): number {
  if (!lastSeenAt) return 1
  const days = (now.getTime() - new Date(lastSeenAt).getTime()) / 86_400_000
  if (days <= FADE_AFTER_DAYS) return 1
  const faded = Math.min((days - FADE_AFTER_DAYS) / FADE_OVER_DAYS, 1)
  return 1 - faded * (1 - MIN_OPACITY)
}

/** Zoomed out, only the largest landmarks carry a label. */
export function prominentIds(landmarks: Landmark[], limit = 12): Set<string> {
  const ranked = [...landmarks].sort((a, b) => b.evidence_count - a.evidence_count || a.name.localeCompare(b.name))
  return new Set(ranked.slice(0, limit).map((mark) => mark.id))
}

export function landmarkLabel(mark: Pick<Landmark, 'type' | 'name' | 'status'>): string {
  return `${TYPE_LABELS[mark.type]}: ${mark.name} (${STATUS_LABELS[mark.status].toLowerCase()})`
}

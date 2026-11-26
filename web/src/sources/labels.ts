import type { Source } from '../api/client'
import type { IconName } from '../icons'

export const STATUS_LABELS: Record<Source['status'], string> = {
  uploaded: 'Waiting for the file',
  transcribing: 'Transcribing',
  needs_speaker_check: 'Needs you: which voice is yours?',
  extracting: 'Extracting',
  placing: 'Placing on the map',
  ready: 'Ready',
  failed: 'Failed',
}

export const KIND_LABELS: Record<Source['kind'], string> = {
  therapy_session: 'Therapy session',
  voice_note: 'Voice note',
  journal: 'Journal entry',
  archive: 'Archive item',
}

export const KIND_ICONS: Record<Source['kind'], IconName> = {
  therapy_session: 'waveform',
  voice_note: 'mic',
  journal: 'page',
  archive: 'page',
}

export const STAGE_LABELS: Record<string, string> = {
  media: 'Prepare audio',
  transcribe: 'Transcribe',
  segment_text: 'Read text',
  import: 'Import test data',
  speakers: 'Identify voices',
  statements: 'Extract statements',
  concepts: 'Extract concepts',
  commit: 'Save to the atlas',
  embed: 'Index',
  place: 'Place on the map',
}

export function isSettled(status: Source['status']): boolean {
  return status === 'ready' || status === 'failed' || status === 'needs_speaker_check'
}

export function formatTime(ms: number | null | undefined): string {
  if (ms == null) return ''
  const total = Math.floor(ms / 1000)
  const minutes = Math.floor(total / 60)
  const seconds = String(total % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function formatLongDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'full' })
}

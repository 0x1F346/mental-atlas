import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { api, unwrap, type Source, type Transcript } from '../api/client'
import { Icon } from '../icons'
import {
  formatLongDate,
  formatTime,
  isSettled,
  KIND_ICONS,
  KIND_LABELS,
  STAGE_LABELS,
  STATUS_LABELS,
} from './labels'
import SpeakerCheck from './SpeakerCheck'

const ROLE_LABELS = { self: 'Me', therapist: 'Therapist', other: 'Other' } as const
const STEP_STATUS: Record<string, string> = { succeeded: 'Done', running: 'Working', failed: 'Failed' }

export default function SourcePage() {
  const { sourceId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [source, setSource] = useState<Source | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [missing, setMissing] = useState(false)
  const [tick, setTick] = useState(0)
  const refresh = useCallback(() => setTick((value) => value + 1), [])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false
    async function load() {
      const path = { source_id: sourceId }
      const result = await api.GET('/api/v1/sources/{source_id}', { params: { path } })
      if (cancelled) return
      if (!result.response.ok || !result.data) {
        setMissing(true)
        return
      }
      setSource(result.data)
      const text = await api.GET('/api/v1/sources/{source_id}/transcript', { params: { path } })
      if (cancelled) return
      if (text.data) setTranscript(text.data)
      if (!isSettled(result.data.status)) timer = setTimeout(load, 1500)
    }
    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [sourceId, tick])

  // A link from the evidence panel names a segment; bring it into view.
  const target = location.hash.replace('#', '')
  useEffect(() => {
    if (target && transcript) document.getElementById(target)?.scrollIntoView({ block: 'center' })
  }, [target, transcript])

  async function reprocess(stage: 'statements' | 'speakers') {
    unwrap(
      await api.POST('/api/v1/sources/{source_id}/reprocess', {
        params: { path: { source_id: sourceId } },
        body: { stage },
      }),
    )
    refresh()
  }

  async function remove() {
    if (!window.confirm('Retract this source and everything derived from it?')) return
    await api.DELETE('/api/v1/sources/{source_id}', { params: { path: { source_id: sourceId } } })
    navigate('/sources')
  }

  if (missing) {
    return (
      <div className="source-placeholder">
        <p>No such source.</p>
      </div>
    )
  }
  if (!source) return <div className="source-detail" aria-busy="true" />

  const speakers = transcript?.speakers ?? []
  const speakerById = new Map(speakers.map((speaker, index) => [speaker.id, { speaker, index }]))
  const voiceName = (id: string) => {
    const entry = speakerById.get(id)
    const role = entry?.speaker.role
    return { role: role ?? 'other', name: role ? ROLE_LABELS[role] : `Voice ${(entry?.index ?? 0) + 1}` }
  }
  // Test data has generated voices; there is nothing to listen to or swap.
  const hasVoices = speakers.length > 1 && source.kind !== 'archive'
  const stages = source.stages ?? []
  const steps = (
    <ol className="steps">
      {stages.map((stage) => (
        <li key={stage.stage} className={`step step-${stage.status}`}>
          <span className="step-mark" aria-hidden="true">
            {stage.status === 'succeeded' && <Icon name="supports" size={14} />}
          </span>
          <span>
            {STAGE_LABELS[stage.stage] ?? stage.stage}
            <span className="step-status">
              {STEP_STATUS[stage.status] ?? stage.status}
              {stage.error ? ` (${stage.error})` : ''}
            </span>
          </span>
        </li>
      ))}
    </ol>
  )

  return (
    <article className="source-detail">
      <header className="source-head">
        <p className="eyebrow eyebrow-icon">
          <Icon name={KIND_ICONS[source.kind]} size={14} />
          {KIND_LABELS[source.kind]} · {source.audio_media_id ? 'Audio' : 'Text'}
        </p>
        <h1>{source.title}</h1>
        <p className="source-meta">
          {formatLongDate(source.occurred_at)}
          {source.duration_ms ? ` · ${formatTime(source.duration_ms)}` : ''}
        </p>
        <div className="row source-chips">
          <span className={`status status-${source.status}`} data-testid="source-status">
            {STATUS_LABELS[source.status]}
          </span>
          {speakers.length > 0 && <span className="eyebrow">Speakers</span>}
          {speakers.map((speaker) => {
            const voice = voiceName(speaker.id)
            return (
              <span key={speaker.id} className={`voice-chip speaker speaker-${voice.role}`}>
                {voice.name}
              </span>
            )
          })}
        </div>
      </header>

      {stages.length > 0 && (
        <section aria-label="Processing steps">
          {source.status === 'ready' ? (
            <details className="steps-details">
              <summary>How it was processed</summary>
              {steps}
            </details>
          ) : (
            steps
          )}
        </section>
      )}

      {source.status === 'needs_speaker_check' && (
        <SpeakerCheck source={source} speakers={speakers} required onDone={refresh} />
      )}

      <div className="row source-actions">
        {source.status === 'ready' && (
          <Link to="/" className="button-link">
            Open the map
          </Link>
        )}
        {(source.status === 'ready' || source.status === 'failed') && speakers.length > 0 && (
          <button type="button" className="quiet" onClick={() => reprocess('statements')}>
            Extract again
          </button>
        )}
        <button type="button" className="quiet danger" onClick={remove}>
          Retract this source
        </button>
      </div>

      {transcript && transcript.segments.length > 0 && (
        <section aria-label="Transcript" className="transcript-section">
          <h2 className="visually-hidden">Transcript</h2>
          <ol className={`transcript${transcript.segments.some((item) => item.start_ms != null) ? ' timed' : ''}`}>
            {transcript.segments.map((segment) => {
              const voice = voiceName(segment.speaker_id)
              const isTarget = target === `segment-${segment.id}`
              return (
                <li key={segment.id} id={`segment-${segment.id}`} className={isTarget ? 'segment target' : 'segment'}>
                  {segment.start_ms != null && <span className="segment-time">{formatTime(segment.start_ms)}</span>}
                  <div>
                    <span className={`who speaker speaker-${voice.role}`}>
                      {voice.name}
                      {isTarget && <span className="opened">Opened from the atlas</span>}
                    </span>
                    <p>{segment.text}</p>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      {hasVoices && source.status !== 'needs_speaker_check' && isSettled(source.status) && (
        <SpeakerCheck source={source} speakers={speakers} required={false} onDone={refresh} />
      )}
    </article>
  )
}

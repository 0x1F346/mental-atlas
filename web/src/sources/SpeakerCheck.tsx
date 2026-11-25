import { useRef, useState } from 'react'

import { api, unwrap, type Source, type Speaker } from '../api/client'

const CLIP_SECONDS = 8

interface Props {
  source: Source
  speakers: Speaker[]
  /** True while the pipeline is waiting for this answer; false when swapping later. */
  required: boolean
  onDone: () => void
}

/** Asks which voice is the owner. The only manual step in the pipeline. */
export default function SpeakerCheck({ source, speakers, required, onDone }: Props) {
  const audio = useRef<HTMLAudioElement>(null)
  const stopAt = useRef<number | null>(null)
  const current = speakers.find((speaker) => speaker.role === 'self')
  const [mine, setMine] = useState<string | null>(current?.id ?? null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function play(speaker: Speaker) {
    if (!source.audio_media_id || !audio.current) return
    const link = unwrap(
      await api.GET('/api/v1/media/{media_id}/link', {
        params: { path: { media_id: source.audio_media_id } },
      }),
    )
    const start = (speaker.first_start_ms ?? 0) / 1000
    const element = audio.current
    if (!element.src || element.dataset.mediaId !== source.audio_media_id) {
      element.src = link.url
      element.dataset.mediaId = source.audio_media_id
    }
    stopAt.current = start + CLIP_SECONDS
    element.currentTime = start
    await element.play()
  }

  async function save() {
    if (!mine) return
    setBusy(true)
    setError(null)
    const others = speakers.filter((speaker) => speaker.id !== mine)
    const roles: Record<string, 'self' | 'therapist' | 'other'> = { [mine]: 'self' }
    others.forEach((speaker, index) => {
      roles[speaker.id] = source.kind === 'therapy_session' && index === 0 ? 'therapist' : 'other'
    })
    try {
      unwrap(
        await api.PUT('/api/v1/sources/{source_id}/speakers', {
          params: { path: { source_id: source.id } },
          body: { roles },
        }),
      )
      onDone()
    } catch {
      setError('Could not save the voices.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card stack" aria-label="Which voice is yours?">
      <h2>{required ? 'Which voice is yours?' : 'Voices'}</h2>
      {required && (
        <p>The voices could not be told apart with confidence. Listen to each, then choose yours.</p>
      )}
      <audio
        ref={audio}
        onTimeUpdate={(event) => {
          const element = event.currentTarget
          if (stopAt.current != null && element.currentTime >= stopAt.current) {
            element.pause()
            stopAt.current = null
          }
        }}
      />
      {speakers.map((speaker, index) => (
        <div key={speaker.id} className="row">
          <label className="inline">
            <input
              type="radio"
              name="mine"
              checked={mine === speaker.id}
              onChange={() => setMine(speaker.id)}
            />
            Voice {index + 1} is me
          </label>
          {source.audio_media_id && (
            <button type="button" className="quiet" onClick={() => play(speaker)}>
              Play voice {index + 1}
            </button>
          )}
        </div>
      ))}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="button" disabled={!mine || busy || (!required && mine === current?.id)} onClick={save}>
        {required ? 'Continue' : 'Swap voices and reprocess'}
      </button>
    </section>
  )
}

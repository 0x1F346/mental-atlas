import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, ApiFailure, unwrap, type Source } from '../api/client'
import { KIND_LABELS } from './labels'

type Kind = Source['kind']
const FILE_KINDS: Kind[] = ['therapy_session', 'voice_note']

export default function UploadForm() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'file' | 'text'>('file')
  const [kind, setKind] = useState<Kind>('therapy_session')
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [names, setNames] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiFailure | Error | null>(null)

  function chooseMode(next: 'file' | 'text') {
    setMode(next)
    setKind(next === 'text' ? 'journal' : 'therapy_session')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const common = {
      kind,
      title,
      occurred_at: new Date(`${date}T12:00:00`).toISOString(),
      expected_names: names
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean),
    }
    try {
      if (mode === 'text') {
        const created = unwrap(await api.POST('/api/v1/sources', { body: { ...common, text } }))
        navigate(`/sources/${created.source.id}`)
        return
      }
      if (!file) throw new Error('Choose a file.')
      const contentType = file.type || 'application/octet-stream'
      const created = unwrap(
        await api.POST('/api/v1/sources', { body: { ...common, content_type: contentType } }),
      )
      const upload = created.upload
      if (!upload) throw new Error('The server did not return an upload link.')
      // The file goes straight to object storage through the signed link.
      const put = await fetch(upload.url, { method: upload.method, headers: upload.headers, body: file })
      if (!put.ok) throw new Error('The upload failed.')
      unwrap(
        await api.POST('/api/v1/sources/{source_id}/complete', {
          params: { path: { source_id: created.source.id } },
        }),
      )
      navigate(`/sources/${created.source.id}`)
    } catch (failure) {
      setError(failure instanceof Error ? failure : new Error('Something went wrong.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="stack card" aria-label="Add a source">
      <h2>Add a source</h2>
      <div className="row" role="radiogroup" aria-label="Input">
        <label className="inline">
          <input type="radio" checked={mode === 'file'} onChange={() => chooseMode('file')} />
          Recording
        </label>
        <label className="inline">
          <input type="radio" checked={mode === 'text'} onChange={() => chooseMode('text')} />
          Text
        </label>
      </div>
      {mode === 'file' && (
        <label>
          Kind
          <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            {FILE_KINDS.map((value) => (
              <option key={value} value={value}>
                {KIND_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </label>
      <label>
        Date it happened
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      {mode === 'file' ? (
        <>
          <label>
            Audio or video file
            <input
              type="file"
              accept="audio/*,video/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
          <label>
            Names to expect (optional, comma-separated)
            <input value={names} onChange={(e) => setNames(e.target.value)} />
          </label>
        </>
      ) : (
        <label>
          Text
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} required />
        </label>
      )}
      {error && (
        <p role="alert" className="error">
          {error.message}{' '}
          {error instanceof ApiFailure && error.sourceId && (
            <Link to={`/sources/${error.sourceId}`}>Open the existing source</Link>
          )}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? 'Uploading…' : 'Add'}
      </button>
    </form>
  )
}

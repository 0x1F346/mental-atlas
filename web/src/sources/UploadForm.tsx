import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, ApiFailure, unwrap, type Source } from '../api/client'
import { Icon } from '../icons'
import { KIND_LABELS } from './labels'

type Kind = Source['kind']
const FILE_KINDS: Kind[] = ['therapy_session', 'voice_note']
type Mode = 'file' | 'text' | 'test'
const MODE_KINDS: Record<Mode, Kind> = { file: 'therapy_session', text: 'journal', test: 'archive' }
const TEST_DATA_HINT = `{
  "person": [{ "name": "Dana", "life_area": "work" }],
  "feeling": ["dread", { "name": "shame", "status": "hypothesis" }],
  "relationships": [{ "type": "ABOUT", "from": "dread", "to": "Dana" }]
}`

export default function UploadForm() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('file')
  const [kind, setKind] = useState<Kind>('therapy_session')
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [names, setNames] = useState('')
  const [text, setText] = useState('')
  const [testData, setTestData] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiFailure | Error | null>(null)

  function chooseMode(next: Mode) {
    setMode(next)
    setKind(MODE_KINDS[next])
    setError(null)
  }

  async function readJsonFile(chosen: File | null) {
    if (chosen) setTestData(await chosen.text())
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
      if (mode === 'test') {
        let blob: Record<string, unknown>
        try {
          blob = JSON.parse(testData) as Record<string, unknown>
        } catch {
          throw new Error('That is not valid JSON.')
        }
        const created = unwrap(await api.POST('/api/v1/sources', { body: { ...common, test_data: blob } }))
        navigate(`/sources/${created.source.id}`)
        return
      }
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
    <form onSubmit={submit} className="stack upload-card" aria-label="Add a source">
      <div className="upload-head">
        <span className="upload-mark">
          <Icon name="upload" size={18} />
        </span>
        <h2>Add a recording, voice note or journal page</h2>
      </div>
      <div className="segmented" role="radiogroup" aria-label="Input">
        <label className="inline">
          <input type="radio" checked={mode === 'file'} onChange={() => chooseMode('file')} />
          Recording
        </label>
        <label className="inline">
          <input type="radio" checked={mode === 'text'} onChange={() => chooseMode('text')} />
          Text
        </label>
        <label className="inline">
          <input type="radio" checked={mode === 'test'} onChange={() => chooseMode('test')} />
          Test data
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
      {mode === 'test' && (
        <>
          <p className="muted">
            Concepts by type as JSON arrays (<code>person</code>, <code>feeling</code>, <code>belief</code>…), with
            optional <code>relationships</code>. Nothing is sent to a model. A full example is in{' '}
            <code>evals/fixtures/synthetic/test_data.example.json</code>.
          </p>
          <label>
            JSON file (optional)
            <input
              type="file"
              accept="application/json,.json"
              onChange={(e) => readJsonFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label>
            Test data
            <textarea
              value={testData}
              onChange={(e) => setTestData(e.target.value)}
              rows={10}
              placeholder={TEST_DATA_HINT}
              spellCheck={false}
              className="code"
              required
            />
          </label>
        </>
      )}
      {mode === 'test' ? null : mode === 'file' ? (
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

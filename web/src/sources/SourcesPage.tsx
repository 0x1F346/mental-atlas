import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, unwrap, type Source } from '../api/client'
import { formatDate, isSettled, KIND_LABELS, STATUS_LABELS } from './labels'
import UploadForm from './UploadForm'

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false
    async function load() {
      try {
        const rows = unwrap(await api.GET('/api/v1/sources'))
        if (cancelled) return
        setSources(rows)
        if (rows.some((row) => !isSettled(row.status))) timer = setTimeout(load, 2000)
      } catch {
        if (!cancelled) setError('Could not load sources.')
      }
    }
    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [])

  return (
    <main className="page">
      <h1>Sources</h1>
      <UploadForm />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {sources && sources.length === 0 && <p className="muted">Nothing uploaded yet.</p>}
      {sources && sources.length > 0 && (
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.id}>
              <Link to={`/sources/${source.id}`}>{source.title}</Link>
              <span className="muted">
                {KIND_LABELS[source.kind]} · {formatDate(source.occurred_at)}
              </span>
              <span className={`status status-${source.status}`}>{STATUS_LABELS[source.status]}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}

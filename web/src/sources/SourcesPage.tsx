import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useParams } from 'react-router-dom'

import { api, unwrap, type Source } from '../api/client'
import { Icon } from '../icons'
import { formatDate, formatTime, isSettled, KIND_ICONS, STATUS_LABELS } from './labels'
import UploadForm from './UploadForm'

/**
 * The Sources page: the list and the upload form on the left, the open source on the right.
 * `/sources` shows a prompt in the right column and `/sources/:sourceId` shows that source.
 */
export default function SourcesPage() {
  const { pathname } = useLocation()
  const { sourceId } = useParams()
  const [sources, setSources] = useState<Source[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Reload when the open source changes, so a new upload appears at once, and keep
  // polling while anything is still being processed.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false
    async function load() {
      try {
        const rows = unwrap(await api.GET('/api/v1/sources'))
        if (cancelled) return
        setSources(rows)
        setError(null)
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
  }, [pathname])

  const inProgress = sources?.filter((source) => source.status !== 'ready') ?? []
  const ready = sources?.filter((source) => source.status === 'ready') ?? []

  return (
    <main className={`sources-layout${sourceId ? ' has-open' : ''}`}>
      <div className="sources-side">
        <header>
          <h1>Sources</h1>
          <p className="lede">Everything the atlas is drawn from. Each landmark traces back to a quote in one of these.</p>
        </header>
        <UploadForm />
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {sources && sources.length === 0 && <p className="muted">Nothing uploaded yet.</p>}
        {inProgress.length > 0 && <SourceList id="in-progress" heading="Processing" sources={inProgress} />}
        {ready.length > 0 && <SourceList id="in-atlas" heading="In the atlas" sources={ready} />}
      </div>
      <div className="sources-main">
        <Outlet />
      </div>
    </main>
  )
}

function SourceList({ id, heading, sources }: { id: string; heading: string; sources: Source[] }) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="eyebrow">
        {heading}
      </h2>
      <ul className="source-list">
        {sources.map((source) => (
          <li key={source.id}>
            <NavLink to={`/sources/${source.id}`} className="source-card">
              <span className="source-icon">
                <Icon name={KIND_ICONS[source.kind]} size={16} />
              </span>
              <span className="source-card-text">
                <span className="source-card-title">{source.title}</span>
                <span className="source-card-meta">
                  {formatDate(source.occurred_at)}
                  {source.duration_ms ? ` · ${formatTime(source.duration_ms)}` : ''}
                  {source.status !== 'ready' && ` · ${STATUS_LABELS[source.status]}`}
                </span>
              </span>
            </NavLink>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The right column when no source is open. */
export function NoSourceOpen() {
  return (
    <div className="source-placeholder">
      <Icon name="waveform" size={28} />
      <p>Open a source to read its transcript, or add a new one.</p>
    </div>
  )
}

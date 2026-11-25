import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, unwrap } from '../api/client'
import { formatDate, formatTime } from '../sources/labels'
import { NOTICED_LABELS, TYPE_LABELS } from './appearance'
import type { Evidence, EvidenceItem, NodeDetail, Relationship } from './types'

const SPEAKERS = { self: 'Me', therapist: 'My therapist', other: 'Someone else' } as const
const RELATIONSHIP_PHRASES: Record<string, [string, string]> = {
  LED_TO: ['Led to', 'Came after'],
  OCCURRED_IN: ['Showed up during', 'What showed up'],
  ABOUT: ['About', 'What is about this'],
  CAME_FROM: ['Came from', 'What came from this'],
  HOLDS: ['Holds', 'Held by'],
  HAS: ['Has', 'Belongs to'],
  BELONGS_TO: ['Belongs to', 'Members'],
  INVOLVES: ['Involves', 'Part of'],
  PART_OF: ['Part of', 'Includes'],
  SERVES: ['Serves the need', 'Served by'],
  HELPS: ['Helps', 'Helped by'],
  BLOCKS: ['Blocks', 'Blocked by'],
  CONFLICTS_WITH: ['Conflicts with', 'Conflicts with'],
}

function groupRelationships(relationships: Relationship[]): [string, Relationship[]][] {
  const groups = new Map<string, Relationship[]>()
  for (const relationship of relationships) {
    const phrases = RELATIONSHIP_PHRASES[relationship.type] ?? [relationship.type, relationship.type]
    const heading = relationship.direction === 'out' ? phrases[0] : phrases[1]
    groups.set(heading, [...(groups.get(heading) ?? []), relationship])
  }
  return [...groups.entries()]
}

interface Props {
  /** The selected concept; null when a relationship line is selected instead. */
  node: NodeDetail | null
  evidence: Evidence
  onSelectNode: (id: string) => void
  onSelectEdge: (edgeId: string) => void
  onClose: () => void
}

/** The quotes behind a concept or a relationship, each traceable to its moment in a source. */
export default function EvidencePanel({ node, evidence, onSelectNode, onSelectEdge, onClose }: Props) {
  const audio = useRef<HTMLAudioElement>(null)
  const stopAt = useRef<number | null>(null)
  const [playing, setPlaying] = useState<string | null>(null)
  const [audioError, setAudioError] = useState(false)

  async function play(item: EvidenceItem) {
    const element = audio.current
    if (!element || !item.audio_media_id) return
    if (playing === item.id) {
      element.pause()
      setPlaying(null)
      return
    }
    try {
      if (element.dataset.mediaId !== item.audio_media_id) {
        // Signed links are short-lived, so one is fetched at the moment of playing.
        const link = unwrap(
          await api.GET('/api/v1/media/{media_id}/link', {
            params: { path: { media_id: item.audio_media_id } },
          }),
        )
        element.src = link.url
        element.dataset.mediaId = item.audio_media_id
      }
      const start = (item.start_ms ?? 0) / 1000
      stopAt.current = item.end_ms != null ? item.end_ms / 1000 + 0.4 : null
      element.currentTime = start
      await element.play()
      setPlaying(item.id)
      setAudioError(false)
    } catch {
      setAudioError(true)
      setPlaying(null)
    }
  }

  return (
    <aside className="evidence-panel" aria-label="Evidence">
      <button type="button" className="quiet close" onClick={onClose} aria-label="Close the panel">
        ×
      </button>
      <p className="muted kind">
        {node ? TYPE_LABELS[node.type] : 'Relationship'}
        {node?.kind ? ` · ${node.kind.replace('_', ' ')}` : ''}
      </p>
      <h2>{evidence.title}</h2>
      {node?.aliases && node.aliases.length > 0 && (
        <p className="muted">Also called {node.aliases.join(', ')}</p>
      )}
      {node?.description && <p>{node.description}</p>}
      <p className={`status-line${evidence.is_hypothesis ? ' hypothesis' : ''}`} data-testid="status-line">
        {evidence.status_line}
      </p>

      {node && (
        <dl className="facts">
          <dt>Noticed by</dt>
          <dd>
            {node.noticed_by.length > 0
              ? node.noticed_by.map((who) => NOTICED_LABELS[who]).join(', ')
              : 'Nobody yet'}
          </dd>
          <dt>First seen</dt>
          <dd>{node.first_seen_at ? formatDate(node.first_seen_at) : 'Never'}</dd>
          <dt>Last seen</dt>
          <dd>{node.last_seen_at ? formatDate(node.last_seen_at) : 'Never'}</dd>
          <dt>Times</dt>
          <dd>{node.evidence_count}</dd>
        </dl>
      )}

      {node && node.relationships.length > 0 && (
        <section aria-label="Related">
          <h3>Related</h3>
          {groupRelationships(node.relationships).map(([heading, items]) => (
            <div key={heading} className="related-group">
              <h4>{heading}</h4>
              <ul>
                {items.map((relationship) => (
                  <li key={relationship.edge_id}>
                    <button type="button" className="linklike" onClick={() => onSelectNode(relationship.other.id)}>
                      {relationship.other.name}
                    </button>
                    {relationship.is_hypothesis && <span className="tag hypothesis">Hypothesis</span>}
                    {relationship.valid_to && <span className="tag">until {formatDate(relationship.valid_to)}</span>}
                    <button
                      type="button"
                      className="linklike muted"
                      onClick={() => onSelectEdge(relationship.edge_id)}
                    >
                      why?
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      <section aria-label="Quotes">
        <h3>
          Quotes <span className="muted">({evidence.items.length})</span>
        </h3>
        <audio
          ref={audio}
          onPause={() => setPlaying(null)}
          onTimeUpdate={(event) => {
            const element = event.currentTarget
            if (stopAt.current != null && element.currentTime >= stopAt.current) {
              element.pause()
              stopAt.current = null
            }
          }}
        />
        {audioError && (
          <p role="alert" className="error">
            The recording could not be played.
          </p>
        )}
        {evidence.items.length === 0 && <p className="muted">Nothing has been said about this yet.</p>}
        <ul className="quotes">
          {evidence.items.map((item) => (
            <li key={item.id} className={`quote stance-${item.stance}`}>
              <blockquote>“{item.quote}”</blockquote>
              <p className="muted quote-meta">
                {SPEAKERS[item.speaker_role]} · {formatDate(item.said_at)} · {item.source_title}
              </p>
              <p className="quote-tags">
                <span className={`tag stance-${item.stance}`}>
                  {item.stance === 'supports' ? 'Supports' : 'Contradicts'}
                </span>
                <span className={`tag basis-${item.basis}`}>
                  {item.basis === 'explicit' ? 'Said directly' : 'Implied'}
                </span>
                {item.audio_media_id && (
                  <button type="button" className="quiet small" onClick={() => play(item)}>
                    {playing === item.id ? 'Pause' : `Play from ${formatTime(item.start_ms)}`}
                  </button>
                )}
                <Link to={`/sources/${item.source_id}#segment-${item.segment_id}`}>In the transcript</Link>
              </p>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  )
}

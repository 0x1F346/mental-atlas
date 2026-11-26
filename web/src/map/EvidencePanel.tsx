import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, unwrap } from '../api/client'
import { LIFE_AREA_LABELS } from '../api/generated/vocabulary'
import { Icon, typeIcon } from '../icons'
import { formatDate, formatTime } from '../sources/labels'
import { NOTICED_LABELS, TYPE_LABELS, typeColour } from './appearance'
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

/** Newest first. Quotes said at the same moment keep the order the API gave them. */
function newestFirst(items: EvidenceItem[]): EvidenceItem[] {
  return [...items].sort((a, b) => Date.parse(b.said_at) - Date.parse(a.said_at))
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

  const quotes = newestFirst(evidence.items)
  const supports = quotes.filter((item) => item.stance === 'supports').length
  const sourceCount = new Set(quotes.map((item) => item.source_id)).size
  const oldest = quotes.at(-1)
  const newest = quotes[0]

  return (
    <aside className="evidence-panel" aria-label="Evidence">
      <header className="panel-head">
        <div className="panel-kicker">
          <p className="kind">
            {node && <Icon name={typeIcon(node.type)} size={15} />}
            {node ? TYPE_LABELS[node.type] : 'Relationship'}
            {node?.kind ? ` · ${node.kind.replace('_', ' ')}` : ''}
            {node ? ` · ${LIFE_AREA_LABELS[node.life_area]}` : ''}
          </p>
          <button type="button" className="icon-button close" onClick={onClose} aria-label="Close the panel">
            <Icon name="close" size={20} />
          </button>
        </div>
        <h2>{evidence.title}</h2>
        {node?.aliases && node.aliases.length > 0 && (
          <p className="muted">Also called {node.aliases.join(', ')}</p>
        )}
        {node?.description && <p className="description">{node.description}</p>}
        <StatusLine status={evidence.status} line={evidence.status_line} hypothesis={evidence.is_hypothesis} />
      </header>

      {node && (
        <dl className="facts">
          <div>
            <dt>Noticed by</dt>
            <dd>
              {node.noticed_by.length > 0
                ? node.noticed_by.map((who) => NOTICED_LABELS[who]).join(', ')
                : 'Nobody yet'}
            </dd>
          </div>
          <div>
            <dt>Seen</dt>
            <dd>{node.evidence_count === 1 ? 'Once' : `${node.evidence_count} times`}</dd>
            {sourceCount > 0 && (
              <dd className="sub">{sourceCount === 1 ? 'in 1 source' : `across ${sourceCount} sources`}</dd>
            )}
          </div>
          <div>
            <dt>First seen</dt>
            <dd>{node.first_seen_at ? formatDate(node.first_seen_at) : 'Never'}</dd>
            {oldest && <dd className="sub">{oldest.source_title}</dd>}
          </div>
          <div>
            <dt>Last seen</dt>
            <dd>{node.last_seen_at ? formatDate(node.last_seen_at) : 'Never'}</dd>
            {newest && <dd className="sub">{newest.source_title}</dd>}
          </div>
        </dl>
      )}

      {node && node.relationships.length > 0 && (
        <section aria-label="Related" className="panel-section">
          <h3>Related</h3>
          {groupRelationships(node.relationships).map(([heading, items]) => (
            <div key={heading} className="related-group">
              <h4>{heading}</h4>
              <ul>
                {items.map((relationship) => (
                  <li key={relationship.edge_id}>
                    <button
                      type="button"
                      className={`chip${relationship.is_hypothesis ? ' hypothesis' : ''}`}
                      onClick={() => onSelectNode(relationship.other.id)}
                    >
                      <span style={{ color: typeColour(relationship.other.type) }}>
                        <Icon name={typeIcon(relationship.other.type)} size={14} />
                      </span>
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

      <section aria-label="Quotes" className="panel-section">
        <div className="section-head">
          <h3>Quotes</h3>
          {quotes.length > 0 && (
            <span className="muted">
              {supports} support · {quotes.length - supports} contradict · newest first
            </span>
          )}
        </div>
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
        {quotes.length === 0 && <p className="muted">Nothing has been said about this yet.</p>}
        <ul className="quotes">
          {quotes.map((item) => (
            <li key={item.id} className={`quote stance-${item.stance}`}>
              <div className="quote-head">
                <p className="quote-meta">
                  <span className={`speaker speaker-${item.speaker_role}`}>{SPEAKERS[item.speaker_role]}</span>
                  <span>{formatDate(item.said_at)}</span>
                  <span className="quote-source">
                    <Icon name={item.audio_media_id ? 'waveform' : 'page'} size={14} />
                    {item.source_title}
                  </span>
                </p>
                <p className="quote-tags">
                  <span className={`stance stance-${item.stance}`}>
                    <Icon name={item.stance === 'supports' ? 'supports' : 'contradicts'} size={14} />
                    {item.stance === 'supports' ? 'Supports' : 'Contradicts'}
                  </span>
                  <span className={`tag basis-${item.basis}`}>
                    {item.basis === 'explicit' ? 'Said directly' : 'Implied'}
                  </span>
                </p>
              </div>
              <blockquote>“{item.quote}”</blockquote>
              <div className="quote-actions">
                {item.audio_media_id && (
                  <button type="button" className="play" onClick={() => play(item)}>
                    <span className="play-dot">
                      <Icon name={playing === item.id ? 'pause' : 'play'} size={14} />
                    </span>
                    {playing === item.id ? 'Pause' : `Play from ${formatTime(item.start_ms)}`}
                  </button>
                )}
                <Link to={`/sources/${item.source_id}#segment-${item.segment_id}`} className="to-transcript">
                  Open in transcript
                  <Icon name="arrow" size={15} />
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  )
}

/** "Hypothesis: nobody has said this directly." with its first word set apart. */
function StatusLine({ status, line, hypothesis }: { status: string; line: string; hypothesis: boolean }) {
  const cut = line.indexOf(':')
  return (
    <p className={`status-line${hypothesis ? ' hypothesis' : ''}`} data-testid="status-line">
      <span className={`status-mark status-${status}`} aria-hidden="true" />
      <span>
        {cut > 0 ? (
          <>
            <strong>{line.slice(0, cut + 1)}</strong>
            {line.slice(cut + 1)}
          </>
        ) : (
          line
        )}
      </span>
    </p>
  )
}

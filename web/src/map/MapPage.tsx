import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, unwrap, type Source } from '../api/client'
import { NODE_TYPES, type NodeType } from '../api/generated/vocabulary'
import { Icon, typeIcon } from '../icons'
import { MAIN_TYPES, NOTICED_LABELS, TYPE_LABELS, typeColour } from './appearance'
import EvidencePanel from './EvidencePanel'
import Legend from './Legend'
import SvgMapRenderer from './SvgMapRenderer'
import type { Evidence, Landmark, MapDocument, MapRenderer, NodeDetail, RelationshipLine } from './types'

// The one place the renderer is chosen.
const Renderer: MapRenderer = SvgMapRenderer

type Noticed = keyof typeof NOTICED_LABELS
const NOTICED: Noticed[] = ['self', 'therapist', 'ai']

interface Filters {
  types: Set<NodeType>
  noticed: Set<Noticed>
  sourceId: string
}

export function hiddenLandmarks(landmarks: Landmark[], filters: Filters): Set<string> {
  const hidden = new Set<string>()
  for (const mark of landmarks) {
    if (mark.is_self) continue
    const typeHidden = filters.types.size > 0 && !filters.types.has(mark.type)
    const noticedHidden =
      filters.noticed.size > 0 && !mark.noticed_by.some((who) => filters.noticed.has(who))
    const sourceHidden = filters.sourceId !== '' && !mark.source_ids.includes(filters.sourceId)
    if (typeHidden || noticedHidden || sourceHidden) hidden.add(mark.id)
  }
  return hidden
}

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}

export default function MapPage() {
  const [map, setMap] = useState<MapDocument | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [failed, setFailed] = useState(false)
  const [filters, setFilters] = useState<Filters>({ types: new Set(), noticed: new Set(), sourceId: '' })
  const [nodeId, setNodeId] = useState<string | null>(null)
  const [edgeId, setEdgeId] = useState<string | null>(null)
  const [node, setNode] = useState<NodeDetail | null>(null)
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  // On phones the filters start folded away so the map can be seen; elsewhere they always show.
  const [filtersFolded, setFiltersFolded] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.GET('/api/v1/map'), api.GET('/api/v1/sources')])
      .then(([mapResult, sourceResult]) => {
        if (cancelled) return
        setMap(unwrap(mapResult))
        setSources(unwrap(sourceResult))
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  // The selected concept's neighbours, and the quotes behind whatever is selected.
  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!nodeId) {
        setNode(null)
        setEvidence(null)
        return
      }
      const path = { node_id: nodeId }
      const detail = unwrap(await api.GET('/api/v1/nodes/{node_id}', { params: { path } }))
      const quotes = edgeId
        ? unwrap(await api.GET('/api/v1/edges/{edge_id}/evidence', { params: { path: { edge_id: edgeId } } }))
        : unwrap(await api.GET('/api/v1/nodes/{node_id}/evidence', { params: { path } }))
      if (cancelled) return
      setNode(detail)
      setEvidence(quotes)
    }
    load().catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [nodeId, edgeId])

  const hidden = useMemo(() => (map ? hiddenLandmarks(map.landmarks, filters) : new Set<string>()), [map, filters])
  const typesPresent = useMemo(
    () => NODE_TYPES.filter((type) => map?.landmarks.some((mark) => mark.type === type)),
    [map],
  )
  const lines: RelationshipLine[] = useMemo(
    () =>
      node && node.id === nodeId
        ? node.relationships.map((relationship) => ({
            edgeId: relationship.edge_id,
            type: relationship.type,
            otherId: relationship.other.id,
            isHypothesis: relationship.is_hypothesis,
          }))
        : [],
    [node, nodeId],
  )

  function selectNode(id: string | null) {
    setNodeId(id)
    setEdgeId(null)
  }

  if (failed) {
    return (
      <main className="page">
        <p role="alert" className="error">
          Could not load the map.
        </p>
      </main>
    )
  }
  if (!map) return <main className="page" aria-busy="true" />

  const concepts = map.landmarks.filter((mark) => !mark.is_self).length
  const mainTypes = typesPresent.filter((type) => MAIN_TYPES.includes(type))
  const otherTypes = typesPresent.filter((type) => !MAIN_TYPES.includes(type))
  const otherChosen = otherTypes.filter((type) => filters.types.has(type)).length
  const typeChip = (type: NodeType) => (
    <button
      key={type}
      type="button"
      className="chip"
      aria-pressed={filters.types.has(type)}
      onClick={() => setFilters({ ...filters, types: toggle(filters.types, type) })}
    >
      <span style={{ color: typeColour(type) }}>
        <Icon name={typeIcon(type)} size={15} />
      </span>
      {TYPE_LABELS[type]}
    </button>
  )

  return (
    <main className="map-page">
      <div className="map-body">
        <div className="map-area">
          <Renderer
            document={map}
            hiddenIds={hidden}
            selectedNodeId={nodeId}
            selectedEdgeId={edgeId}
            lines={lines}
            onSelectNode={selectNode}
            onSelectEdge={setEdgeId}
          />

          <section className={`map-toolbar glass${filtersFolded ? ' folded' : ''}`} aria-label="Filters">
            <button
              type="button"
              className="chip filters-toggle"
              aria-expanded={!filtersFolded}
              onClick={() => setFiltersFolded(!filtersFolded)}
            >
              Filters · {concepts - hidden.size} of {concepts}
            </button>
            <div className="filter-row" role="group" aria-label="Filter by type">
              <span className="filter-label">Type</span>
              {mainTypes.map(typeChip)}
              {otherTypes.length > 0 && (
                <button
                  type="button"
                  className="chip"
                  aria-expanded={moreOpen}
                  aria-controls="more-types"
                  onClick={() => setMoreOpen(!moreOpen)}
                >
                  More types{otherChosen > 0 ? ` · ${otherChosen}` : ''}
                </button>
              )}
            </div>
            {moreOpen && otherTypes.length > 0 && (
              <div id="more-types" className="filter-row more-types" role="group" aria-label="More types">
                {otherTypes.map(typeChip)}
              </div>
            )}
            <div className="filter-row">
              <div className="filter-row" role="group" aria-label="Filter by who noticed it">
                <span className="filter-label">Noticed by</span>
                <button
                  type="button"
                  className="chip"
                  aria-pressed={filters.noticed.size === 0}
                  onClick={() => setFilters({ ...filters, noticed: new Set() })}
                >
                  Anyone
                </button>
                {NOTICED.map((who) => (
                  <button
                    key={who}
                    type="button"
                    className="chip"
                    aria-pressed={filters.noticed.has(who)}
                    onClick={() => setFilters({ ...filters, noticed: toggle(filters.noticed, who) })}
                  >
                    {NOTICED_LABELS[who]}
                  </button>
                ))}
              </div>
              <label className="filter-row filter-source">
                <span className="filter-label">Source</span>
                <select value={filters.sourceId} onChange={(e) => setFilters({ ...filters, sourceId: e.target.value })}>
                  <option value="">All sources</option>
                  {sources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.title}
                    </option>
                  ))}
                </select>
              </label>
              <span className="map-count" data-testid="map-count">
                {concepts - hidden.size} of {concepts} concepts
              </span>
            </div>
          </section>

          {concepts === 0 && (
            <p className="map-empty glass">
              Nothing on the map yet. <Link to="/sources">Add a source</Link> to begin.
            </p>
          )}
          <Legend />
        </div>
        {evidence && nodeId && (
          <EvidencePanel
            node={edgeId ? null : node}
            evidence={evidence}
            onSelectNode={selectNode}
            onSelectEdge={setEdgeId}
            onClose={() => selectNode(null)}
          />
        )}
      </div>
    </main>
  )
}

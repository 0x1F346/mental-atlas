import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, unwrap, type Source } from '../api/client'
import { NODE_TYPES, type NodeType } from '../api/generated/vocabulary'
import { NOTICED_LABELS, TYPE_LABELS } from './appearance'
import EvidencePanel from './EvidencePanel'
import Legend from './Legend'
import type { Evidence, Landmark, MapDocument, MapRenderer, NodeDetail, RelationshipLine } from './types'

// The one place the renderer is chosen. It is loaded on demand: the WebGL library is large.
const Renderer: MapRenderer = lazy(() => import('./ForceGraphRenderer'))

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
  return (
    <main className="map-page">
      <section className="map-toolbar" aria-label="Filters">
        <fieldset>
          <legend>Type</legend>
          {typesPresent.map((type) => (
            <label key={type} className="inline chip">
              <input
                type="checkbox"
                checked={filters.types.has(type)}
                onChange={() => setFilters({ ...filters, types: toggle(filters.types, type) })}
              />
              {TYPE_LABELS[type]}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Noticed by</legend>
          {NOTICED.map((who) => (
            <label key={who} className="inline chip">
              <input
                type="checkbox"
                checked={filters.noticed.has(who)}
                onChange={() => setFilters({ ...filters, noticed: toggle(filters.noticed, who) })}
              />
              {NOTICED_LABELS[who]}
            </label>
          ))}
        </fieldset>
        <label className="inline">
          Source
          <select value={filters.sourceId} onChange={(e) => setFilters({ ...filters, sourceId: e.target.value })}>
            <option value="">All sources</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.title}
              </option>
            ))}
          </select>
        </label>
        <span className="muted" data-testid="map-count">
          {concepts - hidden.size} of {concepts} concepts
        </span>
      </section>

      <div className="map-body">
        <div className="map-area">
          {concepts === 0 && (
            <p className="map-empty">
              Nothing on the map yet. <Link to="/sources">Add a source</Link> to begin.
            </p>
          )}
          <Suspense fallback={<div className="map-frame space" aria-busy="true" />}>
            <Renderer
              document={map}
              hiddenIds={hidden}
              selectedNodeId={nodeId}
              selectedEdgeId={edgeId}
              lines={lines}
              onSelectNode={selectNode}
              onSelectEdge={setEdgeId}
            />
          </Suspense>
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

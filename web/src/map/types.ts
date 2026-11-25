import type { ComponentType } from 'react'

import type { Schemas } from '../api/client'

export type MapDocument = Schemas['MapDocument']
export type Landmark = Schemas['Landmark']
export type Region = Schemas['Region']
export type NodeDetail = Schemas['NodeDetail']
export type Relationship = Schemas['RelationshipOut']
export type Evidence = Schemas['EvidenceOut']
export type EvidenceItem = Schemas['EvidenceItem']

/** A relationship line drawn from the selected landmark to one of its neighbours. */
export interface RelationshipLine {
  edgeId: string
  type: string
  otherId: string
  isHypothesis: boolean
}

export interface MapRendererProps {
  document: MapDocument
  /** Landmarks hidden by the filters. Hidden landmarks are not drawn. */
  hiddenIds: ReadonlySet<string>
  selectedNodeId: string | null
  selectedEdgeId: string | null
  /** Relationships of the selected landmark; empty until one is selected. */
  lines: RelationshipLine[]
  onSelectNode: (id: string | null) => void
  onSelectEdge: (edgeId: string) => void
}

/**
 * The map is drawn only through this interface. The SVG implementation can be
 * swapped for a canvas one when measured frame rates drop, with no change to callers.
 */
export type MapRenderer = ComponentType<MapRendererProps>

import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import { prominentIds } from './appearance'
import EvidencePanel from './EvidencePanel'
import ForceGraphRenderer from './ForceGraphRenderer'
import { hiddenLandmarks } from './MapPage'
import { AREA_COLOURS, glowSize, recentIds, seeded, shapeOf, toSpace } from './space'
import type { Evidence, EvidenceItem, Landmark, MapDocument, NodeDetail } from './types'

// jsdom has no WebGL: the graph library is replaced by a stub that records its props.
const graphProps = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))
vi.mock('react-force-graph-3d', () => ({
  default: (props: Record<string, unknown>) => {
    graphProps.current = props
    return <div data-testid="force-graph" />
  },
}))

beforeEach(() => {
  graphProps.current = null
  // Pretend the browser can create a WebGL context.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as never)
})

function landmark(id: string, more: Partial<Landmark> = {}): Landmark {
  return {
    id,
    type: 'feeling',
    kind: null,
    name: id,
    x: 300,
    y: 300,
    life_area: 'work',
    status: 'stated',
    status_line: 'Stated: you have said this yourself.',
    is_hypothesis: false,
    noticed_by: ['self'],
    evidence_count: 1,
    first_seen_at: '2026-01-12T10:00:00Z',
    last_seen_at: '2026-01-12T10:00:00Z',
    is_self: false,
    source_ids: ['s1'],
    ...more,
  }
}

const HYPOTHESIS: Pick<Landmark, 'status' | 'status_line' | 'is_hypothesis' | 'noticed_by'> = {
  status: 'hypothesis',
  status_line: 'Hypothesis: nobody has said this directly.',
  is_hypothesis: true,
  noticed_by: ['ai'],
}

const MAP: MapDocument = {
  layout_version: 1,
  size: 1000,
  regions: [
    { key: 'work', name: 'Work', anchor: [300, 700], polygon: [[200, 600], [400, 600], [400, 800], [200, 800]] },
    { key: 'self', name: 'Self', anchor: [500, 500], polygon: [[450, 450], [550, 450], [550, 550], [450, 550]] },
  ],
  landmarks: [
    landmark('dread', { evidence_count: 4 }),
    landmark('shame', { ...HYPOTHESIS, x: 340, y: 380 }),
    landmark('found out', { type: 'belief', status: 'observed', noticed_by: ['therapist'], x: 380, y: 300 }),
  ],
}

function renderMap(props: Partial<Parameters<typeof ForceGraphRenderer>[0]> = {}) {
  const onSelectNode = vi.fn()
  const onSelectEdge = vi.fn()
  render(
    <ForceGraphRenderer
      document={MAP}
      hiddenIds={new Set()}
      selectedNodeId={null}
      selectedEdgeId={null}
      lines={[]}
      onSelectNode={onSelectNode}
      onSelectEdge={onSelectEdge}
      {...props}
    />,
  )
  return { onSelectNode, onSelectEdge }
}

interface StubNode {
  id: string
  x: number
  y: number
  z: number
  fx?: number
  home: { x: number; y: number; z: number }
  well: { x: number; y: number }
}

function nodesAreFlat() {
  return graphData().nodes.every((node) => node.z === 0 && node.home.z === 0)
}

function graphData() {
  return graphProps.current?.graphData as {
    nodes: StubNode[]
    links: { source: string; target: string; edgeId: string; isHypothesis: boolean }[]
  }
}

test('every landmark is a node seeded from its map position, in a dark space', () => {
  renderMap()
  expect(screen.getByTestId('force-graph')).toBeInTheDocument()
  expect(graphProps.current?.backgroundColor).toBe('#04050c')
  expect(graphProps.current?.numDimensions).toBe(2)
  expect(nodesAreFlat()).toBe(true)
  const { nodes, links } = graphData()
  expect(nodes.map((node) => node.id)).toEqual(['dread', 'shame', 'found out'])
  const dread = nodes[0]
  // Map position (300, 300) becomes (-200, 200): centred, with y pointing up.
  expect([dread?.x, dread?.y]).toEqual([-200, 200])
  expect(dread?.home.x).toBe(-200)
  // Its gravity well is the anchor of its life area, Work at (300, 700).
  expect(dread?.well).toEqual({ x: -200, y: -200 })
  expect(links).toEqual([])
})

test('landmarks can be selected from the keyboard-accessible list and from the graph', () => {
  const { onSelectNode } = renderMap()
  const list = screen.getByRole('group', { name: 'Map of your atlas' })
  expect(within(list).getByRole('button', { name: 'Feeling: shame (hypothesis)' })).toBeInTheDocument()
  expect(within(list).getByRole('button', { name: 'Belief: found out (observed)' })).toBeInTheDocument()
  fireEvent.click(within(list).getByRole('button', { name: 'Feeling: dread (stated)' }))
  const click = graphProps.current?.onNodeClick as (node: { id: string }) => void
  click({ id: 'shame' })
  const background = graphProps.current?.onBackgroundClick as () => void
  background()
  expect(onSelectNode.mock.calls).toEqual([['dread'], ['shame'], [null]])
})

test('relationships are hidden until a landmark is selected', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true }]
  renderMap({ lines })
  expect(graphData().links).toEqual([])
  expect(screen.queryByRole('button', { name: /Relationship/ })).toBeNull()
})

test('a selected landmark reveals links to its neighbours, and they can be picked', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true }]
  const { onSelectEdge } = renderMap({ lines, selectedNodeId: 'dread' })
  expect(graphData().links).toEqual([{ source: 'dread', target: 'shame', edgeId: 'e1', isHypothesis: true }])
  // Links are plain graded lines: no particles travel along them.
  expect(graphProps.current?.linkDirectionalParticles).toBeUndefined()
  expect(typeof graphProps.current?.linkThreeObject).toBe('function')
  fireEvent.click(screen.getByRole('button', { name: 'Relationship: dread led to shame' }))
  const pick = graphProps.current?.onLinkClick as (link: { edgeId: string }) => void
  pick({ edgeId: 'e1' })
  expect(onSelectEdge.mock.calls).toEqual([['e1'], ['e1']])
  expect(screen.getByRole('button', { name: 'Feeling: dread (stated)' })).toHaveAttribute('aria-pressed', 'true')
})

test('hidden landmarks are not drawn', () => {
  renderMap({ hiddenIds: new Set(['shame']) })
  expect(graphData().nodes.map((node) => node.id)).toEqual(['dread', 'found out'])
  expect(screen.queryByRole('button', { name: /shame/ })).toBeNull()
})

test('the owner is fixed at the centre', () => {
  const me = landmark('me', { type: 'person', is_self: true, life_area: 'self', x: 500, y: 500 })
  renderMap({ document: { ...MAP, landmarks: [me, ...MAP.landmarks] } })
  const node = graphData().nodes.find((item) => item.id === 'me')
  expect([node?.fx, node?.x, node?.y, node?.z]).toEqual([0, 0, 0, 0])
})

test('without WebGL the landmarks are still listed and selectable', () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  const { onSelectNode } = renderMap()
  expect(screen.queryByTestId('force-graph')).toBeNull()
  expect(screen.getByText(/WebGL is unavailable/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Feeling: dread (stated)' }))
  expect(onSelectNode).toHaveBeenCalledWith('dread')
})

test('filters by type, by who noticed it and by source', () => {
  const marks = [
    landmark('a'),
    landmark('b', { type: 'belief', noticed_by: ['therapist'], source_ids: ['s2'] }),
    landmark('c', { noticed_by: ['ai'], source_ids: ['s1', 's2'] }),
    landmark('me', { type: 'person', is_self: true, noticed_by: [], source_ids: [] }),
  ]
  const none = { types: new Set<never>(), noticed: new Set<never>(), sourceId: '' }
  expect(hiddenLandmarks(marks, none)).toEqual(new Set())
  expect(hiddenLandmarks(marks, { ...none, types: new Set(['belief']) })).toEqual(new Set(['a', 'c']))
  expect(hiddenLandmarks(marks, { ...none, noticed: new Set(['ai', 'therapist']) })).toEqual(new Set(['a']))
  expect(hiddenLandmarks(marks, { ...none, sourceId: 's2' })).toEqual(new Set(['a']))
})

test('size grows with evidence, colour follows life area, and recent landmarks are found', () => {
  expect(glowSize(9)).toBeGreaterThan(glowSize(1))
  expect(glowSize(10_000)).toBeLessThanOrEqual(90)
  expect(new Set(Object.values(AREA_COLOURS)).size).toBe(6)
  // People are stars; every other type is a round point.
  expect(shapeOf('person')).toBe('star')
  expect(shapeOf('feeling')).toBe('point')
  expect(shapeOf('group')).toBe('point')
  expect(toSpace(500, 500)).toEqual({ x: 0, y: 0 })
  expect(seeded('abc')).toBe(seeded('abc'))
  expect(seeded('abc')).not.toBe(seeded('abd'))
  const marks = [
    landmark('new', { last_seen_at: '2026-03-01T00:00:00Z' }),
    landmark('near', { last_seen_at: '2026-02-10T00:00:00Z' }),
    landmark('old', { last_seen_at: '2025-06-01T00:00:00Z' }),
    landmark('never', { last_seen_at: null }),
  ]
  expect(recentIds(marks)).toEqual(new Set(['new', 'near']))
  expect(prominentIds(MAP.landmarks, 1)).toEqual(new Set(['dread']))
})

function quote(id: string, more: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id,
    stance: 'supports',
    basis: 'explicit',
    statement_id: `st-${id}`,
    quote: 'I felt dread for days before it',
    text: 'I felt dread for days before my review.',
    kind: 'feeling',
    speaker_role: 'self',
    said_at: '2026-01-12T10:00:30Z',
    start_ms: 95_000,
    end_ms: 99_000,
    segment_id: 'seg1',
    source_id: 'src1',
    source_title: 'Invented session',
    source_occurred_at: '2026-01-12T10:00:00Z',
    audio_media_id: 'media1',
    ...more,
  }
}

function renderPanel(evidence: Evidence, node: NodeDetail | null) {
  const handlers = { onSelectNode: vi.fn(), onSelectEdge: vi.fn(), onClose: vi.fn() }
  render(
    <MemoryRouter>
      <EvidencePanel node={node} evidence={evidence} {...handlers} />
    </MemoryRouter>,
  )
  return handlers
}

const NODE: NodeDetail = {
  id: 'shame',
  type: 'feeling',
  kind: null,
  name: 'shame',
  description: null,
  attributes: {},
  aliases: [],
  life_area: 'family',
  evidence_count: 2,
  first_seen_at: '2026-01-12T10:00:00Z',
  last_seen_at: '2026-01-19T10:00:00Z',
  is_self: false,
  ...HYPOTHESIS,
  noticed_by: ['ai'],
  relationships: [
    {
      edge_id: 'e1',
      type: 'OCCURRED_IN',
      direction: 'out',
      status: 'hypothesis',
      status_line: 'Hypothesis: nobody has said this directly.',
      is_hypothesis: true,
      evidence_count: 1,
      valid_from: null,
      valid_to: null,
      other: { id: 'dinner', type: 'event', kind: null, name: 'The dinner', status: 'stated', status_line: 's', is_hypothesis: false },
    },
  ],
}

test('a hypothesis always shows its label in the panel', () => {
  renderPanel(
    { target_kind: 'node', target_id: 'shame', title: 'shame', ...HYPOTHESIS, items: [quote('1', { basis: 'implied' })] },
    NODE,
  )
  expect(screen.getByTestId('status-line')).toHaveTextContent('Hypothesis: nobody has said this directly.')
  expect(screen.getByTestId('status-line')).toHaveClass('hypothesis')
  expect(screen.getByText('Inferred')).toBeInTheDocument()
  expect(screen.getByText('Implied')).toBeInTheDocument()
  const related = screen.getByRole('region', { name: 'Related' })
  expect(within(related).getByText('Showed up during')).toBeInTheDocument()
  expect(within(related).getByText('Hypothesis')).toBeInTheDocument()
})

test('every quote shows who said it, when, where, its stance and its basis', () => {
  const handlers = renderPanel(
    {
      target_kind: 'node',
      target_id: 'belief',
      title: 'I am not good enough',
      status: 'stated',
      status_line: 'Stated: you have said this yourself.',
      is_hypothesis: false,
      items: [
        quote('1'),
        quote('2', { stance: 'contradicts', quote: 'I am good at my job', speaker_role: 'therapist', audio_media_id: null }),
      ],
    },
    { ...NODE, status: 'stated', is_hypothesis: false, status_line: 'Stated: you have said this yourself.' },
  )
  const [first, second, ...rest] = within(screen.getByRole('region', { name: 'Quotes' })).getAllByRole('listitem')
  if (!first || !second) throw new Error('expected two quotes')
  expect(rest).toHaveLength(0)
  expect(first).toHaveTextContent('“I felt dread for days before it”')
  expect(first).toHaveTextContent('Me')
  expect(first).toHaveTextContent('Invented session')
  expect(first).toHaveTextContent('Supports')
  expect(first).toHaveTextContent('Said directly')
  expect(within(first).getByRole('button', { name: 'Play from 1:35' })).toBeInTheDocument()
  expect(within(first).getByRole('link', { name: 'Open in transcript' })).toHaveAttribute(
    'href',
    '/sources/src1#segment-seg1',
  )
  expect(second).toHaveTextContent('Contradicts')
  expect(second).toHaveTextContent('My therapist')
  // A written source has no recording to play.
  expect(within(second).queryByRole('button', { name: /Play/ })).toBeNull()
  expect(screen.getByTestId('status-line')).not.toHaveClass('hypothesis')

  fireEvent.click(screen.getByRole('button', { name: 'The dinner' }))
  fireEvent.click(screen.getByRole('button', { name: 'why?' }))
  expect(handlers.onSelectNode).toHaveBeenCalledWith('dinner')
  expect(handlers.onSelectEdge).toHaveBeenCalledWith('e1')
})

test('a relationship can be shown on its own', () => {
  renderPanel(
    { target_kind: 'edge', target_id: 'e1', title: 'dread led to going quiet', ...HYPOTHESIS, items: [] },
    null,
  )
  expect(screen.getByRole('heading', { name: 'dread led to going quiet' })).toBeInTheDocument()
  expect(screen.getByText('Relationship')).toBeInTheDocument()
  expect(screen.getByTestId('status-line')).toHaveClass('hypothesis')
})

test('quotes are listed newest first, with the type and life area above the name', () => {
  renderPanel(
    {
      target_kind: 'node',
      target_id: 'shame',
      title: 'shame',
      ...HYPOTHESIS,
      items: [
        quote('old', { quote: 'the first time', said_at: '2026-01-12T10:00:30Z', source_title: 'Session one' }),
        quote('new', { quote: 'the latest time', said_at: '2026-01-19T10:05:00Z', source_title: 'Session two', source_id: 'src2' }),
      ],
    },
    NODE,
  )
  const items = within(screen.getByRole('region', { name: 'Quotes' })).getAllByRole('listitem')
  expect(items.map((item) => item.querySelector('blockquote')?.textContent)).toEqual([
    '“the latest time”',
    '“the first time”',
  ])
  expect(screen.getByText(/Feeling · Family/)).toBeInTheDocument()
  expect(screen.getByText('2 support · 0 contradict · newest first')).toBeInTheDocument()
  expect(screen.getByText('across 2 sources')).toBeInTheDocument()
})

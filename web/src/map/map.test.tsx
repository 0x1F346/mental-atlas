import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { NODE_TYPES } from '../api/generated/vocabulary'
import { typeIcon } from '../icons'
import {
  AREA_COLOURS,
  fadeOf,
  labelColour,
  landmarkDiameter,
  orbOpacity,
  prominentIds,
  typeColour,
} from './appearance'
import EvidencePanel from './EvidencePanel'
import MapPage, { hiddenLandmarks } from './MapPage'
import SvgMapRenderer, { labelLimit } from './SvgMapRenderer'
import { insetPolygon, strand } from './tissue'
import type { Evidence, EvidenceItem, Landmark, MapDocument, NodeDetail } from './types'

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

function renderMap(props: Partial<Parameters<typeof SvgMapRenderer>[0]> = {}) {
  const onSelectNode = vi.fn()
  const onSelectEdge = vi.fn()
  render(
    <SvgMapRenderer
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

function mapGroup() {
  return screen.getByRole('group', { name: 'Map of your atlas' })
}

test('every landmark is a button at its saved position, outlined by its status', () => {
  renderMap()
  const map = mapGroup()
  const dread = within(map).getByRole('button', { name: 'Feeling: dread (stated)' })
  const shame = within(map).getByRole('button', { name: 'Feeling: shame (hypothesis)' })
  const belief = within(map).getByRole('button', { name: 'Belief: found out (observed)' })
  expect([dread.dataset.x, dread.dataset.y]).toEqual(['300', '300'])
  expect([shame.dataset.x, shame.dataset.y]).toEqual(['340', '380'])
  expect(dread).toHaveClass('status-stated')
  expect(shame).toHaveClass('status-hypothesis')
  expect(belief).toHaveClass('status-observed')
  // The hypothesis label is on the landmark itself, not only in the panel.
  expect(shame).toHaveAttribute('title', 'Feeling: shame (hypothesis)')
})

test('regions are drawn from the stored polygons, with their names', () => {
  renderMap()
  const map = mapGroup()
  expect(within(map).getByText('Work')).toBeInTheDocument()
  expect(within(map).getByText('Self')).toBeInTheDocument()
  const work = map.querySelector('.region[data-area="work"]')
  expect(work?.querySelector('.memb')?.getAttribute('d')).toMatch(/^M/)
  expect(work?.querySelector('.memb2')?.getAttribute('d')).toMatch(/^M/)
})

test('landmarks are selected by click, and a click on the background clears the selection', () => {
  const { onSelectNode } = renderMap({ selectedNodeId: 'dread' })
  fireEvent.click(screen.getByRole('button', { name: /shame/ }))
  fireEvent.click(mapGroup())
  fireEvent.keyDown(mapGroup(), { key: 'Escape' })
  expect(onSelectNode.mock.calls).toEqual([['shame'], [null], [null]])
  expect(screen.getByRole('button', { name: /dread/ })).toHaveAttribute('aria-pressed', 'true')
})

test('relationships are hidden until a landmark is selected', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true }]
  renderMap({ lines })
  expect(screen.queryByRole('button', { name: /Relationship/ })).toBeNull()
})

test('a selected landmark shows its relationships, labelled, and they can be picked', () => {
  const lines = [
    { edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true },
    { edgeId: 'e2', type: 'CONFLICTS_WITH', otherId: 'found out', isHypothesis: false },
  ]
  const { onSelectEdge } = renderMap({ lines, selectedNodeId: 'dread' })
  const hypothesis = screen.getByRole('button', { name: 'Relationship: dread led to shame (hypothesis)' })
  const tension = screen.getByRole('button', { name: 'Relationship: dread conflicts with found out' })
  expect(hypothesis.closest('.strand')).toHaveClass('hypothesis')
  expect(tension.closest('.strand')).toHaveClass('tension')
  // A hypothesis strand carries a visible label on the map.
  expect(within(mapGroup()).getByText('Hypothesis')).toHaveClass('strand-tag')
  fireEvent.click(hypothesis)
  fireEvent.keyDown(tension, { key: 'Enter' })
  expect(onSelectEdge.mock.calls).toEqual([['e1'], ['e2']])
})

test('hidden landmarks are not drawn, and neither are relationships to them', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: false }]
  renderMap({ hiddenIds: new Set(['shame']), lines, selectedNodeId: 'dread' })
  expect(screen.queryByRole('button', { name: /shame/ })).toBeNull()
  expect(screen.getAllByRole('button', { name: /^(Feeling|Belief):/ })).toHaveLength(2)
})

test('only prominent landmarks carry a label until one is selected or the map is zoomed in', () => {
  const many = Array.from({ length: 15 }, (_, index) =>
    landmark(`m${index}`, { evidence_count: 20 - index, x: 100 + index * 50 }),
  )
  renderMap({ document: { ...MAP, landmarks: many }, selectedNodeId: 'm14' })
  const labelled = mapGroup().querySelectorAll('.lm-label')
  // Twelve prominent landmarks, plus the selected one.
  expect(labelled).toHaveLength(13)
  expect(screen.getByRole('button', { name: /m14/ }).querySelector('.lm-label')).not.toBeNull()
  expect(screen.getByRole('button', { name: /m13/ }).querySelector('.lm-label')).toBeNull()
})

test('the map page lists filters, with the rarer types under More', async () => {
  const marks = [
    landmark('a'),
    landmark('b', { type: 'person' }),
    landmark('c', { type: 'need' }),
    landmark('d', { type: 'blind_spot' }),
  ]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const body = request.url.endsWith('/map') ? { ...MAP, landmarks: marks } : []
      return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
    }),
  )
  render(
    <MemoryRouter>
      <MapPage />
    </MemoryRouter>,
  )
  const types = await screen.findByRole('group', { name: 'Filter by type' })
  expect(within(types).getAllByRole('button').map((button) => button.textContent)).toEqual([
    'Person',
    'Feeling',
    'More types',
  ])
  fireEvent.click(within(types).getByRole('button', { name: 'More types' }))
  const more = screen.getByRole('group', { name: 'More types' })
  fireEvent.click(within(more).getByRole('button', { name: 'Need' }))
  expect(within(types).getByRole('button', { name: 'More types · 1' })).toBeInTheDocument()
  expect(screen.getByTestId('map-count')).toHaveTextContent('1 of 4 concepts')
  const noticed = screen.getByRole('group', { name: 'Filter by who noticed it' })
  expect(within(noticed).getByRole('button', { name: 'Anyone' })).toHaveAttribute('aria-pressed', 'true')
  vi.unstubAllGlobals()
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

test('size grows with evidence, opacity fades with age, and every type has its own icon', () => {
  expect(landmarkDiameter(1)).toBe(28)
  expect(landmarkDiameter(4)).toBeGreaterThan(landmarkDiameter(2))
  expect(landmarkDiameter(10_000)).toBe(66)
  const newest = Date.parse('2026-03-01T00:00:00Z')
  expect(fadeOf('2026-03-01T00:00:00Z', newest)).toBe(0)
  expect(fadeOf('2026-01-30T00:00:00Z', newest)).toBeCloseTo(0.25)
  expect(fadeOf('2025-01-01T00:00:00Z', newest)).toBe(1)
  expect(fadeOf(null, newest)).toBe(1)
  expect([orbOpacity(0), orbOpacity(1)]).toEqual([1, 0.4])
  // The label fades no further than #93AEAB, so it stays readable.
  expect([labelColour(0), labelColour(1)]).toEqual(['#f2f7f3', '#93aeab'])
  expect(new Set(NODE_TYPES.map(typeIcon)).size).toBe(NODE_TYPES.length)
  expect(typeColour('person')).toBe('#FF9B85')
  expect(typeColour('need')).toBe(typeColour('blind_spot'))
  expect(new Set(Object.values(AREA_COLOURS)).size).toBe(6)
  expect(prominentIds(MAP.landmarks, 1)).toEqual(new Set(['dread']))
})

test('membranes are drawn inside the stored outline, and strands are seeded by edge', () => {
  const square: [number, number][] = [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
  ]
  const inset = insetPolygon(square, 1)
  for (const [x, y] of inset) {
    expect(x).toBeGreaterThan(0)
    expect(x).toBeLessThan(10)
    expect(y).toBeGreaterThan(0)
    expect(y).toBeLessThan(10)
  }
  // The same in the other winding.
  for (const [x] of insetPolygon([...square].reverse(), 1)) expect(x).toBeGreaterThan(0)
  expect(strand([0, 0], [100, 0], 'e1')).toEqual(strand([0, 0], [100, 0], 'e1'))
  expect(strand([0, 0], [100, 0], 'e1').path).not.toEqual(strand([0, 0], [100, 0], 'e2').path)
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

test('more labels appear as the map is zoomed in', () => {
  expect([labelLimit(0.6), labelLimit(1), labelLimit(1.4), labelLimit(1.42), labelLimit(2), labelLimit(4)]).toEqual([
    12, 12, 12, 24, 48, 192,
  ])
})

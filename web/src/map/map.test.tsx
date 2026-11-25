import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { landmarkOpacity, landmarkRadius, prominentIds } from './appearance'
import EvidencePanel from './EvidencePanel'
import { hiddenLandmarks } from './MapPage'
import SvgMapRenderer from './SvgMapRenderer'
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

test('draws regions and one landmark per concept, with status in the outline', () => {
  renderMap()
  expect(screen.getByText('Work')).toBeInTheDocument()
  const dread = screen.getByRole('button', { name: 'Feeling: dread (stated)' })
  const shame = screen.getByRole('button', { name: 'Feeling: shame (hypothesis)' })
  const belief = screen.getByRole('button', { name: 'Belief: found out (observed)' })
  expect(shame.querySelector('.landmark-disc.status-hypothesis')).not.toBeNull()
  expect(dread.querySelector('.landmark-ring')).toBeNull()
  expect(belief.querySelector('.landmark-ring')).not.toBeNull()
})

test('selecting a landmark reports it, by mouse and by keyboard', () => {
  const { onSelectNode } = renderMap()
  fireEvent.click(screen.getByRole('button', { name: /dread/ }))
  fireEvent.keyDown(screen.getByRole('button', { name: /shame/ }), { key: 'Enter' })
  expect(onSelectNode.mock.calls).toEqual([['dread'], ['shame']])
})

test('relationships are hidden until a landmark is selected', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true }]
  renderMap({ lines })
  expect(screen.queryByRole('button', { name: /Relationship/ })).toBeNull()
})

test('a selected landmark shows lines to its neighbours, which can be picked', () => {
  const lines = [{ edgeId: 'e1', type: 'LED_TO', otherId: 'shame', isHypothesis: true }]
  const { onSelectEdge } = renderMap({ lines, selectedNodeId: 'dread' })
  const line = screen.getByRole('button', { name: 'Relationship: dread led to shame' })
  expect(line.parentElement?.querySelector('.relationship.hypothesis')).not.toBeNull()
  fireEvent.click(line)
  expect(onSelectEdge).toHaveBeenCalledWith('e1')
})

test('zoomed out, only the largest landmarks are drawn in full', () => {
  const many = Array.from({ length: 20 }, (_, i) => landmark(`n${i}`, { evidence_count: i + 1, x: 100 + i * 40 }))
  render(
    <SvgMapRenderer
      document={{ ...MAP, landmarks: many }}
      hiddenIds={new Set()}
      selectedNodeId="n0"
      selectedEdgeId={null}
      lines={[]}
      onSelectNode={vi.fn()}
      onSelectEdge={vi.fn()}
    />,
  )
  const detail = (name: string) => screen.getByRole('button', { name: `Feeling: ${name} (stated)` }).dataset.detail
  expect(detail('n19')).toBe('full')
  expect(detail('n3')).toBe('dot')
  // The selected landmark is always drawn in full.
  expect(detail('n0')).toBe('full')
})

test('hidden landmarks are not drawn', () => {
  renderMap({ hiddenIds: new Set(['shame']) })
  expect(screen.queryByRole('button', { name: /shame/ })).toBeNull()
  expect(screen.getByRole('button', { name: /dread/ })).toBeInTheDocument()
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

test('size grows with evidence and landmarks fade with age', () => {
  expect(landmarkRadius(9)).toBeGreaterThan(landmarkRadius(1))
  expect(landmarkRadius(10_000)).toBeLessThanOrEqual(26)
  const now = new Date('2026-06-01T00:00:00Z')
  expect(landmarkOpacity('2026-05-25T00:00:00Z', now)).toBe(1)
  expect(landmarkOpacity('2025-12-01T00:00:00Z', now)).toBeLessThan(0.9)
  expect(landmarkOpacity('2020-01-01T00:00:00Z', now)).toBeCloseTo(0.45)
  expect(landmarkOpacity(null, now)).toBe(1)
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
  expect(within(first).getByRole('link', { name: 'In the transcript' })).toHaveAttribute(
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

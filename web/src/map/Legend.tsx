import type { NodeType } from '../api/generated/vocabulary'
import { TYPE_ICONS, TYPE_LABELS } from './appearance'

const STATUSES = [
  { status: 'stated', label: 'Stated: you said it' },
  { status: 'observed', label: 'Observed: your therapist said it' },
  { status: 'hypothesis', label: 'Hypothesis: nobody has said it directly' },
] as const

export default function Legend({ types }: { types: NodeType[] }) {
  return (
    <details className="legend">
      <summary>Legend</summary>
      <ul>
        {STATUSES.map(({ status, label }) => (
          <li key={status}>
            <svg viewBox="-16 -16 32 32" width="26" height="26" aria-hidden="true">
              {status === 'observed' && <circle r={13.5} className="landmark-ring" />}
              <circle r={10} className={`landmark-disc status-${status}`} />
            </svg>
            {label}
          </li>
        ))}
      </ul>
      <ul>
        {types.map((type) => (
          <li key={type}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path d={TYPE_ICONS[type]} className="landmark-icon" />
            </svg>
            {TYPE_LABELS[type]}
          </li>
        ))}
      </ul>
      <p className="muted">Bigger means more evidence. Fainter means not seen for a while.</p>
    </details>
  )
}

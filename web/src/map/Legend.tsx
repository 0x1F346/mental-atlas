import { LIFE_AREA_LABELS, LIFE_AREAS } from '../api/generated/vocabulary'
import { AREA_COLOURS } from './space'

export default function Legend() {
  return (
    <details className="legend">
      <summary>Legend</summary>
      <ul>
        {LIFE_AREAS.map((area) => (
          <li key={area}>
            <span className="swatch" style={{ background: AREA_COLOURS[area] }} aria-hidden="true" />
            {LIFE_AREA_LABELS[area]}
          </li>
        ))}
      </ul>
      <p>Bigger means more evidence. A pulse means seen recently.</p>
      <p>A dim flicker is a hypothesis: nobody has said it directly.</p>
      <p>Hearts are people. Select a point to see what it is linked to.</p>
      <p>Drag to move, scroll to zoom.</p>
    </details>
  )
}

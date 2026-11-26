/** What the landmark outlines, sizes and fading mean. */
export default function Legend() {
  return (
    <div className="legend glass" role="note" aria-label="Legend">
      <span className="legend-item">
        <span className="legend-orb status-stated" aria-hidden="true" />
        Stated
      </span>
      <span className="legend-item">
        <span className="legend-orb status-observed" aria-hidden="true" />
        Observed
      </span>
      <span className="legend-item">
        <span className="legend-orb status-hypothesis" aria-hidden="true" />
        Hypothesis
      </span>
      <span className="legend-rule" aria-hidden="true" />
      <span className="legend-item">
        <span className="legend-pair" aria-hidden="true">
          <span className="legend-dot small" />
          <span className="legend-dot" />
        </span>
        Grows with evidence
      </span>
      <span className="legend-item">
        <span className="legend-pair" aria-hidden="true">
          <span className="legend-dot" />
          <span className="legend-dot faded" />
        </span>
        Fades when unmentioned
      </span>
    </div>
  )
}

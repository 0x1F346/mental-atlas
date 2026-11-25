"""The extraction scorecard: what was stored, measured against a fixture's expected output."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.models import Evidence, LifeArea, Node, NodeAlias, Run, Segment, Statement
from atlas.domain.generated.vocabulary import NodeType, RecordState
from atlas.domain.rules import DIAGNOSIS_KIND
from atlas.domain.text import normalize_name
from atlas.evaluation.fixtures import Fixture
from atlas.pipeline.quotes import overlap_ratio

# Starting targets proposed in the plan. Revise after the first real session.
TARGETS: dict[str, tuple[str, float]] = {
    "quote_validity": (">=", 1.0),
    "speaker_attribution": (">=", 1.0),
    "statement_recall": (">=", 0.85),
    "concept_recall": (">=", 0.80),
    "concept_precision": (">=", 0.90),
    "type_accuracy": (">=", 0.90),
    "status_accuracy": (">=", 0.90),
    "duplicate_rate": ("<=", 0.05),
    "life_area_agreement": (">=", 0.80),
    "diagnosis_rule_violations": ("<=", 0.0),
}
LABELS = {
    "quote_validity": "Quote validity",
    "speaker_attribution": "Speaker attribution",
    "statement_recall": "Statement recall",
    "concept_recall": "Concept recall",
    "concept_precision": "Concept precision",
    "type_accuracy": "Type accuracy",
    "status_accuracy": "Status accuracy",
    "duplicate_rate": "Duplicate rate",
    "life_area_agreement": "Life-area agreement",
    "diagnosis_rule_violations": "Diagnosis rule violations",
    "silent_segment_statements": "Statements from small talk",
    "dropped_items": "Dropped items",
}


@dataclass
class Tally:
    """Counts for one fixture, or summed over several."""

    counts: dict[str, list[float]] = field(default_factory=dict)  # name -> [hits, total]
    values: dict[str, float] = field(default_factory=dict)  # plain counts

    def add(self, name: str, hits: float, total: float) -> None:
        pair = self.counts.setdefault(name, [0.0, 0.0])
        pair[0] += hits
        pair[1] += total

    def count(self, name: str, value: float) -> None:
        self.values[name] = self.values.get(name, 0.0) + value

    def merge(self, other: "Tally") -> None:
        for name, (hits, total) in other.counts.items():
            self.add(name, hits, total)
        for name, value in other.values.items():
            self.count(name, value)

    def results(self) -> dict[str, float | None]:
        out: dict[str, float | None] = {
            name: (hits / total if total else None) for name, (hits, total) in self.counts.items()
        }
        out.update(self.values)
        return out


@dataclass
class StoredNode:
    id: uuid.UUID
    type: str
    kind: str | None
    names: set[str]
    status: str
    home: str | None


def _matches(names: set[str], fragments: list[str]) -> bool:
    return any(fragment in name for fragment in fragments for name in names)


def score_fixture(
    session: Session,
    source_id: uuid.UUID,
    fixture: Fixture,
    judged_supported: dict[uuid.UUID, bool] | None = None,
) -> Tally:
    """Score what one source put into the atlas. `judged_supported` carries a judge's
    verdict per stored concept; without it, precision counts a stored concept as
    supported when it matches an expected one.
    """
    tally = Tally()
    expected = fixture.expected
    segments = {
        s.id: s for s in session.scalars(select(Segment).where(Segment.source_id == source_id))
    }
    statements = session.scalars(select(Statement).where(Statement.source_id == source_id)).all()

    # Quote validity and speaker attribution.
    valid = sum(1 for s in statements if s.quote and s.quote in segments[s.segment_id].text)
    correct_role = sum(
        1 for s in statements if s.speaker_role == fixture.turns[segments[s.segment_id].idx][0]
    )
    tally.add("quote_validity", valid, len(statements))
    tally.add("speaker_attribution", correct_role, len(statements))

    # Statement recall: an expected statement is found by a stored one with an overlapping quote.
    found = 0
    for want in expected["statements"]:
        text = fixture.turns[want["segment"]][1]
        start = text.index(want["quote"])
        span = (start, start + len(want["quote"]))
        for stored in statements:
            segment = segments[stored.segment_id]
            local = (
                stored.quote_start_char - segment.start_char,
                stored.quote_end_char - segment.start_char,
            )
            if segment.idx == want["segment"] and overlap_ratio(span, local) > 0.5:
                found += 1
                break
    tally.add("statement_recall", found, len(expected["statements"]))
    silent = set(expected.get("silent_segments", []))
    tally.count(
        "silent_segment_statements",
        sum(1 for s in statements if segments[s.segment_id].idx in silent),
    )

    # Concepts this source gave evidence to.
    statement_ids = [s.id for s in statements]
    node_ids = set(
        session.scalars(
            select(Evidence.target_id).where(
                Evidence.target_kind == "node", Evidence.statement_id.in_(statement_ids)
            )
        )
    )
    areas = {area.id: area.key for area in session.scalars(select(LifeArea))}
    aliases: dict[uuid.UUID, set[str]] = {}
    for node_id, alias in session.execute(
        select(NodeAlias.node_id, NodeAlias.normalized_alias).where(NodeAlias.node_id.in_(node_ids))
    ):
        aliases.setdefault(node_id, set()).add(alias)
    stored_nodes = [
        StoredNode(
            n.id,
            n.type,
            n.kind,
            aliases.get(n.id, set()) | {n.normalized_name},
            n.status,
            areas.get(n.life_area_id) if n.life_area_id else None,
        )
        for n in session.scalars(
            select(Node).where(
                Node.id.in_(node_ids),
                Node.state == RecordState.ACTIVE.value,
                Node.type != NodeType.UNSORTED.value,
                Node.run_id.is_not(None),
            )
        )
    ]

    recalled = typed = right_status = right_home = with_home = duplicates = 0
    matched_ids: set[uuid.UUID] = set()
    for want in expected["concepts"]:
        fragments = [f.casefold() for f in want["match"]] + [normalize_name(want["name"])]
        by_name = [n for n in stored_nodes if _matches(n.names, fragments)]
        same_type = [n for n in by_name if n.type == want["type"]]
        if by_name:
            typed += 1 if same_type else 0
        tally.add("type_accuracy", 1 if same_type else 0, 1 if by_name else 0)
        if not same_type:
            continue
        recalled += 1
        duplicates += len(same_type) - 1
        matched_ids |= {n.id for n in same_type}
        best = same_type[0]
        right_status += best.status == want["status"]
        if not want.get("skip_home"):
            with_home += 1
            right_home += best.home == want["home"]
    tally.add("concept_recall", recalled, len(expected["concepts"]))
    tally.add("status_accuracy", right_status, recalled)
    tally.add("life_area_agreement", right_home, with_home)
    tally.add("duplicate_rate", duplicates, len(stored_nodes))
    if judged_supported is None:
        supported = sum(1 for n in stored_nodes if n.id in matched_ids)
    else:
        supported = sum(1 for n in stored_nodes if judged_supported.get(n.id, False))
    tally.add("concept_precision", supported, len(stored_nodes))

    # A diagnosis the fixture forbids, or any diagnosis it does not expect, is a violation.
    allowed = [
        [f.casefold() for f in c["match"]]
        for c in expected["concepts"]
        if c["type"] == NodeType.TRAIT.value and c.get("kind") == DIAGNOSIS_KIND
    ]
    violations = sum(
        1
        for n in stored_nodes
        if n.type == NodeType.TRAIT.value
        and n.kind == DIAGNOSIS_KIND
        and not any(_matches(n.names, fragments) for fragments in allowed)
    )
    tally.count("diagnosis_rule_violations", violations)

    dropped = 0
    for run in session.scalars(
        select(Run).where(Run.source_id == source_id, Run.status == "succeeded")
    ):
        counts: dict[str, Any] = (run.raw_output or {}).get("counts", {})
        dropped += sum(int(v) for v in counts.get("dropped", {}).values())
    tally.count("dropped_items", dropped)
    return tally


def render(results: dict[str, float | None]) -> tuple[str, bool]:
    """A plain-text scorecard and whether every target is met."""
    lines = [f"{'Measure':<28}{'Result':>10}{'Target':>12}  Met"]
    all_met = True
    for name, label in LABELS.items():
        value = results.get(name)
        target = TARGETS.get(name)
        if value is None:
            shown = "n/a"
        elif name in ("diagnosis_rule_violations", "silent_segment_statements", "dropped_items"):
            shown = str(int(value))
        else:
            shown = f"{value * 100:.1f}%"
        if target is None:
            lines.append(f"{label:<28}{shown:>10}{'reported':>12}")
            continue
        op, bound = target
        met = value is not None and (value >= bound if op == ">=" else value <= bound)
        all_met = all_met and met
        wanted = "0" if name == "diagnosis_rule_violations" else f"{op} {bound * 100:.0f}%"
        lines.append(f"{label:<28}{shown:>10}{wanted:>12}  {'yes' if met else 'NO'}")
    return "\n".join(lines), all_met

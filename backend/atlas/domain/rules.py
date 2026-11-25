"""Commit-time rules: computed fields, the hypothesis rule and the diagnosis rule.

These are pure functions over evidence. `noticed_by` and `status` are never set by
hand: they are derived here from who said what, and how directly. The rules are
enforced in code at commit time, not only in prompts.
"""

import datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from atlas.domain.generated.vocabulary import (
    EvidenceBasis,
    EvidenceStance,
    LifeArea,
    NodeType,
    NoticedBy,
    SpeakerRole,
    Status,
)

HOME_AREA_THRESHOLD = 0.5
DIAGNOSIS_KIND = "diagnosis"

STATUS_LINES: dict[Status, str] = {
    Status.STATED: "Stated: you have said this yourself.",
    Status.OBSERVED: "Observed: your therapist has said this; you have not.",
    Status.HYPOTHESIS: "Hypothesis: nobody has said this directly.",
}


class RuleViolation(Exception):
    """A commit-time rule was broken. `code` is safe to log; no content is attached."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EvidenceFact:
    """What the rules need to know about one evidence link and its statement."""

    speaker_role: SpeakerRole
    basis: EvidenceBasis
    stance: EvidenceStance
    said_at: datetime.datetime
    confidence: float | None = None
    life_area_weights: Mapping[str, float] | None = None


@dataclass(frozen=True)
class Computed:
    noticed_by: list[str]
    status: Status
    evidence_count: int
    first_seen_at: datetime.datetime | None
    last_seen_at: datetime.datetime | None
    confidence: float | None
    life_area_weights: dict[str, float]
    home_area: LifeArea


def noticed_by(facts: Sequence[EvidenceFact]) -> list[NoticedBy]:
    """An explicit supporting link from the owner adds self, from the therapist adds
    therapist; any implied link adds ai. A contradicting link names nothing: the
    speaker denied the thing rather than noticing it.
    """
    found: set[NoticedBy] = set()
    for fact in facts:
        if fact.basis is EvidenceBasis.IMPLIED:
            found.add(NoticedBy.AI)
        elif fact.stance is EvidenceStance.SUPPORTS:
            if fact.speaker_role is SpeakerRole.SELF:
                found.add(NoticedBy.SELF)
            elif fact.speaker_role is SpeakerRole.THERAPIST:
                found.add(NoticedBy.THERAPIST)
    return [member for member in NoticedBy if member in found]


def status_from(noticed: Sequence[NoticedBy]) -> Status:
    """Stated when the owner has named it, observed when only the therapist has,
    hypothesis when nobody has.
    """
    if NoticedBy.SELF in noticed:
        return Status.STATED
    if NoticedBy.THERAPIST in noticed:
        return Status.OBSERVED
    return Status.HYPOTHESIS


def status_line(status: Status) -> str:
    """The plain-language label shown wherever an item appears (the hypothesis rule)."""
    return STATUS_LINES[status]


def combine_life_area_weights(facts: Sequence[EvidenceFact]) -> dict[str, float]:
    """Average the per-mention weights and normalise them to sum to 1."""
    totals = dict.fromkeys((area.value for area in LifeArea), 0.0)
    for fact in facts:
        if not fact.life_area_weights:
            continue
        mention_total = sum(max(v, 0.0) for k, v in fact.life_area_weights.items() if k in totals)
        if mention_total <= 0:
            continue
        for key, value in fact.life_area_weights.items():
            if key in totals:
                totals[key] += max(value, 0.0) / mention_total
    total = sum(totals.values())
    if total <= 0:
        return {}
    return {key: round(value / total, 4) for key, value in totals.items() if value > 0}


def home_life_area(weights: Mapping[str, float]) -> LifeArea:
    """The area with the highest weight; Self when no area holds at least half."""
    if not weights:
        return LifeArea.SELF
    key, weight = max(weights.items(), key=lambda item: (item[1], item[0]))
    return LifeArea(key) if weight >= HOME_AREA_THRESHOLD else LifeArea.SELF


def compute(facts: Sequence[EvidenceFact]) -> Computed:
    """Derive every computed field of a node or relationship from its evidence."""
    noticed = noticed_by(facts)
    times = [fact.said_at for fact in facts]
    confidences = [
        fact.confidence
        for fact in facts
        if fact.confidence is not None and fact.stance is EvidenceStance.SUPPORTS
    ]
    weights = combine_life_area_weights(facts)
    return Computed(
        noticed_by=[member.value for member in noticed],
        status=status_from(noticed),
        evidence_count=len(facts),
        first_seen_at=min(times) if times else None,
        last_seen_at=max(times) if times else None,
        confidence=max(confidences) if confidences else None,
        life_area_weights=weights,
        home_area=home_life_area(weights),
    )


def diagnosis_allowed(facts: Sequence[EvidenceFact]) -> bool:
    """A diagnosis needs an explicit supporting link from the owner or the therapist."""
    return any(
        fact.basis is EvidenceBasis.EXPLICIT
        and fact.stance is EvidenceStance.SUPPORTS
        and fact.speaker_role in (SpeakerRole.SELF, SpeakerRole.THERAPIST)
        for fact in facts
    )


def is_diagnosis(node_type: str, kind: str | None) -> bool:
    return node_type == NodeType.TRAIT.value and kind == DIAGNOSIS_KIND


def enforce_diagnosis_rule(node_type: str, kind: str | None, facts: Sequence[EvidenceFact]) -> None:
    """Reject a diagnosis that nobody stated. The AI never creates a diagnosis."""
    if is_diagnosis(node_type, kind) and not diagnosis_allowed(facts):
        raise RuleViolation("diagnosis_without_explicit_statement")

import datetime

import pytest

from atlas.domain import rules
from atlas.domain.generated.vocabulary import (
    EvidenceBasis,
    EvidenceStance,
    LifeArea,
    NoticedBy,
    SpeakerRole,
    Status,
)
from atlas.domain.rules import EvidenceFact

T1 = datetime.datetime(2026, 1, 5, 10, tzinfo=datetime.UTC)
T2 = datetime.datetime(2026, 2, 9, 10, tzinfo=datetime.UTC)


def fact(
    role: SpeakerRole = SpeakerRole.SELF,
    basis: EvidenceBasis = EvidenceBasis.EXPLICIT,
    stance: EvidenceStance = EvidenceStance.SUPPORTS,
    said_at: datetime.datetime = T1,
    confidence: float | None = 0.8,
    weights: dict[str, float] | None = None,
) -> EvidenceFact:
    return EvidenceFact(role, basis, stance, said_at, confidence, weights)


def test_owner_naming_it_makes_it_stated() -> None:
    result = rules.compute([fact()])
    assert result.noticed_by == ["self"]
    assert result.status is Status.STATED


def test_only_the_therapist_naming_it_makes_it_observed() -> None:
    result = rules.compute([fact(role=SpeakerRole.THERAPIST)])
    assert result.noticed_by == ["therapist"]
    assert result.status is Status.OBSERVED


def test_an_inference_from_the_owners_words_is_a_hypothesis() -> None:
    result = rules.compute([fact(basis=EvidenceBasis.IMPLIED)])
    assert result.noticed_by == ["ai"]
    assert result.status is Status.HYPOTHESIS


def test_inference_plus_therapist_stays_observed_and_records_both() -> None:
    result = rules.compute(
        [fact(basis=EvidenceBasis.IMPLIED), fact(role=SpeakerRole.THERAPIST, said_at=T2)]
    )
    assert result.noticed_by == ["therapist", "ai"]
    assert result.status is Status.OBSERVED


def test_owner_statement_outranks_therapist() -> None:
    result = rules.compute([fact(role=SpeakerRole.THERAPIST), fact()])
    assert result.status is Status.STATED


def test_a_third_party_naming_it_is_not_the_owner_noticing() -> None:
    result = rules.compute([fact(role=SpeakerRole.OTHER)])
    assert result.noticed_by == []
    assert result.status is Status.HYPOTHESIS


def test_a_denial_by_the_owner_does_not_make_it_stated() -> None:
    result = rules.compute(
        [
            fact(role=SpeakerRole.THERAPIST),
            fact(role=SpeakerRole.SELF, stance=EvidenceStance.CONTRADICTS, said_at=T2),
        ]
    )
    assert result.noticed_by == ["therapist"]
    assert result.status is Status.OBSERVED
    assert result.evidence_count == 2


def test_no_evidence_is_a_hypothesis_with_empty_fields() -> None:
    result = rules.compute([])
    assert result.status is Status.HYPOTHESIS
    assert result.evidence_count == 0
    assert result.first_seen_at is None and result.last_seen_at is None
    assert result.home_area is LifeArea.SELF


def test_counts_and_dates_come_from_the_evidence() -> None:
    result = rules.compute([fact(said_at=T2, confidence=0.6), fact(said_at=T1, confidence=0.9)])
    assert result.evidence_count == 2
    assert result.first_seen_at == T1
    assert result.last_seen_at == T2
    assert result.confidence == 0.9


def test_home_area_is_the_heaviest_when_it_holds_half() -> None:
    result = rules.compute(
        [fact(weights={"work": 0.7, "self": 0.3}), fact(weights={"work": 0.5, "family": 0.5})]
    )
    assert result.life_area_weights == {"work": 0.6, "self": 0.15, "family": 0.25}
    assert result.home_area is LifeArea.WORK


def test_home_area_falls_back_to_self_when_no_area_holds_half() -> None:
    weights = {"work": 0.4, "family": 0.3, "love": 0.3}
    assert rules.home_life_area(weights) is LifeArea.SELF
    assert rules.home_life_area({"love": 0.5, "family": 0.5}) is LifeArea.LOVE


def test_unknown_areas_and_negative_weights_are_ignored() -> None:
    assert rules.combine_life_area_weights([fact(weights={"moon": 5, "work": -1})]) == {}


def test_every_status_has_a_plain_language_line_and_hypotheses_say_so() -> None:
    for status in Status:
        assert rules.status_line(status)
    assert rules.status_line(Status.HYPOTHESIS).startswith("Hypothesis")


@pytest.mark.parametrize("role", [SpeakerRole.SELF, SpeakerRole.THERAPIST])
def test_a_stated_diagnosis_is_allowed(role: SpeakerRole) -> None:
    rules.enforce_diagnosis_rule("trait", "diagnosis", [fact(role=role)])


@pytest.mark.parametrize(
    "facts",
    [
        [],
        [fact(basis=EvidenceBasis.IMPLIED)],
        [fact(role=SpeakerRole.THERAPIST, basis=EvidenceBasis.IMPLIED)],
        [fact(role=SpeakerRole.OTHER)],
        [fact(stance=EvidenceStance.CONTRADICTS)],
    ],
)
def test_an_inferred_diagnosis_is_rejected(facts: list[EvidenceFact]) -> None:
    with pytest.raises(rules.RuleViolation) as error:
        rules.enforce_diagnosis_rule("trait", "diagnosis", facts)
    assert error.value.code == "diagnosis_without_explicit_statement"


def test_the_diagnosis_rule_ignores_other_traits() -> None:
    rules.enforce_diagnosis_rule("trait", "strength", [])
    rules.enforce_diagnosis_rule("feeling", None, [])


def test_noticed_by_order_is_stable() -> None:
    noticed = rules.noticed_by(
        [fact(basis=EvidenceBasis.IMPLIED), fact(role=SpeakerRole.THERAPIST), fact()]
    )
    assert noticed == [NoticedBy.SELF, NoticedBy.THERAPIST, NoticedBy.AI]

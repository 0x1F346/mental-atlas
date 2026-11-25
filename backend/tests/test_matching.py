from atlas.pipeline.matching import Candidate, Proposed, events_agree, resolve
from atlas.pipeline.quotes import locate_quote, overlap_ratio
from atlas.pipeline.windows import Window, windows


def candidate(
    id_: str, type_: str, name: str, vector: list[float] | None = None, **attrs: object
) -> Candidate:
    return Candidate(id_, type_, name, None, dict(attrs), {name.casefold()}, vector)


def proposed(type_: str, name: str, **attrs: object) -> Proposed:
    return Proposed(type_, name, "", dict(attrs), [name])


def never(*_: object) -> tuple[bool, str]:
    raise AssertionError("the model should not be asked")


def run(p: Proposed, cs: list[Candidate], v: list[float] | None, decide=never):  # type: ignore[no-untyped-def]
    return resolve(p, cs, v, accept=0.9, review=0.75, decide=decide)


def test_exact_name_or_alias_within_the_type_is_accepted() -> None:
    dread = candidate("1", "feeling", "Dread")
    assert run(proposed("feeling", " dread. "), [dread], None).matched_node_id == "1"
    assert run(proposed("belief", "dread"), [dread], None).decision == "new"
    mum = Candidate("2", "person", "my mum", None, {}, {"my mum", "ruth"})
    assert run(proposed("person", "Ruth"), [mum], None).decision == "exact_name"


def test_similarity_thresholds() -> None:
    existing = candidate("1", "feeling", "apprehension", [1.0, 0.0])
    high = run(proposed("feeling", "unease"), [existing], [0.95, 0.3122])
    assert (high.decision, high.matched_node_id) == ("similar", "1")
    low = run(proposed("feeling", "joy"), [existing], [0.5, 0.866])
    assert (low.decision, low.matched_node_id) == ("new", None)
    asked: list[str] = []

    def decide(p: Proposed, c: Candidate) -> tuple[bool, str]:
        asked.append(c.id)
        return p.name == "worry", "invented reason"

    same = run(proposed("feeling", "worry"), [existing], [0.8, 0.6], decide)
    different = run(proposed("feeling", "nerves"), [existing], [0.8, 0.6], decide)
    assert (same.decision, same.matched_node_id) == ("model_same", "1")
    assert (different.decision, different.matched_node_id) == ("model_different", None)
    assert asked == ["1", "1"] and same.candidate_ids == ["1"]


def test_people_never_match_on_similarity_alone() -> None:
    existing = candidate("1", "person", "my manager", [1.0, 0.0])
    calls: list[str] = []

    def decide(p: Proposed, c: Candidate) -> tuple[bool, str]:
        calls.append(p.name)
        return False, "different people"

    result = run(proposed("person", "my old manager"), [existing], [1.0, 0.0], decide)
    assert result.decision == "model_different" and calls == ["my old manager"]


def test_events_match_only_when_date_and_people_agree() -> None:
    review = candidate("1", "event", "Review with Dana", [1.0, 0.0], when="2026-01-08")
    review.involved = {"dana"}
    same_day = proposed("event", "review with dana", when="2026-01-08")
    other_day = proposed("event", "review with dana", when="2026-04-02")
    undated = proposed("event", "review with dana")
    assert run(same_day, [review], [1.0, 0.0]).matched_node_id == "1"
    assert run(other_day, [review], [1.0, 0.0]).decision == "new"
    assert run(undated, [review], [1.0, 0.0]).decision == "new"
    same_day.involved = {"sam"}
    assert not events_agree(same_day, review)


def test_system_nodes_match_by_name_only() -> None:
    me = candidate("1", "person", "Me", [1.0, 0.0])
    me.is_system = True
    assert run(proposed("person", "Someone"), [me], [1.0, 0.0]).decision == "new"
    assert run(proposed("person", "me"), [me], [1.0, 0.0]).decision == "exact_name"


def test_quotes_must_be_exact_apart_from_whitespace() -> None:
    segment = "I felt  dread\nfor days before it."
    assert locate_quote(segment, "felt dread for days") == (2, 22)
    assert segment[2:22] == "felt  dread\nfor days"
    assert locate_quote(segment, "I felt Dread") is None
    assert locate_quote(segment, "I was dreading it") is None
    assert locate_quote(segment, " ") is None
    assert overlap_ratio((0, 10), (5, 20)) == 0.5
    assert overlap_ratio((0, 10), (10, 20)) == 0.0


def test_windows_cover_every_segment_with_overlap() -> None:
    assert windows(0) == []
    assert windows(5) == [Window(0, 5)]
    assert windows(45) == [Window(0, 20), Window(18, 38), Window(36, 45)]
    assert windows(20) == [Window(0, 20)]

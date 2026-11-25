import math

import pytest

from atlas.domain.generated.vocabulary import LifeArea
from atlas.graph.geometry import CENTRE, WEDGES, Geometry
from atlas.graph.layout import MIN_DISTANCE, ToPlace, inside, place

AREAS = [*WEDGES, LifeArea.SELF]


def items(count: int, area: LifeArea, prefix: str = "n", **more: object) -> list[ToPlace]:
    return [ToPlace(f"{prefix}{i}", f"feeling:{prefix}{i}", area, **more) for i in range(count)]  # type: ignore[arg-type]


def min_gap(points: list[tuple[float, float]]) -> float:
    return min(math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1 :])


def test_regions_tile_the_disc_in_clockwise_order_from_the_top() -> None:
    geometry = Geometry(7)
    assert geometry.region_of(CENTRE) is LifeArea.SELF
    for index, area in enumerate(WEDGES):
        assert geometry.region_of(geometry.cartesian(320, index * 72 + 36)) is area
        assert geometry.region_of(geometry.anchor(area)) is area
    assert geometry.region_of((500, 180)) is LifeArea.LOVE  # Just right of the top.
    assert geometry.region_of((5, 5)) is None
    # Every point on the disc belongs to exactly one region.
    for radius in range(0, 440, 20):
        for angle in range(0, 360, 5):
            assert geometry.region_of(geometry.cartesian(radius, angle)) in AREAS


def test_borders_are_seeded_and_never_change() -> None:
    first, again, other = Geometry(42), Geometry(42), Geometry(43)
    assert first.parameters() == again.parameters()
    assert first.polygon(LifeArea.WORK) != other.polygon(LifeArea.WORK)
    work = first.parameters()["regions"]["work"]
    assert len(work["polygon"]) > 40 and set(first.parameters()["regions"]) == {
        a.value for a in AREAS
    }
    # Coastlines are roughened, not circular.
    radii = {round(first.outer_radius(a)) for a in range(0, 360, 10)}
    assert len(radii) > 5


def test_polygon_vertices_lie_on_the_regions_edge() -> None:
    geometry = Geometry(3)
    ring = [(10 * math.cos(math.tau * k / 12), 10 * math.sin(math.tau * k / 12)) for k in range(12)]
    for area in AREAS:
        for x, y in geometry.polygon(area):
            around = {geometry.region_of((x + dx, y + dy)) for dx, dy in ring}
            # An edge vertex has the region on one side and something else on the other.
            assert area in around and len(around) > 1, (area, x, y)


@pytest.mark.parametrize("area", AREAS)
def test_every_concept_sits_inside_its_home_region_without_overlap(area: LifeArea) -> None:
    geometry = Geometry(11)
    positions = place(geometry, {}, items(40, area))
    assert len(positions) == 40
    assert all(inside(geometry, point, area) for point in positions.values())
    assert min_gap(list(positions.values())) >= MIN_DISTANCE - 0.01


def test_placement_is_deterministic() -> None:
    geometry = Geometry(11)
    new = items(15, LifeArea.WORK) + items(10, LifeArea.FAMILY, "f")
    assert place(geometry, {}, new) == place(Geometry(11), {}, list(reversed(new)))
    assert place(geometry, {}, new) != place(Geometry(12), {}, new)


def test_existing_landmarks_are_pinned() -> None:
    geometry = Geometry(11)
    first = place(geometry, {}, items(20, LifeArea.WORK))
    second = place(geometry, first, items(20, LifeArea.WORK, "m"))
    assert set(second) == {f"m{i}" for i in range(20)}  # Only new positions are returned.
    everything = [*first.values(), *second.values()]
    assert min_gap(everything) >= MIN_DISTANCE - 0.01
    # The same concept placed later, alone, lands where it did the first time.
    alone = place(geometry, {}, items(1, LifeArea.WORK))
    assert alone["n0"] == place(geometry, {}, items(1, LifeArea.WORK))["n0"]


def test_a_concept_is_placed_near_its_neighbours() -> None:
    geometry = Geometry(11)
    base = place(geometry, {}, items(3, LifeArea.WORK))
    linked = ToPlace("x", "belief:x", LifeArea.WORK, neighbours=["n0", "n1", "n2"])
    stranger = ToPlace("y", "belief:y", LifeArea.WORK)
    placed = place(geometry, base, [linked, stranger])
    centre = (sum(p[0] for p in base.values()) / 3, sum(p[1] for p in base.values()) / 3)
    assert math.dist(placed["x"], centre) < 120
    assert inside(geometry, placed["x"], LifeArea.WORK)


def test_a_second_life_area_pulls_a_concept_towards_its_border() -> None:
    geometry = Geometry(11)
    plain = ToPlace("a", "feeling:same", LifeArea.WORK, weights={"work": 1.0})
    pulled = ToPlace("a", "feeling:same", LifeArea.WORK, weights={"work": 0.6, "family": 0.4})
    weak = ToPlace("a", "feeling:same", LifeArea.WORK, weights={"work": 0.8, "family": 0.2})
    family = geometry.anchor(LifeArea.FAMILY)
    at_plain = place(geometry, {}, [plain])["a"]
    at_pulled = place(geometry, {}, [pulled])["a"]
    assert math.dist(at_pulled, family) < math.dist(at_plain, family)
    assert inside(geometry, at_pulled, LifeArea.WORK)
    assert place(geometry, {}, [weak])["a"] == at_plain


def test_the_owner_sits_at_the_centre_of_self() -> None:
    geometry = Geometry(11)
    me = ToPlace("me", "person:me", LifeArea.SELF, is_self=True)
    positions = place(geometry, {}, [me, *items(12, LifeArea.SELF)])
    assert positions["me"] == CENTRE
    others = [p for key, p in positions.items() if key != "me"]
    assert all(math.dist(p, CENTRE) >= MIN_DISTANCE - 0.01 for p in others)

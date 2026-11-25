"""Placing concepts on the map.

A concept keeps its position once placed. Placement is deterministic: the same
inputs and seed give the same positions, on every device, because it runs in the
worker and the result is stored.
"""

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from atlas.domain.generated.vocabulary import LifeArea
from atlas.graph.geometry import CENTRE, Geometry, Point

MIN_DISTANCE = 36.0  # No two landmarks sit closer than this.
BORDER_PULL_WEIGHT = 0.3  # A second area holding this much weight pulls the landmark.
BORDER_PULL = 0.6  # How far towards that border, as a share of the way.
RELAX_ROUNDS = 120
MARGIN = 14.0  # Keep landmarks this far inside their region.


@dataclass(frozen=True)
class ToPlace:
    """A concept that needs a position."""

    id: str
    key: str  # Stable across reprocessing: type and normalised name.
    home: LifeArea
    weights: Mapping[str, float] = field(default_factory=dict)
    neighbours: Sequence[str] = ()
    is_self: bool = False


def _rng(seed: int, key: str) -> random.Random:
    return random.Random(f"{seed}:{key}")


def inside(geometry: Geometry, point: Point, area: LifeArea) -> bool:
    """Whether a point lies in the region with a margin all round."""
    if geometry.region_of(point) is not area:
        return False
    return all(
        geometry.region_of((point[0] + dx, point[1] + dy)) is area
        for dx, dy in ((MARGIN, 0.0), (-MARGIN, 0.0), (0.0, MARGIN), (0.0, -MARGIN))
    )


def random_point(geometry: Geometry, area: LifeArea, rng: random.Random) -> Point:
    """A seeded random point inside the region."""
    anchor = geometry.anchor(area)
    for _ in range(400):
        radius = 500.0 * math.sqrt(rng.random())
        candidate = geometry.cartesian(radius, rng.uniform(0.0, 360.0))
        if inside(geometry, candidate, area):
            return candidate
    return anchor


def pull_into(geometry: Geometry, point: Point, area: LifeArea) -> Point:
    """Move a point towards the region's centre until it is inside the region."""
    if inside(geometry, point, area):
        return point
    anchor = geometry.anchor(area)
    for step in range(1, 41):
        share = step / 40
        candidate = (
            point[0] + (anchor[0] - point[0]) * share,
            point[1] + (anchor[1] - point[1]) * share,
        )
        if inside(geometry, candidate, area):
            return candidate
    return anchor


def towards_border(geometry: Geometry, point: Point, home: LifeArea, other: LifeArea) -> Point:
    """Move a point part of the way to where its region meets `other`."""
    target = geometry.anchor(other)
    crossing = point
    for step in range(1, 201):
        share = step / 200
        candidate = (
            point[0] + (target[0] - point[0]) * share,
            point[1] + (target[1] - point[1]) * share,
        )
        if geometry.region_of(candidate) is not home:
            break
        crossing = candidate
    pulled = (
        point[0] + (crossing[0] - point[0]) * BORDER_PULL,
        point[1] + (crossing[1] - point[1]) * BORDER_PULL,
    )
    return pull_into(geometry, pulled, home)


def second_area(item: ToPlace) -> LifeArea | None:
    """Another life area holding enough of the concept's weight to pull it."""
    others = sorted(
        ((weight, key) for key, weight in item.weights.items() if key != item.home.value),
        reverse=True,
    )
    if others and others[0][0] >= BORDER_PULL_WEIGHT:
        return LifeArea(others[0][1])
    return None


def _target(
    geometry: Geometry, item: ToPlace, placed: Mapping[str, Point], rng: random.Random
) -> Point:
    if item.is_self:
        return CENTRE
    # The centre of its already-placed neighbours in the same region.
    near = [
        placed[n]
        for n in sorted(item.neighbours)
        if n in placed and geometry.region_of(placed[n]) is item.home and placed[n] != CENTRE
    ]
    if near:
        centre = (sum(p[0] for p in near) / len(near), sum(p[1] for p in near) / len(near))
        # Start beside the neighbours, not on top of them.
        angle = rng.uniform(0.0, math.tau)
        point = (
            centre[0] + MIN_DISTANCE * math.cos(angle),
            centre[1] + MIN_DISTANCE * math.sin(angle),
        )
        point = pull_into(geometry, point, item.home)
    else:
        point = random_point(geometry, item.home, rng)
    other = second_area(item)
    return towards_border(geometry, point, item.home, other) if other else point


def _free(point: Point, taken: Sequence[Point]) -> bool:
    return all(math.dist(point, other) >= MIN_DISTANCE for other in taken)


def _spiral(geometry: Geometry, start: Point, area: LifeArea, taken: Sequence[Point]) -> Point:
    """The nearest free spot to `start` inside the region, searching outwards."""
    for ring in range(1, 80):
        radius = ring * MIN_DISTANCE * 0.5
        for step in range(ring * 8):
            angle = math.tau * step / (ring * 8)
            candidate = (start[0] + radius * math.cos(angle), start[1] + radius * math.sin(angle))
            if inside(geometry, candidate, area) and _free(candidate, taken):
                return candidate
    return start


def place(
    geometry: Geometry, existing: Mapping[str, Point], new: Sequence[ToPlace]
) -> dict[str, Point]:
    """Positions for the new concepts. Existing landmarks are pinned and never move."""
    ordered = sorted(new, key=lambda item: (not item.is_self, item.key, item.id))
    placed: dict[str, Point] = dict(existing)
    positions: dict[str, Point] = {}
    for item in ordered:
        target = _target(geometry, item, placed, _rng(geometry.seed, item.key))
        positions[item.id] = target
        placed[item.id] = target

    # A short relaxation moves only the new landmarks until none overlap.
    movable = [item for item in ordered if not item.is_self]
    # Sorted, so the result does not depend on the order the positions were read in.
    pinned = sorted(existing.values())
    pinned += [positions[item.id] for item in ordered if item.is_self]
    for _ in range(RELAX_ROUNDS):
        moved = False
        for item in movable:
            here = positions[item.id]
            others = pinned + [positions[o.id] for o in movable if o.id != item.id]
            push_x = push_y = 0.0
            for other in others:
                distance = math.dist(here, other)
                if distance >= MIN_DISTANCE:
                    continue
                if distance < 1e-6:
                    angle = _rng(geometry.seed, item.key + "/nudge").uniform(0.0, math.tau)
                    dx, dy = math.cos(angle), math.sin(angle)
                else:
                    dx, dy = (here[0] - other[0]) / distance, (here[1] - other[1]) / distance
                shove = (MIN_DISTANCE - distance) / 2 + 0.5
                push_x += dx * shove
                push_y += dy * shove
            if push_x or push_y:
                positions[item.id] = pull_into(
                    geometry, (here[0] + push_x, here[1] + push_y), item.home
                )
                moved = True
        if not moved:
            break

    # Anything still crowded takes the nearest free spot in its region.
    settled = list(pinned)
    for item in movable:
        here = positions[item.id]
        if not _free(here, settled) or not inside(geometry, here, item.home):
            here = _spiral(geometry, here, item.home, settled)
        positions[item.id] = (round(here[0], 2), round(here[1], 2))
        settled.append(positions[item.id])
    for item in ordered:
        if item.is_self:
            positions[item.id] = CENTRE
    return positions

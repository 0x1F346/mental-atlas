"""The map's fixed geography.

The map is a disc inside a square of 1,000 by 1,000 units. Self is a circle at the
centre. The other five life areas are equal wedges of the ring around it, in a fixed
clockwise order from the top. Borders are roughened with seeded noise so they read
as coastlines; the seed is fixed per user, so borders never change.
"""

import math
import random
from dataclasses import dataclass
from typing import Any

from atlas.domain.generated.vocabulary import LifeArea

SIZE = 1000.0
CENTRE = (500.0, 500.0)
INNER_RADIUS = 165.0
OUTER_RADIUS = 470.0
INNER_NOISE = 9.0
OUTER_NOISE = 14.0
BORDER_NOISE_DEGREES = 3.5
HARMONICS = 4
# Clockwise from the top. Self is the centre and is not a wedge.
WEDGES: tuple[LifeArea, ...] = (
    LifeArea.LOVE,
    LifeArea.FAMILY,
    LifeArea.FRIENDSHIPS,
    LifeArea.WORK,
    LifeArea.BODY_HEALTH,
)
WEDGE_DEGREES = 360.0 / len(WEDGES)
type Point = tuple[float, float]


@dataclass(frozen=True)
class Wave:
    """A sum of sinusoids: smooth, periodic and fully determined by its terms."""

    terms: tuple[tuple[int, float, float], ...]  # (frequency, amplitude, phase)

    def at(self, t: float) -> float:
        return sum(a * math.sin(k * t + p) for k, a, p in self.terms)

    @staticmethod
    def make(rng: random.Random, amplitude: float, first: int = 2) -> "Wave":
        return Wave(
            tuple(
                (first + i * 3 + rng.randrange(3), amplitude / (i + 1.5), rng.uniform(0, math.tau))
                for i in range(HARMONICS)
            )
        )


class Geometry:
    """Region shapes for one layout. The same seed always gives the same shapes."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        rng = random.Random(seed)
        self._inner = Wave.make(rng, INNER_NOISE)
        self._outer = Wave.make(rng, OUTER_NOISE, first=3)
        self._borders = [Wave.make(rng, BORDER_NOISE_DEGREES, first=1) for _ in WEDGES]

    # Angles are in degrees clockwise from the top, in [0, 360).
    @staticmethod
    def polar(point: Point) -> tuple[float, float]:
        dx, dy = point[0] - CENTRE[0], point[1] - CENTRE[1]
        return math.hypot(dx, dy), math.degrees(math.atan2(dx, -dy)) % 360.0

    @staticmethod
    def cartesian(radius: float, angle: float) -> Point:
        radians = math.radians(angle)
        return CENTRE[0] + radius * math.sin(radians), CENTRE[1] - radius * math.cos(radians)

    def inner_radius(self, angle: float) -> float:
        return INNER_RADIUS + self._inner.at(math.radians(angle))

    def outer_radius(self, angle: float) -> float:
        return OUTER_RADIUS + self._outer.at(math.radians(angle))

    def border_angle(self, index: int, radius: float) -> float:
        """The angle of the border that starts wedge `index`, at a given radius.

        The wobble fades to nothing at the inner and outer edges so borders meet cleanly.
        """
        span = (radius - INNER_RADIUS) / (OUTER_RADIUS - INNER_RADIUS)
        fade = math.sin(math.pi * min(max(span, 0.0), 1.0))
        return index * WEDGE_DEGREES + fade * self._borders[index % len(WEDGES)].at(radius / 55.0)

    def region_of(self, point: Point) -> LifeArea | None:
        """The life area a point lies in, or None when it is off the map."""
        radius, angle = self.polar(point)
        if radius > self.outer_radius(angle):
            return None
        if radius < self.inner_radius(angle):
            return LifeArea.SELF
        for index, area in enumerate(WEDGES):
            start = self.border_angle(index, radius)
            end = self.border_angle((index + 1) % len(WEDGES), radius)
            width = (end - start) % 360.0
            if (angle - start) % 360.0 < width:
                return area
        return WEDGES[-1]

    def anchor(self, area: LifeArea) -> Point:
        """A point safely inside the region, used as its centre."""
        if area is LifeArea.SELF:
            return CENTRE
        index = WEDGES.index(area)
        return self.cartesian((INNER_RADIUS + OUTER_RADIUS) / 2, (index + 0.5) * WEDGE_DEGREES)

    def polygon(
        self, area: LifeArea, step_degrees: float = 3.0, step_radius: float = 12.0
    ) -> list[Point]:
        """The region's outline, as points in drawing order."""
        if area is LifeArea.SELF:
            return [
                self._round(self.cartesian(self.inner_radius(a), a))
                for a in _frange(0.0, 360.0, step_degrees)
            ]
        index = WEDGES.index(area)
        start, end = index * WEDGE_DEGREES, (index + 1) * WEDGE_DEGREES
        points: list[Point] = []
        # Out along the starting border, round the coast, back along the ending border,
        # then round the inner edge.
        r0, r1 = self.inner_radius(start), self.outer_radius(start)
        points += [
            self.cartesian(r, self.border_angle(index, r)) for r in _frange(r0, r1, step_radius)
        ]
        points += [
            self.cartesian(self.outer_radius(a), a) for a in _frange(start, end, step_degrees)
        ]
        r0, r1 = self.inner_radius(end), self.outer_radius(end)
        points += [
            self.cartesian(r, self.border_angle(index + 1, r))
            for r in reversed(_frange(r0, r1, step_radius))
        ]
        points += [
            self.cartesian(self.inner_radius(a), a)
            for a in reversed(_frange(start, end, step_degrees))
        ]
        return [self._round(point) for point in points]

    @staticmethod
    def _round(point: Point) -> Point:
        return round(point[0], 2), round(point[1], 2)

    def parameters(self) -> dict[str, Any]:
        """What is stored in map_layouts: the seed and the shapes computed from it."""
        return {
            "seed": self.seed,
            "size": SIZE,
            "centre": list(CENTRE),
            "regions": {
                area.value: {
                    "anchor": list(self._round(self.anchor(area))),
                    "polygon": [list(point) for point in self.polygon(area)],
                }
                for area in (*WEDGES, LifeArea.SELF)
            },
        }


def _frange(start: float, end: float, step: float) -> list[float]:
    """Evenly spaced values from start to end inclusive."""
    count = max(math.ceil((end - start) / step), 1)
    return [start + (end - start) * i / count for i in range(count + 1)]

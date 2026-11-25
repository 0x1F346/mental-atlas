"""Windows over a transcript's segments.

The whole transcript is in the prompt as cached context; each call works on a
window of about 20 segments with a 2-segment overlap. The full context helps
interpretation and the small window helps recall.
"""

from dataclasses import dataclass

WINDOW_SEGMENTS = 20
WINDOW_OVERLAP = 2


@dataclass(frozen=True)
class Window:
    start: int  # First segment index, inclusive.
    end: int  # Last segment index, exclusive.


def windows(count: int, size: int = WINDOW_SEGMENTS, overlap: int = WINDOW_OVERLAP) -> list[Window]:
    if count <= 0:
        return []
    step = size - overlap
    out: list[Window] = []
    start = 0
    while True:
        end = min(start + size, count)
        out.append(Window(start, end))
        if end >= count:
            return out
        start += step

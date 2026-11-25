"""Verbatim quote checking. A quote must be an exact excerpt of its segment."""

MIN_QUOTE_CHARS = 3


def _normalize(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to one space; map each kept character to its source index."""
    out: list[str] = []
    index: list[int] = []
    pending_space = False
    for position, char in enumerate(text):
        if char.isspace():
            pending_space = bool(out)
            continue
        if pending_space:
            out.append(" ")
            index.append(position - 1)
            pending_space = False
        out.append(char)
        index.append(position)
    return "".join(out), index


def locate_quote(segment_text: str, quote: str) -> tuple[int, int] | None:
    """Find `quote` in `segment_text`, ignoring whitespace differences only.

    Returns (start, end) offsets into segment_text, or None when the quote is not
    an exact excerpt. Case, punctuation and spelling must match.
    """
    normal_segment, index = _normalize(segment_text)
    normal_quote, _ = _normalize(quote)
    if len(normal_quote) < MIN_QUOTE_CHARS:
        return None
    found = normal_segment.find(normal_quote)
    if found < 0:
        return None
    return index[found], index[found + len(normal_quote) - 1] + 1


def overlap_ratio(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Shared length of two spans, as a share of the shorter one."""
    shared = min(a[1], b[1]) - max(a[0], b[0])
    shortest = min(a[1] - a[0], b[1] - b[0])
    return max(shared, 0) / shortest if shortest > 0 else 0.0

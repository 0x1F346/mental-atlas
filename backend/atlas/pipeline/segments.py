"""Build segments from transcribed words or from written text."""

import re
from dataclasses import dataclass, field

from atlas.providers.base import Word

MAX_SEGMENT_CHARS = 1200
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")
_PARAGRAPH = re.compile(r"[^\n]+(?:\n(?![ \t]*\n)[^\n]*)*")
_SENTENCE = re.compile(r"[^.!?]*[.!?]+[\"')\]]*\s*|[^.!?]+$")


@dataclass
class BuiltSegment:
    speaker: str
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    start_char: int = 0
    end_char: int = 0
    # [char offset in text, start_ms, end_ms] per word.
    words: list[list[int]] = field(default_factory=list)


def _segment(speaker: str, words: list[Word]) -> BuiltSegment:
    parts: list[str] = []
    timings: list[list[int]] = []
    offset = 0
    for word in words:
        timings.append([offset, word.start_ms, word.end_ms])
        parts.append(word.text)
        offset += len(word.text) + 1
    return BuiltSegment(
        speaker=speaker,
        text=" ".join(parts),
        start_ms=words[0].start_ms,
        end_ms=words[-1].end_ms,
        words=timings,
    )


def _split_long(words: list[Word], max_chars: int) -> list[list[Word]]:
    """Split one speaker's run so no piece exceeds max_chars, preferring sentence ends."""
    pieces: list[list[Word]] = []
    current: list[Word] = []
    length = 0
    last_sentence_end = -1
    for word in words:
        added = len(word.text) + (1 if current else 0)
        if current and length + added > max_chars:
            cut = last_sentence_end + 1 if last_sentence_end >= 0 else len(current)
            pieces.append(current[:cut])
            current = current[cut:]
            length = len(" ".join(w.text for w in current))
            last_sentence_end = -1
            added = len(word.text) + (1 if current else 0)
        current.append(word)
        length += added
        if _SENTENCE_END.search(word.text):
            last_sentence_end = len(current) - 1
    if current:
        pieces.append(current)
    return pieces


def build_segments(words: list[Word], max_chars: int = MAX_SEGMENT_CHARS) -> list[BuiltSegment]:
    """Consecutive words from one speaker become one segment; long ones are split."""
    runs: list[tuple[str, list[Word]]] = []
    for word in words:
        if not word.text.strip():
            continue
        if runs and runs[-1][0] == word.speaker:
            runs[-1][1].append(word)
        else:
            runs.append((word.speaker, [word]))
    segments = [
        _segment(speaker, piece) for speaker, run in runs for piece in _split_long(run, max_chars)
    ]
    return _with_positions(segments)


def _with_positions(segments: list[BuiltSegment]) -> list[BuiltSegment]:
    """Positions in the whole-source text, which is the segments joined by newlines."""
    offset = 0
    for segment in segments:
        segment.start_char = offset
        segment.end_char = offset + len(segment.text)
        offset = segment.end_char + 1
    return segments


def build_text_segments(
    text: str, speaker: str = "author", max_chars: int = MAX_SEGMENT_CHARS
) -> list[BuiltSegment]:
    """Paragraphs become segments, with character positions in place of timestamps."""
    segments: list[BuiltSegment] = []
    for paragraph in _PARAGRAPH.finditer(text):
        body = paragraph.group()
        lead = len(body) - len(body.lstrip())
        body = body.strip()
        if not body:
            continue
        start = paragraph.start() + lead
        for piece_start, piece in _split_text(body, max_chars):
            segments.append(
                BuiltSegment(
                    speaker=speaker,
                    text=piece,
                    start_char=start + piece_start,
                    end_char=start + piece_start + len(piece),
                )
            )
    return segments


def _split_text(body: str, max_chars: int) -> list[tuple[int, str]]:
    if len(body) <= max_chars:
        return [(0, body)]
    pieces: list[tuple[int, str]] = []
    piece_start, cursor = 0, 0
    for sentence in _SENTENCE.finditer(body):
        if sentence.end() - piece_start > max_chars and cursor > piece_start:
            pieces.append((piece_start, body[piece_start:cursor]))
            piece_start = cursor
        cursor = sentence.end()
    pieces.append((piece_start, body[piece_start:]))
    trimmed: list[tuple[int, str]] = []
    for start, piece in pieces:
        lead = len(piece) - len(piece.lstrip())
        if piece.strip():
            trimmed.append((start + lead, piece.strip()))
    return trimmed


def quote_time(
    words: list[list[int]] | None, quote_start: int, quote_end: int
) -> tuple[int | None, int | None]:
    """The start and end time of a quote, given offsets within its segment's text."""
    if not words:
        return None, None
    start_ms: int | None = None
    end_ms: int | None = None
    for offset, word_start, word_end in words:
        if offset <= quote_start:
            start_ms = word_start
        if offset < quote_end:
            end_ms = word_end
    return (start_ms if start_ms is not None else words[0][1]), end_ms

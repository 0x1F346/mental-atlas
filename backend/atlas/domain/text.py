"""Text helpers shared by matching, validation and seeding."""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = re.compile(r"^[\W_]+|[\W_]+$")


def collapse_whitespace(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def normalize_name(value: str) -> str:
    """The form names and aliases are compared in: case-folded and single-spaced."""
    folded = unicodedata.normalize("NFKC", value).casefold()
    return _EDGE_PUNCTUATION.sub("", collapse_whitespace(folded))

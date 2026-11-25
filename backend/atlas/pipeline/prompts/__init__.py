"""Versioned prompt files. Changing a prompt's text means adding a new version file."""

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load_prompt(name: str, version: int) -> str:
    return (_DIR / f"{name}_v{version}.md").read_text().strip()


def prompt_version(name: str, version: int) -> str:
    return f"{name}_v{version}"

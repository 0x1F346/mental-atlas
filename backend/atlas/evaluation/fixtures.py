"""Load synthetic fixtures and put them into the atlas as sources ready for extraction."""

import datetime
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from atlas.db.models import Segment, Source, Speaker
from atlas.domain.generated.vocabulary import SpeakerRole
from atlas.pipeline import queue
from atlas.pipeline.speakers import apply_roles
from atlas.pipeline.stages import STATUS_DURING, Stage
from atlas.settings import REPO_ROOT

FIXTURE_DIR = REPO_ROOT / "evals" / "fixtures" / "synthetic"
MS_PER_CHAR = 60


@dataclass(frozen=True)
class Fixture:
    name: str
    kind: str
    title: str
    occurred_at: datetime.datetime
    turns: list[tuple[str, str]]  # (speaker role, text) per segment.
    expected: dict[str, Any]


def load_fixture(name: str, directory: Path = FIXTURE_DIR) -> Fixture:
    transcript = json.loads((directory / f"{name}.transcript.json").read_text())
    expected = json.loads((directory / f"{name}.expected.json").read_text())
    if "turns" in transcript:
        turns = [(str(role), str(text)) for role, text in transcript["turns"]]
    else:
        turns = [("self", str(text)) for text in transcript["paragraphs"]]
    return Fixture(
        name=name,
        kind=transcript["kind"],
        title=transcript["title"],
        occurred_at=datetime.datetime.fromisoformat(transcript["occurred_at"]),
        turns=turns,
        expected=expected,
    )


def fixture_names(directory: Path = FIXTURE_DIR) -> list[str]:
    return sorted(
        p.name.removesuffix(".transcript.json") for p in directory.glob("*.transcript.json")
    )


def ingest(session: Session, user_id: uuid.UUID, fixture: Fixture) -> uuid.UUID:
    """Create the source with its speakers and segments, and queue statement extraction.

    The fixture supplies the transcript and the roles, so ingestion stages are skipped.
    """
    source = Source(
        user_id=user_id, kind=fixture.kind, title=fixture.title, occurred_at=fixture.occurred_at
    )
    session.add(source)
    session.flush()
    roles = list(dict.fromkeys(role for role, _ in fixture.turns))
    speakers = {
        role: Speaker(user_id=user_id, source_id=source.id, provider_label=f"speaker_{role}")
        for role in roles
    }
    session.add_all(speakers.values())
    session.flush()
    apply_roles(
        session, user_id, list(speakers.values()),
        {f"speaker_{role}": SpeakerRole(role) for role in roles}, "fixture", 1.0,
    )  # fmt: skip
    offset, clock = 0, 0
    spoken = fixture.kind != "journal"
    for idx, (role, text) in enumerate(fixture.turns):
        duration = len(text) * MS_PER_CHAR
        session.add(
            Segment(
                user_id=user_id, source_id=source.id, speaker_id=speakers[role].id, idx=idx,
                start_ms=clock if spoken else None, end_ms=clock + duration if spoken else None,
                start_char=offset, end_char=offset + len(text), text=text,
            )
        )  # fmt: skip
        offset += len(text) + 1
        clock += duration + 500
    queue.enqueue(session, user_id, source.id, Stage.STATEMENTS)
    source.status = STATUS_DURING[Stage.STATEMENTS].value
    session.flush()
    return source.id

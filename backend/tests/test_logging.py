import io
import json
import uuid
from enum import Enum
from typing import Any

from atlas.logging import REDACTED, get_logger


class Stage(Enum):
    EXTRACTING = "extracting"


def _log(**fields: Any) -> dict[str, object]:
    stream = io.StringIO()
    get_logger("test", stream).info("stage.finished", **fields)
    record = json.loads(stream.getvalue())
    assert isinstance(record, dict)
    return record


def test_ids_counts_and_codes_pass_through() -> None:
    source_id = uuid.uuid4()
    record = _log(source_id=source_id, count=3, duration_ms=12.5, stage=Stage.EXTRACTING, ok=True)
    assert record["event"] == "stage.finished"
    assert record["source_id"] == str(source_id)
    assert record["count"] == 3
    assert record["stage"] == "extracting"
    assert record["ok"] is True


def test_free_text_is_redacted() -> None:
    record = _log(quote="I always pull away when it gets close")
    assert record["quote"] == REDACTED
    assert "pull away" not in json.dumps(record)


def test_exception_message_is_never_logged() -> None:
    record = _log(error=ValueError("quote was: I feel dread"))
    assert record["error"] == "ValueError"
    assert "dread" not in json.dumps(record)


def test_containers_and_long_strings_are_redacted() -> None:
    record = _log(payload={"text": "secret"}, blob="x" * 200)
    assert record["payload"] == REDACTED
    assert record["blob"] == REDACTED


def test_event_must_be_a_code() -> None:
    stream = io.StringIO()
    get_logger("test", stream).info("the model said something private")
    assert json.loads(stream.getvalue())["event"] == REDACTED

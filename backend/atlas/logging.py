"""Structured logging that cannot carry content (design rule 9).

Log lines are JSON objects made of an event code and fields. A field value may be a
number, a boolean, a UUID, an enum member, or a short code-like string with no
whitespace. Anything else, including free text, is replaced with a redaction marker,
so transcript text, quotes and model output cannot reach the logs even by mistake.
Exceptions are reduced to their class name; their messages are never logged.
"""

import json
import re
import sys
import time
import uuid
from enum import Enum
from typing import TextIO

_CODE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,80}$")
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
REDACTED = "<redacted>"

type LogValue = str | int | float | bool | uuid.UUID | Enum | BaseException | None


def _clean(value: object) -> object:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return _clean(value.value)
    if isinstance(value, BaseException):
        return type(value).__name__
    if isinstance(value, str) and _CODE.match(value):
        return value
    return REDACTED


class Logger:
    def __init__(self, name: str, stream: TextIO | None = None) -> None:
        self._name = name
        self._stream = stream

    def _emit(self, level: str, event: str, fields: dict[str, LogValue]) -> None:
        record: dict[str, object] = {
            "ts": round(time.time(), 3),
            "level": level,
            "logger": self._name,
            "event": event if _CODE.match(event) else REDACTED,
        }
        for key, value in fields.items():
            if _KEY.match(key) and key not in record:
                record[key] = _clean(value)
        stream = self._stream or sys.stderr
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")
        stream.flush()

    def debug(self, event: str, **fields: LogValue) -> None:
        self._emit("debug", event, fields)

    def info(self, event: str, **fields: LogValue) -> None:
        self._emit("info", event, fields)

    def warning(self, event: str, **fields: LogValue) -> None:
        self._emit("warning", event, fields)

    def error(self, event: str, **fields: LogValue) -> None:
        self._emit("error", event, fields)


def get_logger(name: str, stream: TextIO | None = None) -> Logger:
    return Logger(name, stream)

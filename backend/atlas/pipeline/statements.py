"""Pass A: statement extraction.

Each statement is tied to a verbatim quote that code checks against its segment.
Nothing is written to the atlas here: the validated statements are kept on the run
and inserted by the commit stage, together with the concepts built on them.
"""

import datetime
import json
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db.ids import new_id
from atlas.db.models import Segment, Speaker
from atlas.domain.generated.vocabulary import SpeakerRole, StatementKind
from atlas.pipeline.prompts import load_prompt, prompt_version
from atlas.pipeline.quotes import locate_quote, overlap_ratio
from atlas.pipeline.runner import StageContext
from atlas.pipeline.stages import Next, Outcome, Stage, StageError
from atlas.pipeline.windows import Window, windows
from atlas.providers.base import TextBlock, ToolCall

PROMPT = "statements"
PROMPT_VERSION = 1
DUPLICATE_OVERLAP = 0.5
ROLE_LABELS = {"self": "ME", "therapist": "THERAPIST", "other": "OTHER"}


@cache
def extraction_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "domain/generated/extraction_schema.json"
    schema: dict[str, Any] = json.loads(path.read_text())
    return schema


@dataclass(frozen=True)
class SegmentView:
    """A segment as the extraction passes see it."""

    id: str
    idx: int
    handle: str
    role: str
    text: str
    start_char: int
    start_ms: int | None
    words: list[list[int]] | None


@dataclass
class StatementDraft:
    id: str
    segment_id: str
    segment_idx: int
    speaker_role: str
    quote: str
    quote_start: int  # Offsets within the segment's text.
    quote_end: int
    text: str
    kind: str
    about_time_text: str | None = None
    about_from: str | None = None
    about_to: str | None = None
    confidence: float | None = None


def load_segments(session: Session, source_id: object) -> list[SegmentView]:
    rows = session.execute(
        select(Segment, Speaker.role)
        .join(Speaker, Speaker.id == Segment.speaker_id)
        .where(Segment.source_id == source_id)
        .order_by(Segment.idx)
    ).all()
    views: list[SegmentView] = []
    for segment, role in rows:
        if role is None:
            raise StageError("speaker_roles_missing")
        views.append(
            SegmentView(
                id=str(segment.id),
                idx=segment.idx,
                handle=f"S{segment.idx}",
                role=role,
                text=segment.text,
                start_char=segment.start_char,
                start_ms=segment.start_ms,
                words=segment.words,
            )
        )
    return views


def render_transcript(segments: list[SegmentView], occurred_at: datetime.datetime) -> str:
    lines = [f"Transcript. Date of this source: {occurred_at.date().isoformat()}.", ""]
    lines += [f"[{s.handle}] {ROLE_LABELS[s.role]}: {s.text}" for s in segments]
    return "\n".join(lines)


def _iso_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return min(max(float(value), 0.0), 1.0)


def validate_statement(
    item: object, by_handle: dict[str, SegmentView], window: Window
) -> StatementDraft | str:
    """Check one model-proposed statement. Returns the draft, or an error code."""
    if not isinstance(item, dict):
        return "malformed"
    segment = by_handle.get(str(item.get("segment", "")).strip().strip("[]"))
    if segment is None or not window.start <= segment.idx < window.end:
        return "unknown_segment"
    quote, text = item.get("quote"), item.get("text")
    if not isinstance(quote, str) or not isinstance(text, str) or not text.strip():
        return "malformed"
    span = locate_quote(segment.text, quote)
    if span is None:
        return "quote_not_in_segment"
    try:
        kind = StatementKind(str(item.get("kind")))
    except ValueError:
        return "unknown_kind"
    # The speaker role is copied from the segment. The model never chooses it.
    if segment.role == SpeakerRole.THERAPIST.value:
        kind = StatementKind.OBSERVATION
    elif kind is StatementKind.OBSERVATION:
        return "observation_from_non_therapist"
    about = item.get("about_time_text")
    return StatementDraft(
        id=str(new_id()),
        segment_id=segment.id,
        segment_idx=segment.idx,
        speaker_role=segment.role,
        quote=segment.text[span[0] : span[1]],
        quote_start=span[0],
        quote_end=span[1],
        text=text.strip(),
        kind=kind.value,
        about_time_text=about.strip() if isinstance(about, str) and about.strip() else None,
        about_from=_iso_date(item.get("about_from")),
        about_to=_iso_date(item.get("about_to")),
        confidence=_confidence(item.get("confidence")),
    )


def deduplicate(drafts: list[StatementDraft]) -> list[StatementDraft]:
    """Overlapping windows can yield the same statement twice; keep the first by quote position."""
    kept: list[StatementDraft] = []
    for draft in sorted(drafts, key=lambda d: (d.segment_idx, d.quote_start, d.quote_end)):
        span = (draft.quote_start, draft.quote_end)
        duplicate = any(
            other.segment_id == draft.segment_id
            and overlap_ratio(span, (other.quote_start, other.quote_end)) > DUPLICATE_OVERLAP
            for other in kept
        )
        if not duplicate:
            kept.append(draft)
    return kept


def add_usage(total: dict[str, int], usage: dict[str, int]) -> None:
    for key, value in usage.items():
        total[key] = total.get(key, 0) + int(value)


def statements_stage(ctx: StageContext) -> Outcome:
    segments = load_segments(ctx.session, ctx.source.id)
    if not segments:
        raise StageError("no_segments")
    by_handle = {segment.handle: segment for segment in segments}
    tool = extraction_schema()["record_statements"]
    system = [
        TextBlock(load_prompt(PROMPT, PROMPT_VERSION)),
        TextBlock(render_transcript(segments, ctx.source.occurred_at), cache=True),
    ]
    usage: dict[str, int] = {}
    raw_calls: list[dict[str, Any]] = []
    drafts: list[StatementDraft] = []
    dropped: dict[str, int] = {}
    repaired = 0
    model = ctx.settings.extraction_model

    for window in windows(len(segments)):
        view = segments[window.start : window.end]
        context = {
            "segments": [{"handle": s.handle, "role": s.role, "text": s.text} for s in view],
            "source_date": ctx.source.occurred_at.date().isoformat(),
        }
        ask = (
            f"Window: segments {view[0].handle} to {view[-1].handle}. "
            "Record the statements whose quotes lie in these segments."
        )
        result = ctx.providers.extraction.call(
            ToolCall(model, system, [TextBlock(ask)], tool, purpose="statements", context=context)
        )
        add_usage(usage, result.usage)
        raw_calls.append({"window": [window.start, window.end], "output": result.data})
        model = result.model

        failed: list[dict[str, Any]] = []
        proposed = result.data.get("statements", [])
        for item in proposed if isinstance(proposed, list) else []:
            checked = validate_statement(item, by_handle, window)
            if isinstance(checked, StatementDraft):
                drafts.append(checked)
            elif checked != "malformed":
                failed.append({"statement": item, "error": checked})
            else:
                dropped[checked] = dropped.get(checked, 0) + 1

        if failed:
            # One repair attempt; whatever still fails is dropped and counted.
            repair = ctx.providers.extraction.call(
                ToolCall(
                    model,
                    system,
                    [
                        TextBlock(ask),
                        TextBlock(
                            "These statements failed validation. Return corrected versions of "
                            "those you can fix, with quotes copied exactly from the named "
                            "segment, and leave out the rest.\n" + json.dumps(failed, indent=1)
                        ),
                    ],
                    tool,
                    purpose="statements_repair",
                    context={**context, "failed": failed},
                )
            )
            add_usage(usage, repair.usage)
            raw_calls.append({"window": [window.start, window.end], "repair": repair.data})
            fixed = repair.data.get("statements", [])
            fixed_count = 0
            for item in fixed if isinstance(fixed, list) else []:
                checked = validate_statement(item, by_handle, window)
                if isinstance(checked, StatementDraft):
                    drafts.append(checked)
                    fixed_count += 1
            repaired += fixed_count
            for failure in failed[fixed_count:]:
                code = str(failure["error"])
                dropped[code] = dropped.get(code, 0) + 1

    unique = deduplicate(drafts)
    return Next(
        Stage.CONCEPTS,
        usage=usage,
        raw_output={
            "calls": raw_calls,
            "statements": [asdict(draft) for draft in unique],
            "counts": {
                "statements": len(unique),
                "duplicates": len(drafts) - len(unique),
                "repaired": repaired,
                "dropped": dropped,
            },
        },
        model=model,
        prompt_version=prompt_version(PROMPT, PROMPT_VERSION),
    )

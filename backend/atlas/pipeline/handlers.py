"""The stage handlers, in pipeline order."""

from atlas.pipeline.ingest import media_stage, segment_text_stage, transcribe_stage
from atlas.pipeline.runner import Handler, StageContext
from atlas.pipeline.speakers import speakers_stage
from atlas.pipeline.stages import Next, Outcome, Stage


def _extraction_not_built(ctx: StageContext) -> Outcome:
    """Placeholder until M3: the pipeline ends once the transcript and roles are in."""
    return Next(None)


HANDLERS: dict[Stage, Handler] = {
    Stage.MEDIA: media_stage,
    Stage.TRANSCRIBE: transcribe_stage,
    Stage.SEGMENT_TEXT: segment_text_stage,
    Stage.SPEAKERS: speakers_stage,
    Stage.STATEMENTS: _extraction_not_built,
}

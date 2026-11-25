"""The stage handlers, in pipeline order."""

from atlas.pipeline.commit import commit_stage, embed_stage
from atlas.pipeline.concepts import concepts_stage
from atlas.pipeline.ingest import media_stage, segment_text_stage, transcribe_stage
from atlas.pipeline.runner import Handler, StageContext
from atlas.pipeline.speakers import speakers_stage
from atlas.pipeline.stages import Next, Outcome, Stage
from atlas.pipeline.statements import statements_stage


def _layout_not_built(ctx: StageContext) -> Outcome:
    """Placeholder until M4: the pipeline ends once the atlas is committed and embedded."""
    return Next(None)


HANDLERS: dict[Stage, Handler] = {
    Stage.MEDIA: media_stage,
    Stage.TRANSCRIBE: transcribe_stage,
    Stage.SEGMENT_TEXT: segment_text_stage,
    Stage.SPEAKERS: speakers_stage,
    Stage.STATEMENTS: statements_stage,
    Stage.CONCEPTS: concepts_stage,
    Stage.COMMIT: commit_stage,
    Stage.EMBED: embed_stage,
    Stage.PLACE: _layout_not_built,
}

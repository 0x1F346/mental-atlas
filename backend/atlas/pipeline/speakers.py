"""Speaker roles: which voice is the owner.

Swapped roles would attribute the therapist's words to the owner across a whole
session, the most damaging single error the pipeline can make. So a low-confidence
assignment stops and asks the owner.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.db.models import Node, Segment, Speaker
from atlas.domain.generated.vocabulary import (
    VOCABULARY_VERSION,
    NodeType,
    NoticedBy,
    SourceKind,
    SourceStatus,
    SpeakerRole,
    Status,
)
from atlas.domain.text import normalize_name
from atlas.pipeline.prompts import load_prompt, prompt_version
from atlas.pipeline.runner import StageContext
from atlas.pipeline.stages import Next, Outcome, Stage, Wait
from atlas.providers.base import TextBlock, ToolCall

PROMPT_VERSION = 1
OPENING_TURNS = 6
TURN_CHARS = 300
THERAPIST_NAME = "My therapist"
THERAPIST_RELATIONSHIP = "therapist"

SPEAKER_ROLES_TOOL: dict[str, Any] = {
    "name": "assign_speaker_roles",
    "description": "Assign a role to every voice in the recording.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["assignments", "confidence"],
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label", "role"],
                    "properties": {
                        "label": {"type": "string"},
                        "role": {"type": "string", "enum": [role.value for role in SpeakerRole]},
                    },
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    },
}


def self_node(session: Session) -> Node:
    return session.scalars(
        select(Node).where(
            Node.type == NodeType.PERSON.value, Node.attributes["is_self"].as_boolean().is_(True)
        )
    ).one()


def therapist_node(session: Session, user_id: uuid.UUID) -> Node:
    """The therapist's Person node is created once and reused."""
    existing = session.scalars(
        select(Node).where(
            Node.type == NodeType.PERSON.value,
            Node.run_id.is_(None),
            Node.attributes["relationship_to_owner"].as_string() == THERAPIST_RELATIONSHIP,
        )
    ).first()
    if existing is not None:
        return existing
    me = self_node(session)
    node = Node(
        user_id=user_id,
        type=NodeType.PERSON.value,
        name=THERAPIST_NAME,
        normalized_name=normalize_name(THERAPIST_NAME),
        description="The owner's therapist.",
        attributes={"relationship_to_owner": THERAPIST_RELATIONSHIP},
        life_area_id=me.life_area_id,
        life_area_weights={"self": 1.0},
        noticed_by=[NoticedBy.SELF.value],
        status=Status.STATED.value,
        schema_version=VOCABULARY_VERSION,
    )
    session.add(node)
    session.flush()
    return node


def apply_roles(
    session: Session,
    user_id: uuid.UUID,
    speakers: list[Speaker],
    roles: dict[str, SpeakerRole],
    method: str,
    confidence: float,
) -> None:
    for speaker in speakers:
        role = roles[speaker.provider_label]
        speaker.role = role.value
        speaker.method = method
        speaker.confidence = confidence
        if role is SpeakerRole.SELF:
            speaker.person_node_id = self_node(session).id
        elif role is SpeakerRole.THERAPIST:
            speaker.person_node_id = therapist_node(session, user_id).id
        else:
            speaker.person_node_id = None
    session.flush()


def valid_assignment(labels: set[str], roles: dict[str, SpeakerRole]) -> bool:
    values = list(roles.values())
    return (
        set(roles) == labels
        and values.count(SpeakerRole.SELF) == 1
        and values.count(SpeakerRole.THERAPIST) <= 1
    )


def opening_turns(session: Session, speakers: list[Speaker]) -> dict[str, list[str]]:
    turns: dict[str, list[str]] = {}
    for speaker in speakers:
        texts = session.scalars(
            select(Segment.text)
            .where(Segment.speaker_id == speaker.id)
            .order_by(Segment.idx)
            .limit(OPENING_TURNS)
        ).all()
        turns[speaker.provider_label] = [text[:TURN_CHARS] for text in texts]
    return turns


def speakers_stage(ctx: StageContext) -> Outcome:
    speakers = list(
        ctx.session.scalars(
            select(Speaker)
            .where(Speaker.source_id == ctx.source.id)
            .order_by(Speaker.provider_label)
        )
    )
    labels = {speaker.provider_label for speaker in speakers}

    if ctx.source.kind != SourceKind.THERAPY_SESSION.value or len(speakers) == 1:
        # A voice note or journal has one speaker, the owner. If the transcriber heard
        # more than one voice anyway, the one who says the most is the owner.
        talk: dict[uuid.UUID, int] = {
            speaker_id: int(length)
            for speaker_id, length in ctx.session.execute(
                select(Segment.speaker_id, func.sum(func.length(Segment.text)))
                .where(Segment.source_id == ctx.source.id)
                .group_by(Segment.speaker_id)
            )
        }
        owner = max(speakers, key=lambda s: (talk.get(s.id, 0), s.provider_label))
        roles = {
            s.provider_label: SpeakerRole.SELF if s is owner else SpeakerRole.OTHER
            for s in speakers
        }
        apply_roles(ctx.session, ctx.user_id, speakers, roles, "single", 1.0)
        return Next(Stage.STATEMENTS)

    turns = opening_turns(ctx.session, speakers)
    listing = "\n\n".join(
        f"Voice {label}:\n" + "\n".join(f"- {text}" for text in texts)
        for label, texts in turns.items()
    )
    result = ctx.providers.extraction.call(
        ToolCall(
            model=ctx.settings.small_model,
            system=[TextBlock(load_prompt("speaker_roles", PROMPT_VERSION))],
            user=[TextBlock(listing)],
            tool=SPEAKER_ROLES_TOOL,
            max_tokens=500,
            purpose="speaker_roles",
            context={"turns": turns},
        )
    )
    roles = {}
    try:
        roles = {
            str(item["label"]): SpeakerRole(item["role"]) for item in result.data["assignments"]
        }
        confidence = float(result.data["confidence"])
    except (KeyError, TypeError, ValueError):
        confidence = 0.0
    if not valid_assignment(labels, roles):
        confidence = 0.0

    if confidence >= ctx.settings.speaker_role_confidence_threshold:
        apply_roles(ctx.session, ctx.user_id, speakers, roles, "model", confidence)
        return Next(
            Stage.STATEMENTS,
            usage=result.usage,
            model=result.model,
            prompt_version=prompt_version("speaker_roles", PROMPT_VERSION),
        )
    # Keep the model's guess as a suggestion, but ask the owner before going on.
    if valid_assignment(labels, roles):
        for speaker in speakers:
            speaker.role = roles[speaker.provider_label].value
            speaker.method = "model_unconfirmed"
            speaker.confidence = confidence
    ctx.run.usage = result.usage
    ctx.run.model = result.model
    ctx.run.prompt_version = prompt_version("speaker_roles", PROMPT_VERSION)
    return Wait(SourceStatus.NEEDS_SPEAKER_CHECK)

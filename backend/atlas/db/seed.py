"""Create a user with the rows every user starts with."""

import math
import uuid

from sqlalchemy.orm import Session

from atlas.db.ids import new_id
from atlas.db.models import LifeArea, Node, User
from atlas.db.session import set_current_user
from atlas.domain.generated.vocabulary import (
    VOCABULARY_VERSION,
    NodeType,
    NoticedBy,
    Status,
)
from atlas.domain.generated.vocabulary import (
    LifeArea as LifeAreaKey,
)
from atlas.domain.text import normalize_name

LIFE_AREA_NAMES: dict[LifeAreaKey, str] = {
    LifeAreaKey.LOVE: "Love",
    LifeAreaKey.FAMILY: "Family",
    LifeAreaKey.FRIENDSHIPS: "Friendships",
    LifeAreaKey.WORK: "Work",
    LifeAreaKey.BODY_HEALTH: "Body and health",
    LifeAreaKey.SELF: "Self",
}
SELF_NODE_NAME = "Me"
LOCKED_PASSWORD_HASH = "!"


def life_area_anchor(position: int) -> tuple[float, float]:
    """Self sits at the centre; the other five are wedge centres, clockwise from the top."""
    if position == 5:
        return 500.0, 500.0
    angle = math.radians(-90 + 36 + 72 * position)
    return round(500 + 330 * math.cos(angle), 3), round(500 + 330 * math.sin(angle), 3)


def create_user(
    session: Session, email: str, password_hash: str = LOCKED_PASSWORD_HASH
) -> uuid.UUID:
    """Insert a user, their six life areas and their own Person node.

    Scopes the session's transaction to the new user, which the policies require.
    """
    user_id = new_id()
    set_current_user(session, user_id)
    session.add(User(id=user_id, user_id=user_id, email=email.lower(), password_hash=password_hash))
    session.flush()
    self_area_id: uuid.UUID | None = None
    for position, (key, name) in enumerate(LIFE_AREA_NAMES.items()):
        x, y = life_area_anchor(position)
        area = LifeArea(
            user_id=user_id, key=key.value, name=name, position=position, anchor_x=x, anchor_y=y
        )
        session.add(area)
        session.flush()
        if key is LifeAreaKey.SELF:
            self_area_id = area.id
    session.add(
        Node(
            user_id=user_id,
            type=NodeType.PERSON.value,
            name=SELF_NODE_NAME,
            normalized_name=normalize_name(SELF_NODE_NAME),
            description="The owner of this atlas.",
            attributes={"is_self": True},
            life_area_id=self_area_id,
            life_area_weights={LifeAreaKey.SELF.value: 1.0},
            noticed_by=[NoticedBy.SELF.value],
            status=Status.STATED.value,
            schema_version=VOCABULARY_VERSION,
            is_system=True,
        )
    )
    session.flush()
    return user_id

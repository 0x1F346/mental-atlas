"""Request dependencies: the signed-in user and a database session scoped to them."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas.api.errors import ApiError
from atlas.api.security import hash_token, tokens_match
from atlas.db.session import anonymous_session, user_session
from atlas.settings import Settings, get_settings

CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    session_id: uuid.UUID
    csrf_token: str


def current_auth(request: Request, settings: SettingsDep) -> AuthContext:
    """Resolve the session cookie. Unsafe methods must also carry the CSRF token."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ApiError(401, "not_signed_in", "Sign in to continue.")
    with anonymous_session() as session:
        row = session.execute(
            text("SELECT session_id, user_id, csrf_token FROM atlas_session_lookup(:hash)"),
            {"hash": hash_token(token)},
        ).one_or_none()
    if row is None:
        raise ApiError(401, "not_signed_in", "Sign in to continue.")
    auth = AuthContext(user_id=row.user_id, session_id=row.session_id, csrf_token=row.csrf_token)
    if request.method not in SAFE_METHODS and not tokens_match(
        auth.csrf_token, request.headers.get(CSRF_HEADER)
    ):
        raise ApiError(403, "csrf_failed", "Missing or wrong CSRF token.")
    return auth


AuthDep = Annotated[AuthContext, Depends(current_auth)]


def user_db(auth: AuthDep) -> Iterator[Session]:
    """One transaction per request, scoped to the signed-in user."""
    with user_session(auth.user_id) as session:
        yield session


DbDep = Annotated[Session, Depends(user_db)]

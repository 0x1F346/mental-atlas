"""Session sign-in for the single seeded user."""

import datetime
import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select, text

from atlas.api.deps import AuthDep, DbDep, SettingsDep
from atlas.api.errors import ApiError
from atlas.api.security import RateLimiter, hash_token, new_token, verify_password
from atlas.db.models import Session as SessionRow
from atlas.db.models import User
from atlas.db.session import anonymous_session, user_session
from atlas.logging import get_logger
from atlas.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("atlas.api.auth")
login_limiter = RateLimiter(get_settings().login_rate_limit_per_minute)


class LoginRequest(BaseModel):
    email: str
    password: str


class Me(BaseModel):
    id: uuid.UUID
    email: str
    csrf_token: str


def _set_cookie(response: Response, settings: Settings, token: str, max_age: int) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, settings: SettingsDep) -> Me:
    client = request.client.host if request.client else "unknown"
    if login_limiter.blocked(client):
        log.warning("auth.login_rate_limited")
        raise ApiError(429, "too_many_attempts", "Too many sign-in attempts. Wait a minute.")
    email = body.email.strip().lower()
    with anonymous_session() as session:
        row = session.execute(
            text("SELECT user_id, password_hash FROM atlas_login_lookup(:email)"), {"email": email}
        ).one_or_none()
    if not verify_password(row.password_hash if row else None, body.password) or row is None:
        login_limiter.record_failure(client)
        log.warning("auth.login_failed")
        raise ApiError(401, "invalid_credentials", "Wrong email or password.")

    token, csrf_token = new_token(), new_token()
    ttl = datetime.timedelta(hours=settings.session_ttl_hours)
    with user_session(row.user_id) as session:
        session.execute(delete(SessionRow).where(SessionRow.expires_at < func.now()))
        session.add(
            SessionRow(
                user_id=row.user_id,
                token_hash=hash_token(token),
                csrf_token=csrf_token,
                expires_at=datetime.datetime.now(datetime.UTC) + ttl,
            )
        )
    _set_cookie(response, settings, token, int(ttl.total_seconds()))
    log.info("auth.login", user_id=row.user_id)
    return Me(id=row.user_id, email=email, csrf_token=csrf_token)


@router.post("/logout", status_code=204)
def logout(auth: AuthDep, db: DbDep, response: Response, settings: SettingsDep) -> None:
    db.execute(delete(SessionRow).where(SessionRow.id == auth.session_id))
    _set_cookie(response, settings, "", 0)


@router.get("/me")
def me(auth: AuthDep, db: DbDep) -> Me:
    email = db.execute(select(User.email).where(User.id == auth.user_id)).scalar_one()
    return Me(id=auth.user_id, email=email, csrf_token=auth.csrf_token)

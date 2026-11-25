"""Password hashing, session tokens and the login rate limit."""

import hashlib
import hmac
import secrets
import time
from collections import deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Verified when no user matches, so a missing account takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(expected: str, given: str | None) -> bool:
    return given is not None and hmac.compare_digest(expected.encode(), given.encode())


class RateLimiter:
    """Blocks a key after too many failed attempts in a minute. In memory: one API process.

    An attempt is counted before the slow password check and forgiven if it succeeds,
    so a burst of parallel guesses cannot all slip past the limit.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._attempts: dict[str, deque[float]] = {}

    def blocked(self, key: str) -> bool:
        now = time.monotonic()
        for known in [k for k, hits in self._attempts.items() if not hits or now - hits[-1] > 60]:
            del self._attempts[known]
        attempts = self._attempts.get(key)
        if attempts is None:
            return False
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        return len(attempts) >= self._limit

    def record_attempt(self, key: str) -> None:
        self._attempts.setdefault(key, deque()).append(time.monotonic())

    def forgive(self, key: str) -> None:
        attempts = self._attempts.get(key)
        if attempts:
            attempts.pop()

    def reset(self) -> None:
        self._attempts.clear()

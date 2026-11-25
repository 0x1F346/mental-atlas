"""Password hashing, session tokens and the login rate limit."""

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

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
    """Blocks a key after too many failures in a minute. Held in memory: one API process."""

    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        now = time.monotonic()
        failures = self._failures[key]
        while failures and now - failures[0] > 60:
            failures.popleft()
        return len(failures) >= self._limit

    def record_failure(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self) -> None:
        self._failures.clear()

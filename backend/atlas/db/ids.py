"""Time-ordered ids (UUID version 7, RFC 9562)."""

import os
import time
import uuid


def new_id() -> uuid.UUID:
    """Return a UUIDv7: 48 bits of Unix milliseconds, then random bits."""
    value = (time.time_ns() // 1_000_000) << 80
    value |= int.from_bytes(os.urandom(10), "big")
    value &= ~(0xF << 76)
    value |= 0x7 << 76
    value &= ~(0x3 << 62)
    value |= 0x2 << 62
    return uuid.UUID(int=value)

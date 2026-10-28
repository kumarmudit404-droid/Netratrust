"""ID and timestamp helpers.

Both are STRINGS. Integers above 2^53 raise in `rfc8785` and these values end
up inside ledger payloads, so an autoincrement integer id or an epoch-
nanosecond timestamp is a chain break waiting to happen.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def now_iso() -> str:
    """RFC 3339 UTC to whole seconds, e.g. `2026-10-28T09:14:02Z`.

    Second resolution on purpose: it is enough for an audit trail, and it keeps
    the canonical bytes stable and short.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    """A prefixed uuid4, e.g. `enc-3f1c...`. Readable in a ledger payload."""
    return f"{prefix}-{uuid.uuid4().hex}"

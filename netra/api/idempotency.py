"""Server-side dedup for at-least-once delivery (SPEC.md section 5).

We never claim exactly-once. The device retries until the server acknowledges;
the server makes a repeat harmless. The contract is:

- Same key, same request, already applied -> replay the stored response.
- Same key, same request, still in flight  -> **409**.
- Same key, DIFFERENT request              -> **422**.

The 422 check comes FIRST, before the in-flight check: a key reused with a
different payload is a client bug in either state, and reporting 409 for it
would invite a retry loop that can never succeed.

There are no merge conflicts to resolve here because screening events are
immutable append-only facts. That is an architectural property, not a dodge.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from netra.db.models import IdempotencyKey
from netra.db.util import now_iso

#: An in-flight claim older than this is treated as abandoned and reclaimed.
#: Without it, a process that dies between committing the work and marking the
#: key `done` would make that key return 409 forever.
IN_FLIGHT_TTL_SECONDS = 60


class Conflict(Exception):
    """The key is still in flight -> 409."""


class FingerprintMismatch(Exception):
    """The key was reused with a different request -> 422."""


@dataclass
class Claim:
    """The outcome of claiming a key. `replay` is set when the work is already done."""

    key: str | None
    replay: dict[str, Any] | None = None

    @property
    def is_replay(self) -> bool:
        return self.replay is not None


def fingerprint(body: Any) -> str:
    """SHA-256 over a deterministic rendering of the request body.

    Plain `json.dumps(sort_keys=True)` on purpose, not `rfc8785`: this is a
    dedup hash, not a ledger artifact, and it must not raise on a body that
    happens to contain a float.
    """
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_stale(created_at: str) -> bool:
    try:
        then = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return False
    return (datetime.now(UTC) - then).total_seconds() > IN_FLIGHT_TTL_SECONDS


def begin(engine, key: str | None, endpoint: str, body: Any) -> Claim:
    """Claim `key` for `endpoint`. Commits immediately so a concurrent duplicate sees it.

    A missing key means no dedup: the caller has opted out of at-least-once
    protection and a retry will create a second encounter. Lane B's client
    always sends one for POST /v1/encounters.
    """
    if not key:
        return Claim(None)

    fp = fingerprint(body)
    with Session(engine) as session:
        row = session.get(IdempotencyKey, key)

        if row is not None:
            if row.endpoint != endpoint or row.request_fingerprint != fp:
                raise FingerprintMismatch(
                    "Idempotency-Key was already used with a different request"
                )
            if row.status == "done":
                return Claim(key, json.loads(row.response_json or "null"))
            if not _is_stale(row.created_at):
                raise Conflict("a request with this Idempotency-Key is still in flight")
            # Stale: reclaim it by refreshing the timestamp.
            row.created_at = now_iso()
            session.add(row)
            session.commit()
            return Claim(key)

        session.add(
            IdempotencyKey(
                key=key,
                endpoint=endpoint,
                request_fingerprint=fp,
                status="in_flight",
                response_json=None,
                created_at=now_iso(),
            )
        )
        session.commit()
    return Claim(key)


def complete(engine, key: str | None, response: Any) -> None:
    """Mark the key applied and store the response for replay."""
    if not key:
        return
    with Session(engine) as session:
        row = session.get(IdempotencyKey, key)
        if row is None:
            return
        row.status = "done"
        row.response_json = json.dumps(response, sort_keys=True, default=str)
        session.add(row)
        session.commit()


def release(engine, key: str | None) -> None:
    """Drop an in-flight claim whose work failed, so a retry can proceed."""
    if not key:
        return
    with Session(engine) as session:
        row = session.get(IdempotencyKey, key)
        if row is not None and row.status == "in_flight":
            session.delete(row)
            session.commit()


def depth(session: Session, limit: int = 20) -> tuple[int, int, list[IdempotencyKey]]:
    """`(queued, synced, recent attempts)` for GET /v1/queue/depth."""
    rows = session.exec(
        select(IdempotencyKey).order_by(IdempotencyKey.created_at.desc())
    ).all()
    queued = sum(1 for r in rows if r.status == "in_flight")
    synced = sum(1 for r in rows if r.status == "done")
    return queued, synced, list(rows[:limit])

"""RFC 8785 canonicalisation, with the two failure modes that break chains.

`rfc8785` is used on BOTH write and verify (BUILD_RULES.md, rules.md section 4). The
reason is not style:

1. **Floats are banned.** `rfc8785.dumps({"n": 1.0})` emits `{"n":1}` while
   `json.dumps` emits `{"n":1.0}`. A payload written with one serialiser and
   re-hashed with the other produces a different hash and the chain breaks with
   no visible cause. `rfc8785` does not reject a float - it quietly normalises
   it - so `reject_floats` below is the guard that actually stops them.
2. **Integers above 2^53 raise.** That is why IDs and timestamps are strings
   everywhere in this codebase.

Store a confidence as a string ("0.87") or a scaled integer (870 per mille),
never as a float.
"""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785

#: JavaScript's exact-integer limit, which RFC 8785 inherits. 2**53 - 1.
MAX_SAFE_INT = 9_007_199_254_740_991


class PayloadError(ValueError):
    """A payload that `rfc8785` would accept but that we refuse to store."""


def reject_floats(payload: Any, path: str = "payload") -> None:
    """Walk a payload and raise on any float, or any int outside 2^53.

    `bool` is a subclass of `int` in Python but canonicalises to `true`/`false`,
    so it is allowed through untouched.
    """
    if isinstance(payload, float):
        raise PayloadError(
            f"{path}: floats are banned from ledger payloads "
            f"(got {payload!r}); use a string or a scaled integer"
        )
    if isinstance(payload, bool):
        return
    if isinstance(payload, int):
        if abs(payload) > MAX_SAFE_INT:
            raise PayloadError(
                f"{path}: integer {payload} exceeds 2^53-1 and raises in rfc8785; "
                f"IDs and timestamps are strings"
            )
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not isinstance(key, str):
                raise PayloadError(f"{path}: object keys must be strings, got {key!r}")
            reject_floats(value, f"{path}.{key}")
        return
    if isinstance(payload, (list, tuple)):
        for i, value in enumerate(payload):
            reject_floats(value, f"{path}[{i}]")
        return
    if payload is None or isinstance(payload, str):
        return
    raise PayloadError(f"{path}: unsupported type {type(payload).__name__}")


def canonical_bytes(payload: Any) -> bytes:
    """Validate, then canonicalise. The ONLY way a payload becomes bytes."""
    reject_floats(payload)
    return rfc8785.dumps(payload)


def payload_hash(payload: Any) -> str:
    """SPEC.md section 4: `payload_hash = SHA-256(rfc8785.dumps(payload))`."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def payload_hash_of_stored(payload_json: str) -> str:
    """Re-hash a payload read back out of the database.

    Verification re-canonicalises rather than trusting the stored text: if the
    stored bytes are not canonical, this produces a different hash and verify
    reports the entry. That is the point - a tamperer who edits `payload_json`
    by hand is caught here even if they also recompute a naive hash.
    """
    import json

    return payload_hash(json.loads(payload_json))


def entry_hash(prev_hash_hex: str, payload_hash_hex: str) -> bytes:
    """SPEC.md section 4: `entry_hash = SHA-256(prev_hash || payload_hash)`.

    Both halves are hashed as RAW BYTES, not as their hex text, so the input is
    exactly 64 bytes. This is the value Ed25519 signs - the 32-byte hash, never
    the payload.
    """
    return hashlib.sha256(
        bytes.fromhex(prev_hash_hex) + bytes.fromhex(payload_hash_hex)
    ).digest()

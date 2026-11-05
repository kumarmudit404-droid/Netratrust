"""Lane A - hash chain, Ed25519 signatures, RFC 8785 canonicalisation.

    entry_hash = SHA-256(prev_hash || SHA-256(rfc8785(payload)))

Ed25519 signs the 32-byte entry hash, never the payload. `rfc8785` is applied
on BOTH write and verify; floats are banned from payloads.
"""

from netra.ledger.canonical import (
    MAX_SAFE_INT,
    PayloadError,
    canonical_bytes,
    entry_hash,
    payload_hash,
)
from netra.ledger.chain import append, current_head
from netra.ledger.keys import SERVER_KID, KeyStore, verify_signature

# `netra.ledger.verify` and `netra.ledger.tamper` are deliberately NOT imported
# here. Both are runnable with `python -m` (BUILD_RULES.md documents
# `python -m netra.ledger.verify`), and importing a submodule in its package's
# __init__ makes runpy emit "found in sys.modules after import of package ...
# this may result in unpredictable behaviour". Import them by module path:
#     from netra.ledger.verify import verify

__all__ = [
    "MAX_SAFE_INT",
    "SERVER_KID",
    "KeyStore",
    "PayloadError",
    "append",
    "canonical_bytes",
    "current_head",
    "entry_hash",
    "payload_hash",
    "verify_signature",
]

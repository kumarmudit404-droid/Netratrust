"""SQLModel tables for NetraTrust (architecture.md section 3).

Conventions that are NOT negotiable here, because breaking them breaks the
ledger silently:

- IDs and timestamps are STRINGS. Integers above 2^53 raise in `rfc8785`, and
  these values end up inside ledger payloads.
- `ledger.seq` is the one integer that travels in a payload-adjacent position;
  it stays below 2^53 by construction (see `netra.ledger.canonical.MAX_SAFE_INT`).
- No float columns anywhere that feeds a ledger payload. Confidence scores are
  scaled integers (per mille) or strings.
- The ledger-bearing tables are append-only, enforced by SQLite triggers
  installed in `netra.db.engine`. `referrals` is deliberately NOT append-only:
  it carries the current state of the state machine, and its history lives in
  `referral_events`, which is.

`SPEC.md` section 4 names the ledger entry fields `idx, prev_hash,
payload_hash, payload_json, signer_kid, signature`; architecture.md section 3
names the column `seq` and adds `entry_hash` and `created_at`. Both are present
below: `seq` IS `idx` (the API returns it as `ledger_idx` / `idx`), and the two
hashes are stored separately because verification needs both.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel

# Ledger-bearing tables: history is added to, never rewritten. The triggers in
# netra.db.engine are installed for exactly these names.
APPEND_ONLY_TABLES = ("encounters", "referral_events", "ledger", "checkpoints")

GENESIS_PREV_HASH = "0" * 64


class Site(SQLModel, table=True):
    """A screening camp or clinic. Must pass an audit before its grades count."""

    __tablename__ = "sites"

    id: str = Field(primary_key=True)
    name: str
    region: str
    created_at: str


class Device(SQLModel, table=True):
    """A capture device. Its Ed25519 public key is how a ledger entry is checked.

    Per-device keypairs replace mTLS (SPEC.md section 8): uvicorn does not expose
    the client certificate to the application, and a certificate cannot
    authenticate an event captured while offline.
    """

    __tablename__ = "devices"

    kid: str = Field(primary_key=True)
    site_id: str = Field(foreign_key="sites.id")
    ed25519_pub: str  # raw 32-byte public key, hex
    registered_at: str


class Encounter(SQLModel, table=True):
    """One screening decision. Append-only: a screening event is an immutable fact.

    `dr_grade` is NULL when the image was rejected or the model abstained. A
    failed quality gate is "no result", never a negative DR result, so a
    rejected encounter carries no grade and no prediction set.
    """

    __tablename__ = "encounters"

    id: str = Field(primary_key=True)
    site_id: str = Field(foreign_key="sites.id")
    device_kid: str = Field(foreign_key="devices.kid")
    quality_verdict: str  # usable | borderline | reject
    cause: str | None = None  # classical reason-code; NULL when admitted
    image_sha256: str
    dr_grade: int | None = None
    abstained: bool = False
    prediction_set: str | None = None  # JSON array of ints, NULL when no result
    model_version: str
    device_seq: int  # the device owns this; the server owns ledger.seq
    created_at: str


class Referral(SQLModel, table=True):
    """Current state of a referral. NOT append-only - `state` advances.

    Every transition writes a `referral_events` row and a ledger entry, so the
    mutable column here is a cache of a history that cannot be rewritten.
    """

    __tablename__ = "referrals"

    id: str = Field(primary_key=True)
    encounter_id: str = Field(foreign_key="encounters.id")
    state: str
    created_at: str
    updated_at: str


class ReferralEvent(SQLModel, table=True):
    """One state transition. Append-only."""

    __tablename__ = "referral_events"

    id: str = Field(primary_key=True)
    referral_id: str = Field(foreign_key="referrals.id")
    from_state: str
    to_state: str
    attempt_n: int | None = None  # contact_attempted only
    channel: str | None = None  # contact_attempted only
    reason: str | None = None  # abandoned only
    created_at: str


class LedgerEntry(SQLModel, table=True):
    """One link in the hash chain. Append-only.

    payload_hash = SHA-256(rfc8785(payload))
    entry_hash   = SHA-256(prev_hash || payload_hash)   [bytes, not hex text]
    signature    = Ed25519(entry_hash)                  [the 32-byte hash, not
                                                         the payload]
    """

    __tablename__ = "ledger"

    seq: int = Field(primary_key=True)  # == SPEC.md's `idx`; stays below 2^53
    prev_hash: str
    payload_hash: str
    entry_hash: str
    payload_json: str  # canonical rfc8785 bytes, decoded utf-8. No floats.
    signer_kid: str
    signature: str
    created_at: str


class Checkpoint(SQLModel, table=True):
    """A signed head: index + hash + timestamp + signature. Append-only.

    This is the Certificate-Transparency idea without the tree. An external
    party holding yesterday's checkpoint can prove history was rewritten, which
    a bare chain cannot.
    """

    __tablename__ = "checkpoints"

    seq: int = Field(primary_key=True)
    root_hash: str  # the head entry_hash at `seq`
    signer_kid: str
    signature: str
    created_at: str


class IdempotencyKey(SQLModel, table=True):
    """Server-side dedup for at-least-once delivery (SPEC.md section 5).

    Not a ledger-bearing table, and deliberately mutable: a row moves from
    `in_flight` to `done` in place. 409 while a key is in flight, 422 when a key
    is reused with a different request fingerprint.

    This is the eighth table; architecture.md section 3 names seven. It stores
    no clinical fact - only whether a delivery has already been applied - and it
    adds no endpoint, so the frozen contract is untouched.
    """

    __tablename__ = "idempotency_keys"

    key: str = Field(primary_key=True)
    endpoint: str
    request_fingerprint: str  # SHA-256 of rfc8785(body), hex
    status: str  # in_flight | done
    response_json: str | None = None
    created_at: str

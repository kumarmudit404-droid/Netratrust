"""GET /v1/ledger/verify and GET /v1/ledger/checkpoint.

`verify` returns only `{ok, first_bad_index}` — the frozen shape. The internal
`reason` string is deliberately NOT exposed: it is a debugging aid, and the
contract says two fields.

There is no endpoint that corrupts the ledger. The tamper demo (T-17) is a CLI,
`python -m netra.ledger.tamper --seq N`, run beside the Ledger view. The nine
endpoints are frozen, and a "rewrite history" route in a deployed build would
be a liability rather than a feature.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlmodel import Session

from netra.api.deps import get_state
from netra.api.schemas import LedgerCheckpointResponse, LedgerVerifyResponse
from netra.ledger import checkpoint as checkpoint_mod
from netra.ledger.verify import verify

router = APIRouter()


@router.get("/v1/ledger/verify", response_model=LedgerVerifyResponse)
def verify_ledger(request: Request) -> LedgerVerifyResponse:
    state = get_state(request)
    with Session(state.engine) as session:
        result = verify(session, state.keystore)
    return LedgerVerifyResponse(ok=result.ok, first_bad_index=result.first_bad_index)


@router.get("/v1/ledger/checkpoint", response_model=LedgerCheckpointResponse)
def get_checkpoint(request: Request) -> LedgerCheckpointResponse:
    """The latest signed head, signing a new one if the head has moved.

    A checkpoint is created on read rather than on a timer: the demo asks for
    one and gets one that attests the chain as it stands. `checkpoints` is
    append-only, so re-reading at an unchanged head returns the stored
    checkpoint rather than re-signing it - the head has not moved, and saying
    so twice with two different timestamps would be noise.
    """
    state = get_state(request)
    with Session(state.engine) as session:
        row = checkpoint_mod.get_or_create(session, state.keystore)
        response = LedgerCheckpointResponse(
            idx=row.seq,
            head_hash=row.root_hash,
            ts=row.created_at,
            signature=row.signature,
            signer_kid=row.signer_kid,
        )
        session.commit()
    return response

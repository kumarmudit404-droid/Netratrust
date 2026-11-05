"""Application state and request dependencies.

Handlers are SYNC `def`. SQLite is blocking, and BUILD_RULES.md names async handlers
over blocking SQLite as the top time sink on this project. Nothing in this
module is a coroutine.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlmodel import Session

from netra.ledger.keys import KeyStore


@dataclass
class AppState:
    """What the lifespan context manager builds once and the routes reuse."""

    engine: object
    keystore: KeyStore


def get_state(request: Request) -> AppState:
    return request.app.state.netra


def get_engine(request: Request):
    return get_state(request).engine


def get_keystore(request: Request) -> KeyStore:
    return get_state(request).keystore


def get_session(request: Request) -> Iterator[Session]:
    """One session per request, committed by the route, closed here."""
    with Session(get_state(request).engine) as session:
        yield session


SessionDep = Depends(get_session)
StateDep = Depends(get_state)
KeyStoreDep = Depends(get_keystore)
EngineDep = Depends(get_engine)

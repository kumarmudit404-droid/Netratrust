"""The FastAPI app.

    uvicorn netra.api.main:app --reload --port 8000

Two conventions from CLAUDE.md are enforced here rather than hoped for:

- **`lifespan=` context manager**, not `@app.on_event`. The decorator is
  deprecated and mixing the two silently disables handlers.
- **Sync `def` route handlers.** SQLite is blocking; an async handler holding a
  blocking SQLite call is the top time sink on this project. `test_api.py`
  asserts that no registered handler is a coroutine function.

The nine endpoints in SPEC.md are frozen. Nothing here adds a tenth: the only
non-contract route is the OPTIONS preflight that CORSMiddleware answers.
"""

from __future__ import annotations

import inspect
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from netra.api.deps import AppState
from netra.api.routes import encounters, referrals
from netra.db.engine import init_db
from netra.ledger.keys import KeyStore

#: The Vite dev server runs on :5173 and the API on :8000, so local dev is
#: cross-origin (architecture.md section 4). Both spellings of localhost are
#: listed because a browser treats them as different origins.
DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

#: `Idempotency-Key` is a custom request header, so it is NOT in the CORS safe
#: list and a preflight fails without it named here. `X-Device-Kid` likewise.
ALLOWED_HEADERS = ("Content-Type", "Idempotency-Key", "X-Device-Kid")

#: `Idempotency-Replayed` tells a client its retry hit an already-applied
#: request. A response header is invisible to JS across origins unless exposed.
EXPOSED_HEADERS = ("Idempotency-Replayed",)


def cors_origins() -> list[str]:
    """Dev origins plus anything in `NETRA_CORS_ORIGINS` (comma-separated)."""
    extra = os.environ.get("NETRA_CORS_ORIGINS", "")
    return [*DEV_ORIGINS, *(o.strip() for o in extra.split(",") if o.strip())]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the database and the keystore once, for the process lifetime."""
    engine = init_db()
    app.state.netra = AppState(engine=engine, keystore=KeyStore())
    try:
        yield
    finally:
        app.state.netra = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="NetraTrust API",
        version="0.1.0",
        summary="Nine frozen endpoints. Images never leave the capture device.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=False,
        # PATCH is needed for /v1/referrals/{id}; OPTIONS is the preflight.
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=list(ALLOWED_HEADERS),
        expose_headers=list(EXPOSED_HEADERS),
    )
    app.include_router(encounters.router)
    app.include_router(referrals.router)
    _assert_handlers_are_sync(app)
    return app


def contract_routes(app: FastAPI) -> list:
    """Our own routes, i.e. the ones under `/v1/`.

    FastAPI's built-in `/openapi.json`, `/docs` and `/redoc` handlers are async
    and are not ours to change, so every convention check is scoped to `/v1/`.

    FastAPI 0.162.0 does NOT flatten `include_router` into `app.routes`: it
    appends one `fastapi.routing._IncludedRouter`, whose real routes hang off
    `.original_router`. Walking that is why this is a function and not a
    comprehension - a naive scan of `app.routes` finds only the docs routes and
    silently checks nothing.
    """
    found: list = []
    seen: set[int] = set()

    def walk(router) -> None:
        if id(router) in seen:
            return
        seen.add(id(router))
        for route in getattr(router, "routes", []):
            if str(getattr(route, "path", "") or "").startswith("/v1/"):
                found.append(route)
            inner = getattr(route, "original_router", None)
            if inner is not None:  # an _IncludedRouter
                walk(inner)
            elif hasattr(route, "routes"):  # a Mount, if one is ever added
                walk(route)

    walk(app.router)
    return found


def _assert_handlers_are_sync(app: FastAPI) -> None:
    """Fail at import time if one of OUR handlers is `async def`. See CLAUDE.md."""
    for route in contract_routes(app):
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None and inspect.iscoroutinefunction(endpoint):
            raise TypeError(
                f"{route.path} is an async handler; SQLite is blocking, so route "
                f"handlers must be sync def (CLAUDE.md)"
            )


app = create_app()

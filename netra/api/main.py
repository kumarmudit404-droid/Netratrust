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
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles

from netra.api.deps import AppState
from netra.api.routes import encounters, ledger, referrals, sites
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

#: Set to the compiled front end (`netra/ui/dist`) to serve it from this app at
#: `/`. UNSET BY DEFAULT: with no value the app is exactly the frozen nine, so
#: local dev keeps the Vite dev server on :5173 and nothing changes. The
#: deployed container sets it, because a single Fly machine with one SQLite
#: volume is simpler than a second service, and `BrowserRouter` needs an
#: index.html fallback that Fly's `[[statics]]` cannot give it.
UI_DIR_ENV = "NETRA_UI_DIR"


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


class SpaFiles:
    """The compiled SPA with a real index.html fallback - but never for `/v1`.

    Two things this does that a plain `StaticFiles` mount does not.

    **It falls back to index.html.** `StaticFiles(html=True)` does NOT do SPA
    fallback - for a path it cannot find it looks for `404.html` and 404s when
    that is missing too. The front end uses `BrowserRouter`, so `/sites` exists
    only in the browser: a hard refresh asks this server for a file that was
    never built, and the SPA shell is the correct answer. Relying on `html=True`
    for this would 404 a presenter who reloads mid-demo.

    **It does not answer for `/v1`.** The same fallback applied to `/v1/typo`
    would return 200 and a page of HTML, so a client with a misspelled path
    would see a success and have to read the body to discover it was wrong.
    A `/v1/{path:path}` catch-all would be the obvious fix and is not allowed:
    `tests/test_sites.py` pins the registered `/v1` routes at exactly the nine
    in SPEC.md, and that test is right. This is an ASGI wrapper, not a route,
    so the frozen contract is untouched.
    """

    def __init__(self, directory: str) -> None:
        self._root = pathlib.Path(directory).resolve()
        self._files = StaticFiles(directory=directory, html=True)

    def _is_built_file(self, path: str) -> bool:
        """Whether this path names a file that the UI build actually produced.

        A traversal attempt resolves outside the root, so it is not a built
        file and falls through to the shell rather than reaching the
        filesystem. `StaticFiles` checks this again on the way out.
        """
        try:
            candidate = (self._root / path.lstrip("/")).resolve()
        except (OSError, ValueError):
            return False
        if not candidate.is_relative_to(self._root):
            return False
        return candidate.is_file()

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if path == "/v1" or path.startswith("/v1/"):
            response = PlainTextResponse("no such endpoint", status_code=404)
            await response(scope, receive, send)
            return
        if not self._is_built_file(path):
            # A client-side route. Serve the shell and let the router read the
            # URL. 200 is correct: the page exists, just not as a file.
            scope = {**scope, "path": "/index.html"}
        await self._files(scope, receive, send)


def mount_ui(app: FastAPI) -> bool:
    """Mount the compiled front end if `NETRA_UI_DIR` names a real directory.

    Returns whether it mounted. A missing directory is not an error: the API is
    useful on its own and the UI is a separate build step, so an app that
    refused to start without `dist/` would make the API hostage to the front
    end.
    """
    directory = os.environ.get(UI_DIR_ENV, "").strip()
    if not directory or not os.path.isdir(directory):
        return False
    # Mounted LAST, after the nine, so the routes always win the match.
    app.mount("/", SpaFiles(directory), name="ui")
    return True


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
    app.include_router(ledger.router)
    app.include_router(sites.router)
    _assert_handlers_are_sync(app)
    mount_ui(app)
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

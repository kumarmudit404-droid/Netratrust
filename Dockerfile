# NetraTrust - API + compiled front end in one image (T-21).
#
# Two stages: node builds the SPA, python runs it behind the API. One container
# because one Fly machine owns the SQLite volume (see fly.toml); a second
# service would need a second machine and the volume attaches to one.
#
# WHY THIS DOES NOT `pip install -r requirements.txt`
# ---------------------------------------------------
# requirements.txt pins torch, torchvision, timm, opencv and mapie for Lane C's
# training and inference. `netra/api/main.py` imports none of them - verified by
# importing it and inspecting sys.modules - and torch alone is larger than the
# whole rest of the image. So this installs the subset the API actually imports,
# AT THE SAME PINNED VERSIONS. requirements.txt is unchanged: it is an
# agreement-only file, and the runtime subset is a selection from it, not a
# re-pin. `tests/test_deploy.py::test_runtime_pins_match_requirements` fails if
# a version here ever drifts from the one there.
#
# The model artifacts are not in this image either. When Lane C's checkpoints
# land they are loaded on the capture device, not here: SPEC.md says images are
# never uploaded, so there is nothing for a server-side model to look at.

# ----------------------------------------------------------------- UI build
# Matches the Node that builds it locally (v24).
FROM node:24-alpine AS ui

WORKDIR /ui
# package.json + lockfile first, so a source-only change reuses this layer.
COPY netra/ui/package.json netra/ui/package-lock.json ./
RUN npm ci

COPY netra/ui/ ./
# `npm run build` is `tsc -b && vite build`, so a type error fails the image
# rather than shipping a broken bundle.
RUN npm run build

# ----------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The subset netra/api imports, at requirements.txt's pins.
#   fastapi/starlette/pydantic/uvicorn - the app
#   sqlmodel/sqlalchemy               - the tables
#   cryptography                      - Ed25519
#   rfc8785                           - canonical JSON, on write AND verify
#   numpy/scipy/scikit-learn          - netra/eval/metrics.py, via the Wilson
#                                       interval that every rate goes through
RUN pip install --no-cache-dir \
      fastapi==0.162.0 \
      starlette==1.6.0 \
      pydantic==2.14.1 \
      uvicorn==0.54.0 \
      sqlmodel==0.0.48 \
      sqlalchemy==2.1.6 \
      cryptography==50.0.2 \
      rfc8785==0.1.4 \
      numpy==2.5.4 \
      scipy==1.18.1 \
      scikit-learn==1.9.1

# Only what the API needs at runtime. netra/models and notebooks are omitted on
# purpose - see the header.
COPY netra/__init__.py netra/__init__.py
COPY netra/api/ netra/api/
COPY netra/db/ netra/db/
COPY netra/ledger/ netra/ledger/
COPY netra/eval/ netra/eval/
COPY config/ config/
COPY scripts/seed_dev.py scripts/seed_dev.py

COPY --from=ui /ui/dist/ netra/ui/dist/

# Serve the compiled front end from this app. Unset, the app is exactly the
# frozen nine endpoints; set, it also answers `/` with the SPA shell.
ENV NETRA_UI_DIR=/app/netra/ui/dist

# Defaults for a plain `docker run` with no volume. fly.toml overrides both to
# point inside the mount - a database or a keystore on the container filesystem
# is gone on the next deploy, and losing the keys fails verify forever.
ENV NETRA_DB=/data/netra.db \
    NETRA_KEYS_DIR=/data/keys

EXPOSE 8000

# Sync handlers over blocking SQLite, one worker: SQLite has a single writer,
# and a second worker would serialise on it at best.
CMD ["uvicorn", "netra.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

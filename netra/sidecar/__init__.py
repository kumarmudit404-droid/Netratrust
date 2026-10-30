"""The on-device inference sidecar.

NOT part of `netra/api`. The nine `/v1` endpoints in `SPEC.md` are frozen,
none of them grades an image, and `SPEC.md` forbids uploading the image at
all - so the gate cannot be a tenth endpoint. It is a separate process that
runs on the capture device, beside the browser, and never leaves it.

See `netra/sidecar/server.py`.
"""

from netra.sidecar.server import DEFAULT_PORT, GateSidecar, build_engine, main

__all__ = ["DEFAULT_PORT", "GateSidecar", "build_engine", "main"]

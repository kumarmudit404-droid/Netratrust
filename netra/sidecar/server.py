"""The local inference sidecar: an image in, an `InferenceResult` out.

`MODEL_LANDING.md` section 5 offers two ways to make the gate real, and this is
the sidecar. The reasoning, from that file and `SPEC.md`:

* the gate runs ON-DEVICE, because `SPEC.md` forbids the image leaving it;
* the nine `/v1` endpoints are frozen and none of them grades an image, so the
  gate cannot become a tenth one;
* `netra/models/infer.py` is Python, so the browser cannot call it directly.

A separate loopback process satisfies all three. The image crosses `localhost`
and nothing else: it is read into memory, written to a temporary file because
`InferenceEngine.run` takes a path, hashed, graded, and deleted in a `finally`.
Nothing is logged but the hash.

It deliberately uses `http.server` rather than FastAPI. CLAUDE.md asks for a
stdlib solution over a dependency, and more importantly a sidecar that imported
`netra.api` would be one refactor away from becoming the tenth endpoint this
design exists to avoid. The only shared surface is `netra.models.infer`.

Run it:

    python -m netra.sidecar --port 8731

Endpoints (this is not the `/v1` API and shares no schema with it):

    GET  /health   -> {ok, model_version, gate_loaded, classifier_loaded, ...}
    POST /gate     -> the raw image bytes in the body; an InferenceResult out

The image arrives as a raw body rather than a multipart form so that parsing it
is `read(content_length)` and nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import tempfile
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from netra.models.dr import UNLOADED, DRClassifier
from netra.models.infer import InferenceEngine
from netra.models.quality import QualityGate, QuickQualFeatures

#: Not 8000 (the API) and not 5173 (Vite). Override with --port.
DEFAULT_PORT = 8731

#: Loopback only, and not configurable. A screening device must not serve
#: fundus images to its network, and `SPEC.md` is explicit that the image never
#: leaves the device. Binding 0.0.0.0 here would make that false.
HOST = "127.0.0.1"

#: A fundus image is a few megabytes. This caps a hostile or mistaken body
#: before it is read into memory.
MAX_IMAGE_BYTES = 32 * 1024 * 1024

#: Only a local page may call the sidecar. Checked against the Origin header.
ALLOWED_ORIGIN_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


def build_engine(
    svm_path: str | pathlib.Path | None = None,
    checkpoint: str | pathlib.Path | None = None,
    pretrained: bool = True,
    abstention=None,
) -> InferenceEngine:
    """An engine over whatever is actually on disk.

    Both loaders report rather than raise (MODEL_LANDING.md section 1), so this
    always builds. When nothing is loaded the engine returns `model_version:
    "unloaded"` with no grade, which is a true answer and the one the UI shows
    as "no result" - never a negative result.

    `abstention` defaults to None, and that default is deliberate. Without a
    conformalized wrapper `infer.py` abstains and says why, rather than
    reporting an argmax, which is not a grade this project publishes. Building
    one is Lane C's conformalisation step (MODEL_LANDING.md section 3), so it
    is opt-in via `conformalize_from_calib` rather than something this process
    decides on its own at startup.
    """
    return InferenceEngine(
        gate=QualityGate(
            features=QuickQualFeatures(pretrained=pretrained), svm_path=svm_path
        ),
        classifier=DRClassifier(checkpoint=checkpoint),
        abstention=abstention,
    )


def conformalize_from_calib(
    classifier: DRClassifier,
    images_dir: str | pathlib.Path,
    limit: int | None = None,
):
    """Conformalize on the CALIBRATION split, and only ever on that.

    This is the step `MODEL_LANDING.md` section 3 describes, run locally so the
    demo can show a real prediction set instead of a permanent abstention. Two
    guards make it the calibration split and not something else:

    * the split name is hard-coded to `calib`, and `dataset.collect` raises for
      `test` unless `allow_test=True`, which is never passed here;
    * it reads probabilities from the real classifier, so it cannot be run at
      all without a loaded checkpoint.

    `rules.md` and `tracker.md` both name evaluation drift as the risk no hook
    catches, and the rule is: never re-fit after seeing test results. Nothing
    here touches the test split or `config/thresholds.yaml`.

    Returns a conformalized `AbstentionWrapper`, or raises.
    """
    import numpy as np

    from netra.models.abstain import AbstentionWrapper, PrefitProbaEstimator
    from netra.models.dataset import collect
    from netra.models.preprocess import load_image

    if not classifier.available:
        raise RuntimeError(
            "cannot conformalize without a loaded DR checkpoint: "
            f"{classifier.load_error or 'no checkpoint supplied'}"
        )

    examples, report = collect("calib", pathlib.Path(images_dir), limit=limit)
    if not examples:
        raise RuntimeError(
            f"no calibration images found under {images_dir}; "
            f"retained {report.get('retained', 0)} of the split"
        )

    proba = np.vstack(
        [
            classifier.predict_proba(load_image(ex.path)).reshape(1, -1)
            for ex in examples
        ]
    )
    labels = np.array([ex.label for ex in examples])
    wrapper = AbstentionWrapper(PrefitProbaEstimator(proba.shape[1])).conformalize(
        proba, labels
    )
    return wrapper, {"n": len(examples), **report}


@dataclass(frozen=True)
class Health:
    """What the UI needs to decide whether the gate is real.

    `model_version` is the engine's own, so `unloaded` here means the same
    thing it means everywhere else in this codebase.
    """

    ok: bool
    model_version: str
    gate_loaded: bool
    classifier_loaded: bool
    conformalized: bool
    gate_error: str | None
    classifier_error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "model_version": self.model_version,
            "gate_loaded": self.gate_loaded,
            "classifier_loaded": self.classifier_loaded,
            "conformalized": self.conformalized,
            "gate_error": self.gate_error,
            "classifier_error": self.classifier_error,
        }


def health_of(engine: InferenceEngine) -> Health:
    gate_ok = bool(engine.gate.available)
    clf_ok = bool(engine.classifier.available)
    return Health(
        # `ok` means the process is up and answering, NOT that a model loaded.
        # The UI needs those apart: a reachable sidecar with no checkpoint is a
        # different thing to say than no sidecar at all.
        ok=True,
        model_version=engine.model_version,
        gate_loaded=gate_ok,
        classifier_loaded=clf_ok,
        conformalized=bool(getattr(engine.abstention, "conformalized", False)),
        gate_error=engine.gate.load_error,
        classifier_error=engine.classifier.load_error,
    )


def gate_image(engine: InferenceEngine, image: bytes, suffix: str = ".png") -> dict:
    """Run the engine over image bytes held in memory.

    `InferenceEngine.run` takes a path, so the bytes go to a temporary file
    that is removed in a `finally` - including when inference raises. The
    device keeps no copy of a fundus image it was only asked to grade.
    """
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="netra-gate-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(image)
        return engine.run(name).as_dict()
    finally:
        pathlib.Path(name).unlink(missing_ok=True)


def _origin_allowed(origin: str) -> bool:
    """True for a loopback page. An absent Origin (curl, the CLI) is fine."""
    if not origin:
        return True
    from urllib.parse import urlparse

    try:
        host = urlparse(origin).hostname
    except ValueError:
        return False
    return host in ALLOWED_ORIGIN_HOSTS


class GateSidecar(BaseHTTPRequestHandler):
    """The whole sidecar. `engine` is attached to the server, not the handler."""

    server_version = "NetraTrustGateSidecar/1.0"
    #: Set by `serve()`; one engine is shared by every request so the model is
    #: loaded once rather than per capture.
    engine: InferenceEngine

    # ------------------------------------------------------------------ util

    @property
    def _engine(self) -> InferenceEngine:
        return self.server.engine  # type: ignore[attr-defined]

    def _cors(self, origin: str) -> None:
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # A verdict is never cached: the next capture is a different image.
        self.send_header("Cache-Control", "no-store")
        self._cors(self.headers.get("Origin", ""))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        # The default logs the request line to stderr. Kept, because an
        # operator needs to see the sidecar working, but it carries only the
        # method and path - never a filename and never the bytes.
        super().log_message(fmt, *args)

    # --------------------------------------------------------------- routing

    # The do_* casing is BaseHTTPRequestHandler's dispatch contract.
    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        if not _origin_allowed(origin):
            self._json(403, {"error": "origin not allowed"})
            return
        self.send_response(204)
        self._cors(origin)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if not _origin_allowed(self.headers.get("Origin", "")):
            self._json(403, {"error": "origin not allowed"})
            return
        if self.path.split("?")[0] in ("/health", "/"):
            self._json(200, health_of(self._engine).as_dict())
            return
        self._json(404, {"error": f"no such path: {self.path}"})

    def do_POST(self) -> None:
        if not _origin_allowed(self.headers.get("Origin", "")):
            self._json(403, {"error": "origin not allowed"})
            return
        if self.path.split("?")[0] != "/gate":
            self._json(404, {"error": f"no such path: {self.path}"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Content-Length is not a number"})
            return
        if length <= 0:
            self._json(400, {"error": "no image in the request body"})
            return
        if length > MAX_IMAGE_BYTES:
            self._json(
                413,
                {"error": f"image larger than {MAX_IMAGE_BYTES} bytes"},
            )
            return

        image = self.rfile.read(length)
        if len(image) != length:
            self._json(400, {"error": "the request body was truncated"})
            return

        try:
            result = gate_image(self._engine, image)
        except Exception as exc:  # noqa: BLE001
            # Reported, not raised: a decoder failure on one capture must not
            # take the sidecar down mid-clinic. The UI shows "the gate did not
            # run", which is the honest answer and not a negative result.
            self._json(
                422,
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "note": "the image could not be graded; this is not a result",
                },
            )
            return

        self._json(200, result)


def serve(engine: InferenceEngine, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Bind the sidecar on loopback. The caller runs it."""
    httpd = ThreadingHTTPServer((HOST, port), GateSidecar)
    httpd.engine = engine  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument(
        "--svm",
        type=pathlib.Path,
        default=None,
        help="QuickQual head; defaults to $NETRA_QUICKQUAL_SVM",
    )
    ap.add_argument(
        "--checkpoint",
        type=pathlib.Path,
        default=None,
        help="DR checkpoint; defaults to $NETRA_DR_CHECKPOINT",
    )
    ap.add_argument(
        "--random-init",
        action="store_true",
        help="skip pretrained feature weights (tests only; never a real gate)",
    )
    ap.add_argument(
        "--calibrate",
        type=pathlib.Path,
        default=None,
        metavar="CALIB_IMAGES_DIR",
        help=(
            "conformalize on the CALIBRATION split under this directory, so "
            "results carry a real prediction set instead of abstaining. "
            "Off by default: this is MODEL_LANDING.md section 3 and a "
            "methodology decision, not a startup convenience. "
            "Typically data/aptos/images/calib"
        ),
    )
    ap.add_argument(
        "--calibrate-limit",
        type=int,
        default=None,
        help="use at most N calibration images (a faster demo start)",
    )
    args = ap.parse_args(argv)

    engine = build_engine(
        svm_path=args.svm,
        checkpoint=args.checkpoint,
        pretrained=not args.random_init,
    )

    if args.calibrate is not None:
        print(f"conformalizing on the calibration split in {args.calibrate} ...")
        try:
            wrapper, report = conformalize_from_calib(
                engine.classifier, args.calibrate, limit=args.calibrate_limit
            )
        except Exception as exc:  # noqa: BLE001 - reported; the sidecar still serves
            # A failed calibration must not stop the sidecar: without it the
            # engine abstains and says why, which is a worse demo but a true
            # answer. Silently continuing with no prediction sets would be the
            # bug, so it is printed loudly.
            print(f"  calibration FAILED ({type(exc).__name__}: {exc})")
            print("  continuing without it: results will abstain, not grade.")
        else:
            engine.abstention = wrapper
            print(
                f"  conformalized on {report['n']} calibration images at "
                f"confidence {wrapper.confidence_level}"
            )

    health = health_of(engine)

    print(f"netra gate sidecar on http://{HOST}:{args.port}")
    print(f"  model_version      {health.model_version}")
    print(f"  gate_loaded        {health.gate_loaded}")
    print(f"  classifier_loaded  {health.classifier_loaded}")
    print(f"  conformalized      {health.conformalized}")
    if health.model_version == UNLOADED:
        # Said once, loudly, at startup. The UI says it too, per capture.
        print(
            "\n  model_version is 'unloaded': this sidecar will return "
            "verdicts with\n  no grade, and invent nothing. Set "
            "NETRA_DR_CHECKPOINT and NETRA_QUICKQUAL_SVM,\n  or pass "
            "--checkpoint and --svm."
        )
    if not health.conformalized:
        print(
            "\n  no conformal calibration: results will abstain rather than "
            "report an\n  argmax grade. That is MODEL_LANDING.md section 3, "
            "and it is Lane C's step."
        )

    httpd = serve(engine, port=args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

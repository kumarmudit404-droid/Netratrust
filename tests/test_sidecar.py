"""The on-device gate sidecar.

The sidecar is the one piece of this system that holds a fundus image in
memory and writes it to disk, so most of what is worth asserting here is about
what it REFUSES and what it cleans up, not about verdicts - verdicts are
`netra/models/infer.py`'s and are tested in `test_infer.py`.

Four things carry this file:

* it binds loopback and only loopback, and refuses a non-local `Origin`;
* the temporary file it has to create (because `InferenceEngine.run` takes a
  path) is removed even when inference raises;
* `/health` reports `unloaded` as `unloaded` rather than flattering itself;
* the conformalisation helper reads the CALIBRATION split and nothing else.

No test here loads a real checkpoint. The artifacts are gigabytes and env-var
only, and a suite that needs them is a suite that fails on a fresh clone.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
from threading import Thread

import pytest

from netra.models.dr import UNLOADED, DRClassifier
from netra.sidecar.server import (
    ALLOWED_ORIGIN_HOSTS,
    HOST,
    MAX_IMAGE_BYTES,
    _origin_allowed,
    build_engine,
    conformalize_from_calib,
    gate_image,
    health_of,
    serve,
)
from tests.test_quality import fundus

# --------------------------------------------------------------- the engine


@pytest.fixture
def empty_engine(no_model_artifacts):
    """An engine with nothing loaded, and nothing on the environment either.

    `no_model_artifacts` matters: without it an exported NETRA_DR_CHECKPOINT
    silently loads a real model into a test asserting there is none - the same
    failure the nine refusal tests in test_dr/test_infer/test_quality had.
    """
    return build_engine(pretrained=False)


def test_an_engine_builds_with_nothing_on_disk(empty_engine):
    """Both loaders report rather than raise, so the sidecar always starts.
    A gate process that refuses to boot in a camp with no checkpoint is worse
    than one that boots and says it has no model."""
    health = health_of(empty_engine)
    assert health.ok is True, "the process is up; that is what ok means"
    assert health.model_version == UNLOADED
    assert health.gate_loaded is False
    assert health.classifier_loaded is False
    assert health.conformalized is False


def test_health_keeps_reachable_and_loaded_apart(empty_engine):
    """`ok` is 'the sidecar answered', NOT 'a model is loaded'. The UI needs
    those apart: a reachable sidecar with no checkpoint is a different thing
    to tell an operator than no sidecar at all."""
    health = health_of(empty_engine)
    assert health.ok is True and health.gate_loaded is False


def test_abstention_is_not_built_by_default(empty_engine):
    """Conformalisation is a methodology decision (MODEL_LANDING.md section 3),
    so it is opt-in. Without it `infer.py` abstains and says why instead of
    reporting an argmax."""
    assert empty_engine.abstention is None
    assert health_of(empty_engine).conformalized is False


# ------------------------------------------------- the image on disk, briefly


def test_the_temporary_image_is_removed(empty_engine, monkeypatch):
    """The device keeps no copy of an image it was only asked to grade."""
    seen: list[pathlib.Path] = []

    def spy(path):
        seen.append(pathlib.Path(path))
        raise RuntimeError("inference exploded")

    monkeypatch.setattr(empty_engine, "run", spy)

    with pytest.raises(RuntimeError):
        gate_image(empty_engine, b"not really a png")

    assert seen, "the engine was never called"
    # Removed in a `finally`, so a crash mid-inference does not leave a fundus
    # image behind on the capture device.
    assert not seen[0].exists(), f"{seen[0]} survived a failed inference"


def test_the_image_reaches_the_engine_unchanged(empty_engine, monkeypatch):
    """The bytes the sidecar writes are the bytes it was posted: the hash the
    model computes has to be the hash of what the caller sent."""
    import hashlib

    payload = b"\x89PNG\r\n\x1a\n" + b"some pixels" * 100
    digests: list[str] = []

    def spy(path):
        digests.append(hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest())
        raise RuntimeError("stop here")

    monkeypatch.setattr(empty_engine, "run", spy)
    with pytest.raises(RuntimeError):
        gate_image(empty_engine, payload)

    assert digests == [hashlib.sha256(payload).hexdigest()]


# ------------------------------------------------------------------- origins


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173", "https://localhost:443", ""],
)
def test_local_origins_are_allowed(origin):
    """An absent Origin is fine too: curl and the CLI do not send one."""
    assert _origin_allowed(origin) is True


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example.com",
        "https://netratrust.fly.dev",
        "http://localhost.evil.com",
        "http://10.0.0.5:5173",
    ],
)
def test_remote_origins_are_refused(origin):
    """A page on the network must not be able to post an image to a clinician's
    sidecar. `localhost.evil.com` is the one that looks local and is not."""
    assert _origin_allowed(origin) is False


def test_the_allowlist_is_loopback_only():
    assert ALLOWED_ORIGIN_HOSTS == frozenset({"localhost", "127.0.0.1", "[::1]"})


def test_the_sidecar_binds_loopback_and_is_not_configurable():
    """SPEC.md: the image never leaves the device. Binding 0.0.0.0 would make
    that false, so HOST is a constant and not a flag."""
    assert HOST == "127.0.0.1"
    import inspect

    from netra.sidecar import server

    src = inspect.getsource(server)
    assert '"0.0.0.0"' not in src and "'0.0.0.0'" not in src


# ------------------------------------------------------------- over the wire


@pytest.fixture
def running(empty_engine):
    """The real handler on a real socket, on a port the OS picks."""
    httpd = serve(empty_engine, port=0)
    Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://{HOST}:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


def _post(url, body: bytes, headers=None):
    req = urllib.request.Request(
        url, data=body, headers=headers or {"Content-Type": "image/png"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


def test_health_answers_over_http(running):
    status, body, _ = _get(f"{running}/health")
    assert status == 200
    assert body["model_version"] == UNLOADED
    assert body["gate_loaded"] is False


def test_a_verdict_is_never_cached(running):
    """The next capture is a different image."""
    _status, _body, headers = _get(f"{running}/health")
    assert headers.get("Cache-Control") == "no-store"


def test_an_unknown_path_is_a_404_not_a_verdict(running):
    status, body, _ = _get(f"{running}/v1/encounters")
    assert status == 404
    assert "no such path" in body["error"]


def test_a_remote_origin_is_refused_over_http(running):
    status, body, _ = _get(
        f"{running}/health", headers={"Origin": "http://evil.example.com"}
    )
    assert status == 403
    assert body["error"] == "origin not allowed"


def test_an_empty_body_is_refused(running):
    status, body, _ = _post(f"{running}/gate", b"")
    assert status == 400
    assert "no image" in body["error"]


def test_an_oversized_image_is_refused_before_it_is_read(running):
    """The cap is checked against Content-Length, so a hostile body is never
    pulled into memory in the first place.

    Driven over a raw socket, and the body is never sent at all - that IS the
    assertion. The server answers 413 from the header alone, so nothing has to
    be transferred and there is no half-sent 32 MB upload to race the close.
    (urllib cannot express this: it insists on sending the body it declared,
    and turns the server's early close into a transport error, not a status.)
    """
    import socket
    from urllib.parse import urlparse

    crlf = chr(13) + chr(10)
    url = urlparse(running)
    request = crlf.join(
        [
            "POST /gate HTTP/1.1",
            f"Host: {url.hostname}:{url.port}",
            "Content-Type: image/png",
            f"Content-Length: {MAX_IMAGE_BYTES + 1}",
            "",
            "",
        ]
    )

    with socket.create_connection((url.hostname, url.port), timeout=10) as s:
        s.sendall(request.encode())
        status_line = s.recv(256).decode("latin-1", "replace").split(crlf)[0]

    assert "413" in status_line, status_line


def test_an_ungradable_body_is_422_and_not_a_result(running):
    """A decoder failure on one capture must not take the sidecar down, and
    must not come back looking like a verdict."""
    status, body, _ = _post(f"{running}/gate", b"this is not an image at all")
    assert status == 422
    assert "not a result" in body["note"]
    assert "quality_verdict" not in body


def test_the_sidecar_survives_a_bad_request(running):
    """The request after a failure still works - the clinic does not restart a
    process between patients."""
    _post(f"{running}/gate", b"garbage")
    status, body, _ = _get(f"{running}/health")
    assert status == 200 and body["ok"] is True


def test_a_real_frame_gets_a_result_shaped_answer(running, monkeypatch):
    """A real PNG over the real socket, so the wire shape `qualityGate.ts` maps
    field-for-field is exercised end to end rather than assumed."""
    import cv2

    ok, buf = cv2.imencode(".png", cv2.cvtColor(fundus(size=128), cv2.COLOR_RGB2BGR))
    assert ok
    status, body, _ = _post(f"{running}/gate", buf.tobytes())
    assert status == 200
    # Nothing is loaded, so this is the honest "no result" shape.
    assert body["quality_verdict"] is None
    assert body["prediction_set"] is None
    assert body["grade"] is None
    assert body["model_version"] == UNLOADED
    assert set(body) == {
        "image_sha256",
        "quality_verdict",
        "cause",
        "prediction_set",
        "grade",
        "abstain",
        "model_version",
        "quality_score_milli",
        "note",
    }, "the wire shape the UI maps field-for-field has changed"


# ------------------------------------------------------- conformalisation


def test_conformalizing_without_a_checkpoint_refuses(no_model_artifacts, tmp_path):
    """It reads probabilities from the real classifier, so it cannot run at all
    without one - which is the point: there is nothing to calibrate against."""
    clf = DRClassifier(checkpoint=None)
    with pytest.raises(RuntimeError, match="cannot conformalize"):
        conformalize_from_calib(clf, tmp_path)


def test_conformalisation_reads_the_calibration_split_and_only_that():
    """`.claude/rules/ml.md` and tracker.md both name evaluation drift as the
    risk no hook catches. The split name is hard-coded; `dataset.collect`
    refuses `test` unless `allow_test=True`, which is never passed here."""
    import ast
    import inspect
    import textwrap

    # The docstring explains `allow_test`, so strip it before looking: this
    # must assert about the CODE, not about the prose next to it.
    tree = ast.parse(textwrap.dedent(inspect.getsource(conformalize_from_calib)))
    fn = tree.body[0]
    if (
        fn.body
        and isinstance(fn.body[0], ast.Expr)
        and isinstance(fn.body[0].value, ast.Constant)
    ):
        fn.body = fn.body[1:]
    code = ast.unparse(fn)

    assert "'calib'" in code or '"calib"' in code, (
        "the split name is no longer hard-coded"
    )
    assert "allow_test" not in code, "conformalisation must never reach the test split"
    assert "'test'" not in code and '"test"' not in code

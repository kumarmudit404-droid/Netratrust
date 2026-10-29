"""T-21: the deployment story, held to the three things that actually break it.

1. The SPA mount must serve the front end WITHOUT swallowing `/v1`. A deployed
   API that answers 200-and-a-page-of-HTML to a misspelled endpoint costs
   somebody an hour.
2. It must be OFF by default, so the app stays exactly the frozen nine in dev
   and in every other test in this suite.
3. `fly.toml` must put the SQLite database and the device keys INSIDE the
   mounted volume. The database is recoverable; the Ed25519 private keys are
   not - lose them and every existing ledger entry fails verification with
   `unknown signer_kid`, which is the whole demo.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
FLY_TOML = ROOT / "fly.toml"
DOCKERFILE = ROOT / "Dockerfile"


# --------------------------------------------------------------- the SPA mount


@pytest.fixture
def dist(tmp_path):
    """A stand-in for `netra/ui/dist`."""
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>NetraTrust</title>")
    (d / "assets" / "index.js").write_text("console.log('app')")
    return d


@pytest.fixture
def ui_client(tmp_path, monkeypatch, registered, dist):
    from netra.api.main import create_app

    monkeypatch.setenv("NETRA_DB", str(tmp_path / "netra.db"))
    monkeypatch.setenv("NETRA_KEYS_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("NETRA_UI_DIR", str(dist))
    with TestClient(create_app()) as c:
        yield c


def test_the_ui_is_not_mounted_without_the_env_var(client):
    """Off by default: `client` sets no NETRA_UI_DIR, so `/` is not served."""
    assert client.get("/").status_code == 404


def test_a_missing_dist_directory_does_not_stop_the_api(
    tmp_path, monkeypatch, registered
):
    """The API is useful on its own; it is not hostage to the front-end build."""
    from netra.api.main import create_app

    monkeypatch.setenv("NETRA_DB", str(tmp_path / "netra.db"))
    monkeypatch.setenv("NETRA_KEYS_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("NETRA_UI_DIR", str(tmp_path / "does-not-exist"))
    with TestClient(create_app()) as c:
        assert c.get("/v1/ledger/verify").status_code == 200


def test_the_app_shell_is_served_at_the_root(ui_client):
    res = ui_client.get("/")
    assert res.status_code == 200
    assert "NetraTrust" in res.text


def test_a_static_asset_is_served(ui_client):
    res = ui_client.get("/assets/index.js")
    assert res.status_code == 200
    assert "console.log" in res.text


@pytest.mark.parametrize(
    "route", ["/capture", "/grade", "/referrals", "/sites", "/ledger"]
)
def test_a_hard_refresh_on_a_client_route_serves_the_shell(ui_client, route):
    """`BrowserRouter` means these paths exist only in the browser.

    Without the index.html fallback a presenter who reloads the page mid-demo
    gets a 404 instead of the view they were on.
    """
    res = ui_client.get(route)
    assert res.status_code == 200
    assert "NetraTrust" in res.text


def test_the_nine_endpoints_still_answer_with_the_ui_mounted(ui_client):
    assert ui_client.get("/v1/ledger/verify").json() == {
        "ok": True,
        "first_bad_index": None,
    }


@pytest.mark.parametrize("path", ["/v1/typo", "/v1/encounters/extra", "/v1"])
def test_an_unknown_api_path_is_a_404_and_not_the_app_shell(ui_client, path):
    """The reason `SpaFiles` exists instead of a plain StaticFiles mount."""
    res = ui_client.get(path)
    assert res.status_code == 404
    assert "<!doctype html" not in res.text.lower()


def test_mounting_the_ui_adds_no_tenth_endpoint(ui_client):
    from netra.api.main import contract_routes

    registered = {
        (method, route.path)
        for route in contract_routes(ui_client.app)
        for method in sorted(route.methods)
        if method != "HEAD"
    }
    assert len(registered) == 9


# ------------------------------------------------------------- fly.toml / image


@pytest.fixture(scope="module")
def fly() -> str:
    assert FLY_TOML.exists(), "fly.toml is T-21; the deploy needs it"
    return FLY_TOML.read_text(encoding="utf-8")


def _mount_destination(fly: str) -> str:
    match = re.search(r'destination\s*=\s*"([^"]+)"', fly)
    assert match, "fly.toml declares no volume destination"
    return match.group(1)


def _env(fly: str, key: str) -> str:
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', fly, re.MULTILINE)
    assert match, f"fly.toml sets no {key}"
    return match.group(1)


def test_the_database_lives_inside_the_mounted_volume(fly):
    """A SQLite file outside the mount is deleted on every deploy."""
    assert _env(fly, "NETRA_DB").startswith(_mount_destination(fly) + "/")


def test_the_device_keys_live_inside_the_mounted_volume(fly):
    """Lose these and every existing entry fails verify with unknown signer_kid.

    `tests/test_ledger.py::test_keystore_persists_so_a_chain_survives_a_restart`
    is the same property one layer down.
    """
    assert _env(fly, "NETRA_KEYS_DIR").startswith(_mount_destination(fly) + "/")


def test_only_one_machine_runs(fly):
    """SQLite has a single writer and a Fly volume attaches to one machine.

    A second machine would either fail to mount the volume or write to its own
    copy, which silently forks the ledger.
    """
    assert re.search(r"min_machines_running\s*=\s*1", fly)
    assert re.search(r"auto_stop_machines\s*=\s*(false|'off'|\"off\")", fly)


def test_the_image_is_not_asked_to_carry_torch(fly):
    """The API imports no model code; torch would add gigabytes for nothing.

    `requirements.txt` is the pinned source of truth and is NOT edited - the
    Dockerfile installs the subset the API imports, at those same versions.
    `test_runtime_pins_match_requirements` keeps the two in step.
    """
    assert DOCKERFILE.exists(), "Dockerfile is T-21"
    # Only the install lines matter. The header explains WHY torch is absent,
    # and that sentence must not fail the test it documents.
    installed = {name.lower() for name, _ in _dockerfile_pins()}
    for heavy in ("torch", "torchvision", "timm", "opencv-python-headless", "mapie"):
        assert heavy not in installed


def _dockerfile_pins() -> list[tuple[str, str]]:
    """Every `name==version` the Dockerfile installs, from its pip lines."""
    return re.findall(
        r"^\s*([A-Za-z0-9_.\-]+)==([^\s\\]+)",
        DOCKERFILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )


def test_runtime_pins_match_requirements():
    """Every version the Dockerfile installs must equal requirements.txt's pin.

    The runtime subset is a selection, not a re-pin. If these drift, the
    deployed app is running something nobody tested.
    """
    pins: dict[str, str] = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower()] = version.strip()

    installed = _dockerfile_pins()
    assert installed, "the Dockerfile pins nothing"
    for name, version in installed:
        key = name.lower()
        assert key in pins, f"{name} is not in requirements.txt"
        assert version == pins[key], (
            f"{name}=={version} in the Dockerfile but {pins[key]} in requirements.txt"
        )


def test_the_ui_is_built_and_pointed_at_by_the_image():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "npm" in text, "the image has to build the front end"
    assert "NETRA_UI_DIR" in text, "nothing would serve the built front end"

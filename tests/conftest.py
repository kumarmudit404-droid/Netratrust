"""Shared fixtures. Every test gets its own database.

Nothing here touches the repo's `netra.db` or `keys/`: a test that appends to
the real ledger, or signs with the real device key, would make the tamper demo
unreproducible.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from netra.db.engine import init_db
from netra.db.models import Device, Site
from netra.db.util import now_iso
from netra.ledger.keys import KeyStore

TEST_SITE = "site-07"
TEST_KID = "device-test"


@pytest.fixture
def keystore(tmp_path) -> KeyStore:
    """A keystore under tmp_path. Never the repo's `keys/`."""
    return KeyStore(tmp_path / "keys")


@pytest.fixture
def engine(tmp_path):
    return init_db(str(tmp_path / "netra.db"))


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def registered(session, keystore):
    """One site and one device, with the device's real public key stored.

    Verification resolves a signer's public key from `devices`, so a chain
    signed by an unregistered kid fails - correctly, but not for the reason a
    test about hashes wants to assert.
    """
    session.add(
        Site(id=TEST_SITE, name="Test camp", region="test", created_at=now_iso())
    )
    # Flush before the device: foreign keys are ON, and SQLAlchemy does not
    # order these two INSERTs for us (there is no relationship() between them).
    session.flush()
    session.add(
        Device(
            kid=TEST_KID,
            site_id=TEST_SITE,
            ed25519_pub=keystore.public_hex(TEST_KID),
            registered_at=now_iso(),
        )
    )
    session.commit()
    return {"site_id": TEST_SITE, "device_kid": TEST_KID}


@pytest.fixture
def client(tmp_path, monkeypatch, registered):
    """A TestClient over the real app, with the real lifespan.

    `NETRA_DB` and `NETRA_KEYS_DIR` point at the same tmp_path the `engine` and
    `keystore` fixtures use, so a test can inspect the database the app just
    wrote and verify signatures against the key it just signed with. The
    lifespan is exercised rather than bypassed: `TestClient` as a context
    manager is what triggers it.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("NETRA_DB", str(tmp_path / "netra.db"))
    monkeypatch.setenv("NETRA_KEYS_DIR", str(tmp_path / "keys"))

    from netra.api.main import create_app

    with TestClient(create_app()) as c:
        yield c


# ----------------------------------------------- model artifacts, absent

#: The two env-var-only loader paths. `DRClassifier` and `QualityGate` both
#: fall back to these when their constructor argument is None, so a developer
#: (or `fly.toml`'s `[env]`) having them exported silently loads a real model
#: into a test that asked for an empty one.
MODEL_ARTIFACT_ENVS = ("NETRA_DR_CHECKPOINT", "NETRA_QUICKQUAL_SVM")


@pytest.fixture
def no_model_artifacts(monkeypatch):
    """Unset both artifact env vars, so `checkpoint=None` really means none.

    The refusal tests - an unloaded gate must not guess a verdict, an unloaded
    classifier must raise rather than return a grade - construct their loaders
    with nothing and assert `model_version == "unloaded"`. That assertion is
    about the argument, not about the machine the suite runs on, and without
    this fixture it inverts the moment the artifacts are on disk and exported:
    the loader finds a real model and the refusal never happens.

    `fly.toml` puts both variables in `[env]`, so the exported case is the
    deployed case, not a local quirk.
    """
    for name in MODEL_ARTIFACT_ENVS:
        monkeypatch.delenv(name, raising=False)

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

TEST_SITE = "site-07"
TEST_KID = "device-test"

#: A syntactically valid raw Ed25519 public key for tests that only need the
#: `devices` row to exist. Signature checks use the `keystore` fixture instead.
PLACEHOLDER_PUB = "11" * 32


@pytest.fixture
def engine(tmp_path):
    return init_db(str(tmp_path / "netra.db"))


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def registered(session):
    """One site and one device, so an encounter's foreign keys resolve."""
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
            ed25519_pub=PLACEHOLDER_PUB,
            registered_at=now_iso(),
        )
    )
    session.commit()
    return {"site_id": TEST_SITE, "device_kid": TEST_KID}

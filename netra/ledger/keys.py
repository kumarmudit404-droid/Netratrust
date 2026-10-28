"""Ed25519 keystore. Per-device keypairs replace mTLS (SPEC.md section 8).

Private keys live in `keys/` which is gitignored and denied to tooling in
`.claude/settings.json`. A `signer_kid` travels with every ledger entry and
every checkpoint from day one, so key rotation is answerable later without a
schema change: verification resolves the public key by kid.
"""

from __future__ import annotations

import os
import pathlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DEFAULT_KEYS_DIR = "keys"

#: The kid that signs checkpoints. A checkpoint attests the chain head, which is
#: a server-side fact, so it is not signed with a capture device's key.
SERVER_KID = "server-1"


class KeyStore:
    """Loads, and on first use creates, `keys/<kid>.pem` + `keys/<kid>.pub`.

    Creating on first use is deliberate: a demo box with no keys must still
    produce a verifiable chain. The alternative - signing with a throwaway
    in-memory key - produces a chain that cannot be verified after a restart,
    which is worse than no signature at all.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self.dir = pathlib.Path(
            directory or os.environ.get("NETRA_KEYS_DIR") or DEFAULT_KEYS_DIR
        )
        self._cache: dict[str, Ed25519PrivateKey] = {}

    # ------------------------------------------------------------ private keys

    def private_key(self, kid: str) -> Ed25519PrivateKey:
        if kid in self._cache:
            return self._cache[kid]
        path = self.dir / f"{kid}.pem"
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise TypeError(f"{path} is not an Ed25519 private key")
        else:
            key = self._generate(kid)
        self._cache[kid] = key
        return key

    def _generate(self, kid: str) -> Ed25519PrivateKey:
        key = Ed25519PrivateKey.generate()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{kid}.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        (self.dir / f"{kid}.pub").write_bytes(public_hex(key.public_key()).encode())
        return key

    # ------------------------------------------------------------- public keys

    def public_hex(self, kid: str) -> str:
        return public_hex(self.private_key(kid).public_key())

    def known_public_hex(self, kid: str) -> str | None:
        """The public key for `kid` if one is already on disk, else None.

        Verification uses this rather than `public_hex`, which would GENERATE a
        key for an unknown kid and then check a signature against it. That
        would turn "we have never seen this signer" into a signature mismatch
        on a specific entry, which reads as tampering. Returning None lets
        verify report the real reason.
        """
        pub = self.dir / f"{kid}.pub"
        if pub.exists():
            return pub.read_bytes().decode().strip()
        pem = self.dir / f"{kid}.pem"
        if pem.exists():
            return self.public_hex(kid)
        return None

    # --------------------------------------------------------------- signing

    def sign(self, kid: str, message: bytes) -> str:
        """Sign raw bytes (the 32-byte entry hash) and return hex."""
        return self.private_key(kid).sign(message).hex()


def public_hex(public_key: Ed25519PublicKey) -> str:
    """Raw 32-byte public key as hex - the form stored in `devices.ed25519_pub`."""
    return public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def load_public_hex(pub_hex: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))


def verify_signature(pub_hex: str, signature_hex: str, message: bytes) -> bool:
    """True when `signature_hex` is a valid Ed25519 signature over `message`."""
    try:
        load_public_hex(pub_hex).verify(bytes.fromhex(signature_hex), message)
    except (InvalidSignature, ValueError):
        return False
    return True

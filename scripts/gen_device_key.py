"""Generate a per-device Ed25519 keypair (replaces mTLS). Private key stays in keys/ (gitignored)."""
import sys, pathlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
kid = sys.argv[1] if len(sys.argv) > 1 else "device-1"
k = Ed25519PrivateKey.generate()
p = pathlib.Path("keys"); p.mkdir(exist_ok=True)
(p/f"{kid}.pem").write_bytes(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
(p/f"{kid}.pub").write_bytes(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex().encode())
print("wrote", kid)

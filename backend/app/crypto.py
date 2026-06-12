import os
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings


def _key() -> bytes:
    hex_key = get_settings().token_encryption_key
    if len(hex_key) != 64:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY must be 64 hex chars (32 bytes)")
    return bytes.fromhex(hex_key)


def encrypt(plain: str) -> str:
    iv = os.urandom(12)
    ct = AESGCM(_key()).encrypt(iv, plain.encode("utf-8"), None)
    return b64encode(iv + ct).decode("ascii")


def decrypt(blob: str) -> str:
    raw = b64decode(blob)
    iv, ct = raw[:12], raw[12:]
    return AESGCM(_key()).decrypt(iv, ct, None).decode("utf-8")

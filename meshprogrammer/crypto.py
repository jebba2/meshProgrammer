"""Optional password-based encryption for backup/channel payload dicts.

Uses scrypt (RFC 7914 interactive parameters) to derive a key from a
password and a random per-file salt, then Fernet (AES128-CBC + HMAC, from
the `cryptography` package) for authenticated symmetric encryption. An
encrypted payload is itself a JSON-serializable dict (an "envelope"), so it
can be written/read through the same storage functions as a plain payload.
"""

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_SALT_LENGTH = 16
_KEY_LENGTH = 32
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class WrongPasswordError(Exception):
    """Raised when decrypting a payload with the wrong password."""


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=_KEY_LENGTH, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def is_encrypted(data: dict[str, Any]) -> bool:
    """Return True if ``data`` is an encrypted envelope rather than a plain payload."""
    return data.get("encrypted") is True


def encrypt_payload(payload: dict[str, Any], password: str) -> dict[str, Any]:
    """Encrypt ``payload`` with ``password``, returning a JSON-serializable envelope."""
    salt = os.urandom(_SALT_LENGTH)
    key = _derive_key(password, salt)
    ciphertext = Fernet(key).encrypt(json.dumps(payload).encode("utf-8"))
    return {
        "encrypted": True,
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": ciphertext.decode("ascii"),
    }


def decrypt_payload(envelope: dict[str, Any], password: str) -> dict[str, Any]:
    """Decrypt an envelope produced by ``encrypt_payload``, returning the original payload."""
    salt = base64.b64decode(envelope["salt"])
    key = _derive_key(password, salt)
    try:
        plaintext = Fernet(key).decrypt(envelope["ciphertext"].encode("ascii"))
    except InvalidToken as exc:
        raise WrongPasswordError("Incorrect password") from exc
    return json.loads(plaintext)

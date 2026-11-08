"""The encrypted ``.gleaks`` container.

Layout (all integers are single bytes)::

    "GLEAKS" | format | kdf | log2(n) | r | p | salt[16] | nonce[12] | ciphertext+tag

The whole header, nonce included, is authenticated as associated data, so any
tampering fails decryption. The plaintext is a serialized SQLite database.
"""

from __future__ import annotations

import hashlib
import os
import unicodedata
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"GLEAKS"
FORMAT_VERSION = 1
KDF_SCRYPT = 1
_HEADER_LEN = len(MAGIC) + 5 + 16 + 12
MIN_PASSWORD_LENGTH = 8
# The parameters come from the file being opened, so bound what it can demand.
_MAX_LOG2N, _MAX_R, _MAX_P = 20, 16, 4


class ContainerError(Exception):
    """The file is not a profile this version can read."""


class WrongPasswordError(Exception):
    """Authentication failed: wrong password, or a damaged file."""


@dataclass(frozen=True)
class KdfParams:
    log2n: int = 17
    r: int = 8
    p: int = 1


def derive_key(password: str, salt: bytes, params: KdfParams) -> bytes:
    secret = unicodedata.normalize("NFC", password).encode("utf-8")
    n = 1 << params.log2n
    return hashlib.scrypt(secret, salt=salt, n=n, r=params.r, p=params.p, dklen=32,
                          maxmem=128 * n * params.r * params.p + 32 * 1024 * 1024)


def new_salt() -> bytes:
    return os.urandom(16)


def seal(key: bytes, salt: bytes, params: KdfParams, plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    header = (MAGIC + bytes([FORMAT_VERSION, KDF_SCRYPT, params.log2n, params.r, params.p])
              + salt + nonce)
    return header + AESGCM(key).encrypt(nonce, plaintext, header)


def read_header(blob: bytes) -> tuple[KdfParams, bytes]:
    """Validate the header and return its KDF parameters and salt."""
    if len(blob) < _HEADER_LEN + 16 or not blob.startswith(MAGIC):
        raise ContainerError("not a GLeaks profile")
    version, kdf, log2n, r, p = blob[len(MAGIC):len(MAGIC) + 5]
    if version != FORMAT_VERSION or kdf != KDF_SCRYPT:
        raise ContainerError("unsupported profile format")
    if not (10 <= log2n <= _MAX_LOG2N and 1 <= r <= _MAX_R and 1 <= p <= _MAX_P):
        raise ContainerError("unsupported key derivation parameters")
    salt_at = len(MAGIC) + 5
    return KdfParams(log2n, r, p), blob[salt_at:salt_at + 16]


def open_sealed(key: bytes, blob: bytes) -> bytes:
    header, ciphertext = blob[:_HEADER_LEN], blob[_HEADER_LEN:]
    try:
        return AESGCM(key).decrypt(header[-12:], ciphertext, header)
    except InvalidTag as exc:
        raise WrongPasswordError from exc

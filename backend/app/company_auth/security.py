"""Password and session-token helpers for company auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 260_000
_SALT_BYTES = 16


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Hash a plaintext password with PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return (
        f"{_PBKDF2_ALGORITHM}${_PBKDF2_ITERATIONS}$"
        f"{_b64encode(salt)}${_b64encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True when ``password`` matches ``stored_hash``."""
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = stored_hash.split("$", 3)
        if algorithm != _PBKDF2_ALGORITHM:
            return False
        iterations = int(raw_iterations)
        salt = _b64decode(raw_salt)
        expected = _b64decode(raw_digest)
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    return f"fpi_sess_{secrets.token_urlsafe(32)}"


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

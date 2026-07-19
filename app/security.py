from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def _read_or_create_secret_file(name: str, length: int = 64) -> str:
    path = INSTANCE_DIR / name
    if path.exists():
        return path.read_text().strip()
    secret = secrets.token_urlsafe(length)
    path.write_text(secret)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return secret


def session_secret() -> str:
    return os.getenv("NORTHSTAR_SESSION_SECRET") or _read_or_create_secret_file("dev_session_secret.txt")


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240_000)
    return "pbkdf2_sha256$240000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def new_token(bytes_len: int = 32) -> str:
    return secrets.token_urlsafe(bytes_len)


def csrf_token(session: dict[str, Any]) -> str:
    token = session.get("csrf_token")
    if not token:
        token = new_token(24)
        session["csrf_token"] = token
    return token


def validate_csrf(session: dict[str, Any], submitted: str | None) -> bool:
    token = session.get("csrf_token")
    return bool(token and submitted and hmac.compare_digest(str(token), str(submitted)))

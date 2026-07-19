from __future__ import annotations

import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
KEY_FILE = INSTANCE_DIR / "dev_fernet.key"


def _load_key() -> bytes:
    env_key = os.getenv("NORTHSTAR_FERNET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return key


_FERNET = Fernet(_load_key())


def encrypt_text(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return _FERNET.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _FERNET.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return "[unable to decrypt]"


def encrypt_bytes(value: bytes) -> bytes:
    return _FERNET.encrypt(value)


def decrypt_bytes(value: bytes) -> bytes:
    return _FERNET.decrypt(value)

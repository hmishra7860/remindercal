import base64
import datetime as dt
import hashlib

import bcrypt
import jwt
from cryptography.fernet import Fernet

from .config import settings

ALGORITHM = "HS256"


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": _now() + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_action_token(reminder_id: int, action: str) -> str:
    """Signed, expiring token embedded in email buttons (Mark as Done / Snooze)."""
    payload = {
        "type": "action",
        "rid": reminder_id,
        "act": action,
        "exp": _now() + dt.timedelta(days=settings.action_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


# ---------- symmetric encryption for stored SMTP passwords ----------
def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")

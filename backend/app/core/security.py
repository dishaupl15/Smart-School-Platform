from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import Settings, get_settings

_password_hasher = PasswordHash((Argon2Hasher(),))
ACCESS_TOKEN_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _password_hasher.hash(password)
        return False
    try:
        return _password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: UUID,
    session_id: UUID,
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ACCESS_TOKEN_ALGORITHM,
    )
    return token, expires_at


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ACCESS_TOKEN_ALGORITHM],
        options={"require": ["sub", "sid", "typ", "iat", "exp", "jti"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("Wrong token type.")
    UUID(payload["sub"])
    UUID(payload["sid"])
    return payload


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    key = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    return hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()

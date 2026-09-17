"""Password hashing and JWT encode/decode. No FastAPI here; deps.py wires
this into the request cycle."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import Settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Used when login hits an unknown email so that branch costs one bcrypt
# verify like the known-email branch does. Without it, response time
# reveals which emails are registered.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def burn_password_check(password: str) -> None:
    bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))


def create_access_token(subject: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    """Returns the subject (user id) or raises jwt.PyJWTError."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return payload["sub"]

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# bcrypt hashes at most 72 bytes and bcrypt 5.x raises on anything longer
# instead of silently truncating. The limit is on UTF-8 bytes, not
# characters, so a short passphrase of multi-byte characters can still hit it.
PASSWORD_MAX_BYTES = 72


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=PASSWORD_MAX_BYTES)

    @field_validator("password")
    @classmethod
    def _within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} bytes.")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    user: UserOut

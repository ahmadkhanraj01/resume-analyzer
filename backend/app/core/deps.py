"""FastAPI dependencies: DB session and the current authenticated user."""

from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import TokenInvalidError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise TokenInvalidError()

    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = decode_access_token(token, settings)
    except jwt.PyJWTError:
        raise TokenInvalidError() from None

    user = db.get(User, user_id)
    if user is None:
        raise TokenInvalidError()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]

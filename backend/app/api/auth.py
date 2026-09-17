from fastapi import APIRouter, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.deps import CurrentUserDep, DbDep, SettingsDep
from app.core.exceptions import InvalidCredentialsError, RateLimitedError, ValidationError
from app.core.limiter import get_auth_limiter
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _throttle(request: Request, settings) -> None:
    """Register and login are keyed on client IP since there is no user yet.
    Without this, password guessing is unthrottled."""
    ip = request.client.host if request.client else "unknown"
    if not get_auth_limiter(settings.auth_attempts_per_hour).acquire(ip):
        raise RateLimitedError("Too many attempts. Try again later.")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: DbDep, settings: SettingsDep) -> TokenOut:
    _throttle(request, settings)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValidationError(
            "An account with this email already exists.",
            fields={"email": "already registered"},
        ) from None
    db.refresh(user)
    # Register logs the user in directly; there is no benefit to making
    # someone log in again immediately after signing up.
    token = create_access_token(user.id, settings)
    return TokenOut(access_token=token, user=UserOut.model_validate(user, from_attributes=True))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: DbDep, settings: SettingsDep) -> TokenOut:
    _throttle(request, settings)
    user = db.exec(select(User).where(User.email == body.email.lower())).first()
    if user is None:
        burn_password_check(body.password)
        raise InvalidCredentialsError()
    if not verify_password(body.password, user.password_hash):
        raise InvalidCredentialsError()
    token = create_access_token(user.id, settings)
    return TokenOut(access_token=token, user=UserOut.model_validate(user, from_attributes=True))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)

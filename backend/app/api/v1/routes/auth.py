from datetime import datetime, timedelta, timezone
import logging
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.v1.dependencies.auth import (
    get_current_user,
    get_user_roles,
)
from app.core.config import Settings, get_settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.enums import RoleName
from app.models.role import Role
from app.models.school import School
from app.models.user import User
from app.schemas.auth import (
    AuthenticatedUserResponse,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_dummy_password_hash: str | None = None


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid identifier or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _safe_user(user: User, db: Session) -> AuthenticatedUserResponse:
    school = db.get(School, user.school_id) if user.school_id else None
    return AuthenticatedUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        username=user.username,
        school_id=user.school_id,
        school_name=school.name if school else None,
        roles=get_user_roles(db, user.id),
    )


def _token_response(
    user: User,
    auth_session: AuthSession,
    db: Session,
    settings: Settings,
) -> TokenResponse:
    access_token, _ = create_access_token(user.id, auth_session.id, settings)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=_safe_user(user, db),
    )


def _set_refresh_cookie(
    response: Response,
    token: str,
    settings: Settings,
    expires_at: datetime,
) -> None:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite.lower(),
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite.lower(),
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
    )


def _check_cookie_request_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origin_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin is not allowed.",
        )


def _login_rate_keys(
    request: Request,
    identifier: str,
    school_code: str | None,
    settings: Settings,
) -> tuple[tuple[str, int], ...]:
    remote_addr = request.client.host if request.client else "unknown"
    school = school_code.casefold() if school_code else ""
    identity_key = f"identity:{school}:{identifier.casefold()}"
    ip_key = f"ip:{remote_addr}"
    return (
        (identity_key, settings.login_rate_limit_attempts),
        (ip_key, settings.login_rate_limit_attempts * 5),
    )


def _dummy_hash() -> str:
    global _dummy_password_hash
    if _dummy_password_hash is None:
        _dummy_password_hash = hash_password(secrets.token_urlsafe(32))
    return _dummy_password_hash


def _find_login_user(
    db: Session,
    identifier: str,
    school_code: str | None,
) -> list[User]:
    identifier_match = or_(
        func.lower(User.username) == identifier.casefold(),
        func.lower(User.email) == identifier.casefold(),
    )
    statement = select(User).options(joinedload(User.school)).where(identifier_match)
    if school_code:
        statement = statement.join(User.school).where(
            func.lower(School.school_code) == school_code.casefold()
        )
    return list(db.execute(statement.limit(2)).unique().scalars())


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    rate_keys = _login_rate_keys(
        request,
        payload.identifier,
        payload.school_code,
        settings,
    )
    if any(
        login_rate_limiter.is_limited(
            key,
            limit,
            settings.login_rate_limit_window_seconds,
        )
        for key, limit in rate_keys
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        )

    users = _find_login_user(db, payload.identifier, payload.school_code)
    user = users[0] if len(users) == 1 else None
    valid_password = verify_password(
        payload.password,
        user.password_hash if user else _dummy_hash(),
    )
    roles = get_user_roles(db, user.id) if user else []
    if user is None or not valid_password or not user.is_active or not roles:
        for key, _ in rate_keys:
            login_rate_limiter.record_failure(
                key,
                settings.login_rate_limit_window_seconds,
            )
        raise _invalid_credentials()

    login_rate_limiter.clear(rate_keys[0][0])
    now = datetime.now(timezone.utc)
    refresh_token = create_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        session_family_id=uuid4(),
        refresh_token_hash=hash_refresh_token(refresh_token, settings),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        last_used_at=now,
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    _set_refresh_cookie(response, refresh_token, settings, auth_session.expires_at)
    return _token_response(user, auth_session, db, settings)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    _check_cookie_request_origin(request, settings)
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        _clear_refresh_cookie(response, settings)
        raise _invalid_credentials()

    token_hash = hash_refresh_token(raw_token, settings)
    auth_session = db.execute(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash)
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if auth_session is None:
        _clear_refresh_cookie(response, settings)
        raise _invalid_credentials()
    if auth_session.revoked_at is not None:
        db.execute(
            update(AuthSession)
            .where(AuthSession.session_family_id == auth_session.session_family_id)
            .where(AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        _clear_refresh_cookie(response, settings)
        raise _invalid_credentials()
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    user = db.get(User, auth_session.user_id)
    if expires_at <= now or user is None or not user.is_active:
        auth_session.revoked_at = now
        db.commit()
        _clear_refresh_cookie(response, settings)
        raise _invalid_credentials()

    raw_replacement = create_refresh_token()
    replacement = AuthSession(
        user_id=auth_session.user_id,
        session_family_id=auth_session.session_family_id,
        refresh_token_hash=hash_refresh_token(raw_replacement, settings),
        expires_at=expires_at,
        last_used_at=now,
    )
    db.add(replacement)
    db.flush()
    auth_session.revoked_at = now
    auth_session.last_used_at = now
    auth_session.replaced_by_session_id = replacement.id
    db.commit()
    db.refresh(replacement)
    _set_refresh_cookie(response, raw_replacement, settings, replacement.expires_at)
    return _token_response(user, replacement, db, settings)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    _check_cookie_request_origin(request, settings)
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        auth_session = db.execute(
            select(AuthSession)
            .where(
                AuthSession.refresh_token_hash
                == hash_refresh_token(raw_token, settings)
            )
            .with_for_update()
        ).scalar_one_or_none()
        if auth_session and auth_session.revoked_at is None:
            now = datetime.now(timezone.utc)
            db.execute(
                update(AuthSession)
                .where(AuthSession.session_family_id == auth_session.session_family_id)
                .where(AuthSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            db.commit()
    _clear_refresh_cookie(response, settings)
    return MessageResponse(message="Logged out.")


@router.get("/me", response_model=AuthenticatedUserResponse)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthenticatedUserResponse:
    return _safe_user(user, db)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a new password different from your current password.",
        )

    current_session_id: UUID = request.state.auth_session_id
    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id)
        .where(AuthSession.id != current_session_id)
        .where(AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    logger.info("Password changed for user_id=%s", user.id)
    return MessageResponse(message="Password changed.")

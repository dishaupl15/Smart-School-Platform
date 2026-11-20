from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import (
    get_current_user,
    require_admin,
    require_student,
    require_teacher,
)
from app.core.config import get_settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import (
    ACCESS_TOKEN_ALGORITHM,
    create_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.enums import RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User
from app.services.bootstrap_admin import create_initial_admin


def create_user(
    db_session: Session,
    *,
    role: RoleName = RoleName.STUDENT,
    username: str = "student-01",
    email: str = "student@example.test",
    password: str = "correct horse battery staple",
    active: bool = True,
) -> User:
    school = School(name="Authentication School", school_code=f"S-{uuid4().hex[:8]}")
    db_session.add(school)
    db_session.flush()
    user = User(
        school_id=school.id,
        full_name="Test Learner",
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_active=active,
    )
    role_row = db_session.query(Role).filter_by(name=role).one()
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role_row.id))
    db_session.commit()
    return user


def authenticate(
    client: TestClient,
    identifier: str = "student-01",
    password: str = "correct horse battery staple",
) -> tuple[dict, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    return body, body["access_token"]


def test_login_by_username_sets_httponly_cookie_and_returns_safe_profile(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "STUDENT-01", "password": "correct horse battery staple"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["roles"] == ["STUDENT"]
    assert "password_hash" not in response.json()["user"]
    assert "refresh_token" not in response.json()
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert get_settings().refresh_cookie_name in cookie_header
    assert response.json()["access_token"]
    assert db_session.query(AuthSession).count() == 1
    stored_hash = db_session.query(AuthSession).one().refresh_token_hash
    assert response.cookies[get_settings().refresh_cookie_name] not in stored_hash


def test_login_by_email_and_school_code(auth_client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    school = db_session.get(School, user.school_id)
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "identifier": user.email,
            "password": "correct horse battery staple",
            "school_code": school.school_code,
        },
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        ({"identifier": "student-01", "password": "wrong"}, 401),
        ({"identifier": "missing", "password": "wrong"}, 401),
        ({"identifier": "", "password": "wrong"}, 422),
        ({"identifier": "student-01"}, 422),
    ],
)
def test_login_rejects_bad_or_missing_credentials(
    auth_client: TestClient,
    db_session: Session,
    payload: dict,
    status_code: int,
) -> None:
    create_user(db_session)
    response = auth_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == status_code
    if status_code == 401:
        assert response.json()["detail"] == "Invalid identifier or password."


def test_inactive_users_cannot_login(auth_client: TestClient, db_session: Session) -> None:
    create_user(db_session, active=False)
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "student-01", "password": "correct horse battery staple"},
    )
    assert response.status_code == 401


def test_access_token_authenticates_me_endpoint(auth_client: TestClient, db_session: Session) -> None:
    create_user(db_session)
    body, access_token = authenticate(auth_client)

    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == body["user"]


@pytest.mark.parametrize("token_kind", ["malformed", "expired", "refresh"])
def test_me_rejects_malformed_expired_and_wrong_type_tokens(
    auth_client: TestClient,
    db_session: Session,
    token_kind: str,
) -> None:
    user = create_user(db_session)
    session_id = uuid4()
    db_session.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            session_family_id=uuid4(),
            refresh_token_hash=hash_refresh_token(uuid4().hex),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db_session.commit()
    settings = get_settings()
    if token_kind == "malformed":
        token = "not-a-jwt"
    else:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user.id),
            "sid": str(session_id),
            "typ": "refresh" if token_kind == "refresh" else "access",
            "iat": now,
            "exp": now - timedelta(minutes=1) if token_kind == "expired" else now + timedelta(minutes=1),
            "jti": uuid4().hex,
        }
        token = jwt.encode(
            claims,
            settings.jwt_secret_key.get_secret_value(),
            algorithm=ACCESS_TOKEN_ALGORITHM,
        )

    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_inactive_user_access_is_rejected(auth_client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    _, token = authenticate(auth_client)
    user.is_active = False
    db_session.commit()
    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_refresh_rotates_tokens_and_reuse_revokes_the_family(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session)
    _, access_token = authenticate(auth_client)
    cookie_name = get_settings().refresh_cookie_name
    original_refresh = auth_client.cookies.get(cookie_name)

    rotated = auth_client.post("/api/v1/auth/refresh")

    assert rotated.status_code == 200
    assert rotated.json()["access_token"] != access_token
    assert auth_client.cookies.get(cookie_name) != original_refresh
    sessions = db_session.query(AuthSession).order_by(AuthSession.created_at).all()
    assert len(sessions) == 2
    assert sessions[0].revoked_at is not None
    assert sessions[0].replaced_by_session_id == sessions[1].id
    family_id = sessions[0].session_family_id

    reused = auth_client.post(
        "/api/v1/auth/refresh",
        cookies={cookie_name: original_refresh},
    )
    assert reused.status_code == 401
    assert all(
        session.revoked_at is not None
        for session in db_session.query(AuthSession)
        .filter_by(session_family_id=family_id)
        .all()
    )


def test_logout_revokes_refresh_session_and_clears_cookie(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session)
    authenticate(auth_client)
    response = auth_client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.headers["set-cookie"].lower().find("max-age=0") >= 0
    assert db_session.query(AuthSession).one().revoked_at is not None
    assert auth_client.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_without_cookie_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_password_change_requires_current_password_and_revokes_other_sessions(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)
    _, first_access = authenticate(auth_client)
    _, first_access = authenticate(auth_client)
    sessions = db_session.query(AuthSession).all()
    assert len(sessions) == 2
    current_session = next(
        session
        for session in sessions
        if session.refresh_token_hash
        == hash_refresh_token(auth_client.cookies[get_settings().refresh_cookie_name])
    )

    invalid = auth_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {first_access}"},
        json={
            "current_password": "incorrect current password",
            "new_password": "a new strong password",
        },
    )
    assert invalid.status_code == 400

    changed = auth_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {first_access}"},
        json={
            "current_password": "correct horse battery staple",
            "new_password": "a new strong password",
        },
    )
    assert changed.status_code == 200
    db_session.refresh(user)
    db_session.refresh(current_session)
    assert verify_password("a new strong password", user.password_hash)
    assert current_session.revoked_at is None
    assert sum(session.revoked_at is not None for session in sessions) == 1
    assert auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {first_access}"},
    ).status_code == 200


def test_password_change_validates_password_length(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session)
    _, token = authenticate(auth_client)
    response = auth_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "anything", "new_password": "short"},
    )
    assert response.status_code == 422


def test_argon2id_password_hashing(auth_client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", user.password_hash)
    assert not verify_password("incorrect", user.password_hash)


def test_login_rate_limit_returns_429(auth_client: TestClient, db_session: Session) -> None:
    create_user(db_session)
    for _ in range(get_settings().login_rate_limit_attempts):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"identifier": "rate-test", "password": "incorrect"},
        )
        assert response.status_code == 401
    blocked = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "rate-test", "password": "incorrect"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]


def test_login_rate_limit_also_bounds_identifier_spraying(
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "login_rate_limit_attempts", 1)
    login_rate_limiter.clear("ip:testclient")

    for index in range(5):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"identifier": f"unknown-{index}", "password": "incorrect"},
        )
        assert response.status_code == 401

    blocked = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "another-unknown", "password": "incorrect"},
    )
    login_rate_limiter.clear("ip:testclient")
    assert blocked.status_code == 429


@pytest.mark.parametrize(
    ("role", "dependency"),
    [
        (RoleName.ADMIN, require_admin),
        (RoleName.TEACHER, require_teacher),
        (RoleName.STUDENT, require_student),
    ],
)
def test_role_dependencies_grant_assigned_role_only(
    auth_client: TestClient,
    db_session: Session,
    role: RoleName,
    dependency,
) -> None:
    user = create_user(db_session, role=role, username=f"user-{role.value.lower()}")
    path = f"/_test/role/{role.value.lower()}"
    auth_client.app.add_api_route(
        path,
        lambda current_user=Depends(dependency): {"user_id": str(current_user.id)},
        methods=["GET"],
    )
    _, token = authenticate(auth_client, f"user-{role.value.lower()}")
    assert auth_client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    other_path = f"/_test/not-{role.value.lower()}"
    missing_role = {
        RoleName.ADMIN: require_teacher,
        RoleName.TEACHER: require_student,
        RoleName.STUDENT: require_admin,
    }[role]
    auth_client.app.add_api_route(
        other_path,
        lambda current_user=Depends(missing_role): {"user_id": str(current_user.id)},
        methods=["GET"],
    )
    assert (
        auth_client.get(other_path, headers={"Authorization": f"Bearer {token}"}).status_code
        == 403
    )


def test_protected_route_returns_401_without_credentials(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session, role=RoleName.ADMIN)
    auth_client.app.add_api_route(
        "/_test/admin",
        lambda current_user=Depends(require_admin): {"id": str(current_user.id)},
        methods=["GET"],
    )
    assert auth_client.get("/_test/admin").status_code == 401


def test_bootstrap_admin_hashes_password_and_rejects_duplicate(
    db_session: Session,
) -> None:
    role = Role(name=RoleName.ADMIN)
    db_session.add(role)
    db_session.flush()
    admin = create_initial_admin(
        db_session,
        full_name="Initial Admin",
        email="admin@example.test",
        password="a safe administrator password",
    )
    assert admin.password_hash != "a safe administrator password"
    assert verify_password("a safe administrator password", admin.password_hash)
    assert db_session.query(UserRole).filter_by(user_id=admin.id, role_id=role.id).count() == 1
    with pytest.raises(ValueError, match="already uses"):
        create_initial_admin(
            db_session,
            full_name="Duplicate Admin",
            email="admin@example.test",
            password="another safe administrator password",
        )


def test_authentication_response_does_not_expose_sensitive_fields(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    create_user(db_session)
    body, token = authenticate(auth_client)
    assert "password_hash" not in body["user"]
    assert "refresh_token" not in body
    assert auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200

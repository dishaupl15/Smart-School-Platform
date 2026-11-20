from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


def create_initial_admin(
    db: Session,
    *,
    full_name: str,
    password: str,
    email: str | None = None,
    username: str | None = None,
    school_code: str | None = None,
) -> User:
    full_name = full_name.strip()
    email = email.strip().casefold() if email else None
    username = username.strip() if username else None
    if not full_name or not (email or username):
        raise ValueError("A name and email or username are required.")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must contain between 12 and 128 characters.")

    school = None
    if school_code:
        school = db.execute(
            select(School).where(func.lower(School.school_code) == school_code.casefold())
        ).scalar_one_or_none()
        if school is None:
            raise ValueError("The specified school code does not exist.")

    conditions = []
    if email:
        conditions.append(func.lower(User.email) == email)
    if username:
        conditions.append(func.lower(User.username) == username.casefold())
    duplicate_query = select(User).where(or_(*conditions))
    duplicate_query = duplicate_query.where(User.school_id == (school.id if school else None))
    if db.execute(duplicate_query).first():
        raise ValueError("An account already uses this identifier in the selected school.")

    admin_role = db.execute(
        select(Role).where(Role.name == RoleName.ADMIN)
    ).scalar_one_or_none()
    if admin_role is None:
        raise RuntimeError("The ADMIN role is missing; apply the database migrations first.")

    user = User(
        school_id=school.id if school else None,
        full_name=full_name,
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()
    db.refresh(user)
    return user

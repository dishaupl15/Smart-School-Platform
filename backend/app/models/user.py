from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("id", "school_id", name="uq_users_id_school"),
        UniqueConstraint("school_id", "email", name="uq_users_school_email"),
        UniqueConstraint("school_id", "username", name="uq_users_school_username"),
        Index(
            "uq_users_school_username_lower",
            "school_id",
            text("lower(username)"),
            unique=True,
            postgresql_where=text("school_id IS NOT NULL AND username IS NOT NULL"),
            sqlite_where=text("school_id IS NOT NULL AND username IS NOT NULL"),
        ),
        Index(
            "uq_users_school_email_lower",
            "school_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("school_id IS NOT NULL AND email IS NOT NULL"),
            sqlite_where=text("school_id IS NOT NULL AND email IS NOT NULL"),
        ),
    )

    school_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    school: Mapped["School | None"] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

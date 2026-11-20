from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class School(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (UniqueConstraint("school_code", name="uq_schools_school_code"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    school_code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list["User"]] = relationship(back_populates="school")
    academic_classes: Mapped[list["AcademicClass"]] = relationship(back_populates="school")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="school")

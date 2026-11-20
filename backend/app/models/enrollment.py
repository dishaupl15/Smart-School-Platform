from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class StudentEnrollment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "school_id"],
            ["users.id", "users.school_id"],
            name="fk_student_enrollments_student_school",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["class_id", "school_id", "academic_year"],
            ["academic_classes.id", "academic_classes.school_id", "academic_classes.academic_year"],
            name="fk_student_enrollments_class_school_year",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_student_enrollments_active_year",
            "student_id",
            "school_id",
            "academic_year",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
    )

    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TeacherAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["teacher_id", "school_id"],
            ["users.id", "users.school_id"],
            name="fk_teacher_assignments_teacher_school",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["class_id", "school_id", "academic_year"],
            ["academic_classes.id", "academic_classes.school_id", "academic_classes.academic_year"],
            name="fk_teacher_assignments_class_school_year",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["class_id", "subject_id"],
            ["class_subjects.class_id", "class_subjects.subject_id"],
            name="fk_teacher_assignments_class_subject",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("teacher_id", "class_id", "subject_id", "academic_year", name="uq_teacher_assignments_identity"),
    )

    teacher_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

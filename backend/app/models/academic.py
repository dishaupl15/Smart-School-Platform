from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin


class AcademicClass(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "academic_classes"
    __table_args__ = (
        UniqueConstraint("id", "school_id", name="uq_academic_classes_id_school"),
        UniqueConstraint(
            "school_id",
            "academic_year",
            "grade_number",
            "section",
            name="uq_academic_classes_identity",
        ),
        Index(
            "uq_academic_classes_identity_no_section",
            "school_id",
            "academic_year",
            "grade_number",
            unique=True,
            postgresql_where=text("section IS NULL"),
            sqlite_where=text("section IS NULL"),
        ),
        UniqueConstraint(
            "id",
            "school_id",
            "academic_year",
            name="uq_academic_classes_id_school_year",
        ),
        CheckConstraint("grade_number >= 1 AND grade_number <= 12", name="ck_academic_classes_grade"),
    )

    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade_number: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    school: Mapped["School"] = relationship(back_populates="academic_classes")
    class_subjects: Mapped[list["ClassSubject"]] = relationship(
        back_populates="academic_class",
        cascade="all, delete-orphan",
        foreign_keys="ClassSubject.class_id",
    )
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="academic_class")


class Subject(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("id", "school_id", name="uq_subjects_id_school"),
        UniqueConstraint("school_id", "code", name="uq_subjects_school_code"),
        UniqueConstraint("school_id", "name", name="uq_subjects_school_name"),
        Index(
            "uq_subjects_school_code_lower",
            "school_id",
            text("lower(code)"),
            unique=True,
        ),
        Index(
            "uq_subjects_school_name_lower",
            "school_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    school: Mapped["School"] = relationship(back_populates="subjects")
    class_subjects: Mapped[list["ClassSubject"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
        foreign_keys="ClassSubject.subject_id",
    )
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="subject")


class ClassSubject(UUIDMixin, Base):
    __tablename__ = "class_subjects"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subjects_class_subject"),
        ForeignKeyConstraint(
            ["class_id", "school_id"],
            ["academic_classes.id", "academic_classes.school_id"],
            name="fk_class_subjects_class_school",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["subject_id", "school_id"],
            ["subjects.id", "subjects.school_id"],
            name="fk_class_subjects_subject_school",
            ondelete="CASCADE",
        ),
    )

    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)

    academic_class: Mapped["AcademicClass"] = relationship(
        back_populates="class_subjects",
        foreign_keys=[class_id],
    )
    subject: Mapped["Subject"] = relationship(
        back_populates="class_subjects",
        foreign_keys=[subject_id],
    )


class Chapter(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "chapter_number", name="uq_chapters_class_subject_number"),
        UniqueConstraint("class_id", "subject_id", "title", name="uq_chapters_class_subject_title"),
        UniqueConstraint("id", "subject_id", name="uq_chapters_id_subject"),
        UniqueConstraint("id", "subject_id", "class_id", name="uq_chapters_id_subject_class"),
        ForeignKeyConstraint(
            ["class_id", "subject_id"],
            ["class_subjects.class_id", "class_subjects.subject_id"],
            name="fk_chapters_class_subject",
            ondelete="RESTRICT",
        ),
        CheckConstraint("chapter_number >= 1", name="ck_chapters_number"),
    )

    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subject: Mapped["Subject"] = relationship(back_populates="chapters")
    academic_class: Mapped["AcademicClass"] = relationship(back_populates="chapters")

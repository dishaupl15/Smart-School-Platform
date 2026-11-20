from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
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
from app.models.enums import LanguageCode, QuestionDifficulty, QuestionStatus, QuestionType


class Question(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chapter_id", "subject_id"],
            ["chapters.id", "chapters.subject_id"],
            name="fk_questions_chapter_subject",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["subject_id", "school_id"],
            ["subjects.id", "subjects.school_id"],
            name="fk_questions_subject_school",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by", "school_id"],
            ["users.id", "users.school_id"],
            name="fk_questions_created_by_school",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["updated_by", "school_id"],
            ["users.id", "users.school_id"],
            name="fk_questions_updated_by_school",
            ondelete="RESTRICT",
        ),
        Index("ix_questions_school_status", "school_id", "status"),
        Index("ix_questions_subject_chapter", "subject_id", "chapter_id"),
        Index("ix_questions_created_at", "created_at"),
        UniqueConstraint("id", "subject_id", "chapter_id", name="uq_questions_id_subject_chapter"),
    )

    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type", native_enum=True, create_constraint=True), nullable=False, default=QuestionType.SINGLE_CHOICE)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(Enum(QuestionDifficulty, name="question_difficulty", native_enum=True, create_constraint=True), nullable=False)
    status: Mapped[QuestionStatus] = mapped_column(Enum(QuestionStatus, name="question_status", native_enum=True, create_constraint=True), nullable=False, default=QuestionStatus.DRAFT)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)

    translations: Mapped[list["QuestionTranslation"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionTranslation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "question_translations"
    __table_args__ = (
        UniqueConstraint("question_id", "language_code", name="uq_question_translations_question_language"),
        Index("ix_question_translations_language", "language_code"),
    )

    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    language_code: Mapped[LanguageCode] = mapped_column(Enum(LanguageCode, name="language_code", native_enum=True, create_constraint=True), nullable=False)
    question_text: Mapped[str] = mapped_column(String(), nullable=False)
    explanation: Mapped[str | None] = mapped_column(String(), nullable=True)

    question: Mapped["Question"] = relationship(back_populates="translations")


class QuestionOption(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "option_key", name="uq_question_options_question_key"),
        UniqueConstraint("question_id", "display_order", name="uq_question_options_question_order"),
        UniqueConstraint("id", "question_id", name="uq_question_options_id_question"),
        CheckConstraint("display_order >= 1", name="ck_question_options_order"),
        Index("ix_question_options_question_correct", "question_id", "is_correct"),
        Index(
            "uq_question_options_single_correct",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct"),
            sqlite_where=text("is_correct"),
        ),
    )

    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_key: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")
    translations: Mapped[list["OptionTranslation"]] = relationship(back_populates="option", cascade="all, delete-orphan")


class OptionTranslation(UUIDMixin, Base):
    __tablename__ = "option_translations"
    __table_args__ = (
        UniqueConstraint("option_id", "language_code", name="uq_option_translations_option_language"),
    )

    option_id: Mapped[UUID] = mapped_column(ForeignKey("question_options.id", ondelete="CASCADE"), nullable=False, index=True)
    language_code: Mapped[LanguageCode] = mapped_column(Enum(LanguageCode, name="language_code", native_enum=True, create_constraint=True), nullable=False)
    option_text: Mapped[str] = mapped_column(String(), nullable=False)

    option: Mapped["QuestionOption"] = relationship(back_populates="translations")

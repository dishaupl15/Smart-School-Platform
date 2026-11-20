from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDMixin
from app.models.enums import AttemptStatus, LanguageCode


class Quiz(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chapter_id", "subject_id", "class_id"],
            ["chapters.id", "chapters.subject_id", "chapters.class_id"],
            name="fk_quizzes_academic_context",
            ondelete="RESTRICT",
        ),
        CheckConstraint("total_questions >= 1", name="ck_quizzes_total_questions"),
        UniqueConstraint(
            "id",
            "class_id",
            "subject_id",
            "chapter_id",
            name="uq_quizzes_id_context",
        ),
        Index("ix_quizzes_context", "class_id", "subject_id", "chapter_id"),
    )

    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        foreign_keys="QuizQuestion.quiz_id",
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz",
        foreign_keys="QuizAttempt.quiz_id",
    )


class QuizQuestion(UUIDMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "question_id", name="uq_quiz_questions_quiz_question"),
        UniqueConstraint("quiz_id", "display_order", name="uq_quiz_questions_quiz_order"),
        ForeignKeyConstraint(
            ["quiz_id", "class_id", "subject_id", "chapter_id"],
            ["quizzes.id", "quizzes.class_id", "quizzes.subject_id", "quizzes.chapter_id"],
            name="fk_quiz_questions_quiz_context",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["question_id", "subject_id", "chapter_id"],
            ["questions.id", "questions.subject_id", "questions.chapter_id"],
            name="fk_quiz_questions_question_context",
            ondelete="RESTRICT",
        ),
        CheckConstraint("display_order >= 1", name="ck_quiz_questions_order"),
    )

    quiz_id: Mapped[UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True)
    class_id: Mapped[UUID] = mapped_column(nullable=False)
    subject_id: Mapped[UUID] = mapped_column(nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    quiz: Mapped["Quiz"] = relationship(
        back_populates="quiz_questions",
        foreign_keys=[quiz_id],
    )


class QuizAttempt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("student_id", "quiz_id", "attempt_number", name="uq_quiz_attempts_student_quiz_number"),
        CheckConstraint("attempt_number >= 1", name="ck_quiz_attempts_number"),
        CheckConstraint("correct_answers >= 0 AND incorrect_answers >= 0 AND unanswered_questions >= 0", name="ck_quiz_attempts_counts"),
        CheckConstraint(
            "total_questions >= 0",
            name="ck_quiz_attempts_total",
        ),
        CheckConstraint(
            "correct_answers + incorrect_answers + unanswered_questions = total_questions",
            name="ck_quiz_attempts_count_total",
        ),
        CheckConstraint("score = correct_answers", name="ck_quiz_attempts_score_correct"),
        CheckConstraint("score >= 0", name="ck_quiz_attempts_score"),
        CheckConstraint("score <= total_questions", name="ck_quiz_attempts_score_total"),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_quiz_attempts_percentage"),
        CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status != 'COMPLETED' AND completed_at IS NULL)",
            name="ck_quiz_attempts_completion",
        ),
        CheckConstraint(
            "(total_questions = 0 AND percentage = 0) OR "
            "(total_questions > 0 AND percentage BETWEEN "
            "(100.0 * score / total_questions - 0.005) AND "
            "(100.0 * score / total_questions + 0.005))",
            name="ck_quiz_attempts_percentage_matches_score",
        ),
        UniqueConstraint(
            "id",
            "class_id",
            "subject_id",
            "chapter_id",
            name="uq_quiz_attempts_id_context",
        ),
        ForeignKeyConstraint(
            ["quiz_id", "class_id", "subject_id", "chapter_id"],
            ["quizzes.id", "quizzes.class_id", "quizzes.subject_id", "quizzes.chapter_id"],
            name="fk_quiz_attempts_quiz_context",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["student_id", "school_id"],
            ["users.id", "users.school_id"],
            name="fk_quiz_attempts_student_school",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["class_id", "school_id"],
            ["academic_classes.id", "academic_classes.school_id"],
            name="fk_quiz_attempts_class_school",
            ondelete="RESTRICT",
        ),
        Index("ix_quiz_attempts_student_started", "student_id", "started_at"),
        Index("ix_quiz_attempts_status_started", "status", "started_at"),
        Index("ix_quiz_attempts_subject_chapter", "subject_id", "chapter_id"),
    )

    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    school_id: Mapped[UUID] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    quiz_id: Mapped[UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False, index=True)
    class_id: Mapped[UUID] = mapped_column(ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus, name="attempt_status", native_enum=True, create_constraint=True), nullable=False, default=AttemptStatus.IN_PROGRESS)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incorrect_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unanswered_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))

    quiz: Mapped["Quiz"] = relationship(
        back_populates="attempts",
        foreign_keys=[quiz_id],
    )
    attempt_questions: Mapped[list["AttemptQuestion"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        foreign_keys="AttemptQuestion.attempt_id",
    )


class AttemptQuestion(UUIDMixin, Base):
    __tablename__ = "attempt_questions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_questions_attempt_question"),
        UniqueConstraint("attempt_id", "display_order", name="uq_attempt_questions_attempt_order"),
        UniqueConstraint("id", "question_id", name="uq_attempt_questions_id_question"),
        UniqueConstraint("id", "attempt_id", name="uq_attempt_questions_id_attempt"),
        ForeignKeyConstraint(
            ["attempt_id", "class_id", "subject_id", "chapter_id"],
            ["quiz_attempts.id", "quiz_attempts.class_id", "quiz_attempts.subject_id", "quiz_attempts.chapter_id"],
            name="fk_attempt_questions_attempt_context",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["question_id", "subject_id", "chapter_id"],
            ["questions.id", "questions.subject_id", "questions.chapter_id"],
            name="fk_attempt_questions_question_context",
            ondelete="RESTRICT",
        ),
        CheckConstraint("display_order >= 1", name="ck_attempt_questions_order"),
        Index("ix_attempt_questions_question", "question_id"),
    )

    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    class_id: Mapped[UUID] = mapped_column(nullable=False)
    subject_id: Mapped[UUID] = mapped_column(nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    question_translation_id: Mapped[UUID | None] = mapped_column(ForeignKey("question_translations.id", ondelete="SET NULL"), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_language: Mapped[LanguageCode] = mapped_column(Enum(LanguageCode, name="language_code", native_enum=True, create_constraint=True), nullable=False)
    question_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    option_order_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    question_text_snapshot: Mapped[str] = mapped_column(String(), nullable=False)

    attempt: Mapped["QuizAttempt"] = relationship(
        back_populates="attempt_questions",
        foreign_keys="AttemptQuestion.attempt_id",
    )
    answers: Mapped[list["StudentAnswer"]] = relationship(
        back_populates="attempt_question",
        cascade="all, delete-orphan",
        foreign_keys="StudentAnswer.attempt_question_id",
    )


class StudentAnswer(UUIDMixin, Base):
    __tablename__ = "student_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_question_id", "question_id"],
            ["attempt_questions.id", "attempt_questions.question_id"],
            name="fk_student_answers_attempt_question",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["selected_option_id", "question_id"],
            ["question_options.id", "question_options.question_id"],
            name="fk_student_answers_option_question",
            ondelete="RESTRICT",
        ),
    )

    attempt_question_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)
    question_id: Mapped[UUID] = mapped_column(nullable=False)
    selected_option_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    attempt_question: Mapped["AttemptQuestion"] = relationship(
        back_populates="answers",
        foreign_keys="StudentAnswer.attempt_question_id",
    )

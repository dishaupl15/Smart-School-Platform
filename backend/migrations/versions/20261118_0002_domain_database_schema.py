"""Add the initial modular school learning database schema.

Revision ID: 20261118_0002
Revises: 20261118_0001
Create Date: 2026-11-18
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20261118_0002"
down_revision = "20261118_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role_name = sa.Enum("ADMIN", "TEACHER", "STUDENT", name="role_name", create_constraint=True)
    question_type = sa.Enum("SINGLE_CHOICE", name="question_type", create_constraint=True)
    question_difficulty = sa.Enum("EASY", "MEDIUM", "HARD", name="question_difficulty", create_constraint=True)
    question_status = sa.Enum("DRAFT", "REVIEW", "APPROVED", "ARCHIVED", name="question_status", create_constraint=True)
    language_code = sa.Enum("en", "hi", "mr", name="language_code", create_constraint=True)
    attempt_status = sa.Enum("IN_PROGRESS", "COMPLETED", "ABANDONED", name="attempt_status", create_constraint=True)

    role_name.create(op.get_bind(), checkfirst=True)
    question_type.create(op.get_bind(), checkfirst=True)
    question_difficulty.create(op.get_bind(), checkfirst=True)
    question_status.create(op.get_bind(), checkfirst=True)
    language_code.create(op.get_bind(), checkfirst=True)
    attempt_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "schools",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("school_code", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("school_code", name="uq_schools_school_code"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("school_id", "email", name="uq_users_school_email"),
        sa.UniqueConstraint("school_id", "username", name="uq_users_school_username"),
    )
    op.create_index("ix_users_school_id", "users", ["school_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", role_name, nullable=False, unique=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Uuid(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    op.create_table(
        "academic_classes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("grade_number", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("section", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("school_id", "academic_year", "grade_number", "section", name="uq_academic_classes_identity"),
        sa.CheckConstraint("grade_number >= 1 AND grade_number <= 12", name="ck_academic_classes_grade"),
    )
    op.create_index("ix_academic_classes_school_id", "academic_classes", ["school_id"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("school_id", "code", name="uq_subjects_school_code"),
        sa.UniqueConstraint("school_id", "name", name="uq_subjects_school_name"),
    )
    op.create_index("ix_subjects_school_id", "subjects", ["school_id"])

    op.create_table(
        "class_subjects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("class_id", "subject_id", name="uq_class_subjects_class_subject"),
    )
    op.create_index("ix_class_subjects_class_id", "class_subjects", ["class_id"])
    op.create_index("ix_class_subjects_subject_id", "class_subjects", ["subject_id"])

    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("class_id", "subject_id", "chapter_number", name="uq_chapters_class_subject_number"),
        sa.UniqueConstraint("class_id", "subject_id", "title", name="uq_chapters_class_subject_title"),
        sa.CheckConstraint("chapter_number >= 1", name="ck_chapters_number"),
    )
    op.create_index("ix_chapters_subject_id", "chapters", ["subject_id"])
    op.create_index("ix_chapters_class_id", "chapters", ["class_id"])

    op.create_table(
        "student_enrollments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "class_id", "academic_year", name="uq_student_enrollments_identity"),
        sa.CheckConstraint("student_id IS NOT NULL", name="ck_student_enrollments_student"),
    )
    op.create_index("ix_student_enrollments_student_id", "student_enrollments", ["student_id"])
    op.create_index("ix_student_enrollments_class_id", "student_enrollments", ["class_id"])
    op.create_index("ix_student_enrollments_school_id", "student_enrollments", ["school_id"])

    op.create_table(
        "teacher_assignments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("teacher_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("teacher_id", "class_id", "subject_id", "academic_year", name="uq_teacher_assignments_identity"),
    )
    op.create_index("ix_teacher_assignments_teacher_id", "teacher_assignments", ["teacher_id"])
    op.create_index("ix_teacher_assignments_class_id", "teacher_assignments", ["class_id"])
    op.create_index("ix_teacher_assignments_subject_id", "teacher_assignments", ["subject_id"])
    op.create_index("ix_teacher_assignments_school_id", "teacher_assignments", ["school_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_id", sa.Uuid(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_type", question_type, nullable=False),
        sa.Column("difficulty", question_difficulty, nullable=False),
        sa.Column("status", question_status, nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_questions_school_id", "questions", ["school_id"])
    op.create_index("ix_questions_subject_id", "questions", ["subject_id"])
    op.create_index("ix_questions_chapter_id", "questions", ["chapter_id"])
    op.create_index("ix_questions_school_status", "questions", ["school_id", "status"])
    op.create_index("ix_questions_subject_chapter", "questions", ["subject_id", "chapter_id"])
    op.create_index("ix_questions_created_at", "questions", ["created_at"])

    op.create_table(
        "question_translations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("question_id", sa.Uuid(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_code", language_code, nullable=False),
        sa.Column("question_text", sa.String(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("question_id", "language_code", name="uq_question_translations_question_language"),
    )
    op.create_index("ix_question_translations_question_id", "question_translations", ["question_id"])
    op.create_index("ix_question_translations_language", "question_translations", ["language_code"])

    op.create_table(
        "question_options",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("question_id", sa.Uuid(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_key", sa.String(20), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("question_id", "option_key", name="uq_question_options_question_key"),
        sa.UniqueConstraint("question_id", "display_order", name="uq_question_options_question_order"),
    )
    op.create_index("ix_question_options_question_id", "question_options", ["question_id"])
    op.create_index("ix_question_options_question_correct", "question_options", ["question_id", "is_correct"])

    op.create_table(
        "option_translations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("option_id", sa.Uuid(as_uuid=True), sa.ForeignKey("question_options.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_code", language_code, nullable=False),
        sa.Column("option_text", sa.String(), nullable=False),
        sa.UniqueConstraint("option_id", "language_code", name="uq_option_translations_option_language"),
    )
    op.create_index("ix_option_translations_option_id", "option_translations", ["option_id"])

    op.create_table(
        "quizzes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_id", sa.Uuid(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total_questions >= 1", name="ck_quizzes_total_questions"),
    )
    op.create_index("ix_quizzes_context", "quizzes", ["class_id", "subject_id", "chapter_id"])
    op.create_index("ix_quizzes_class_id", "quizzes", ["class_id"])
    op.create_index("ix_quizzes_subject_id", "quizzes", ["subject_id"])
    op.create_index("ix_quizzes_chapter_id", "quizzes", ["chapter_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("quiz_id", sa.Uuid(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(as_uuid=True), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("quiz_id", "question_id", name="uq_quiz_questions_quiz_question"),
        sa.UniqueConstraint("quiz_id", "display_order", name="uq_quiz_questions_quiz_order"),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])
    op.create_index("ix_quiz_questions_question_id", "quiz_questions", ["question_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quiz_id", sa.Uuid(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("class_id", sa.Uuid(as_uuid=True), sa.ForeignKey("academic_classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject_id", sa.Uuid(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_id", sa.Uuid(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", attempt_status, nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_answers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incorrect_answers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unanswered_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "quiz_id", "attempt_number", name="uq_quiz_attempts_student_quiz_number"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_quiz_attempts_number"),
        sa.CheckConstraint("correct_answers >= 0 AND incorrect_answers >= 0 AND unanswered_questions >= 0", name="ck_quiz_attempts_counts"),
        sa.CheckConstraint("score >= 0", name="ck_quiz_attempts_score"),
        sa.CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_quiz_attempts_percentage"),
    )
    op.create_index("ix_quiz_attempts_student_id", "quiz_attempts", ["student_id"])
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])
    op.create_index("ix_quiz_attempts_student_started", "quiz_attempts", ["student_id", "started_at"])
    op.create_index("ix_quiz_attempts_status_started", "quiz_attempts", ["status", "started_at"])
    op.create_index("ix_quiz_attempts_subject_chapter", "quiz_attempts", ["subject_id", "chapter_id"])

    op.create_table(
        "attempt_questions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("attempt_id", sa.Uuid(as_uuid=True), sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(as_uuid=True), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_translation_id", sa.Uuid(as_uuid=True), sa.ForeignKey("question_translations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("selected_language", language_code, nullable=False),
        sa.Column("question_snapshot", sa.JSON(), nullable=True),
        sa.Column("option_order_snapshot", sa.JSON(), nullable=True),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_questions_attempt_question"),
        sa.UniqueConstraint("attempt_id", "display_order", name="uq_attempt_questions_attempt_order"),
    )
    op.create_index("ix_attempt_questions_attempt_id", "attempt_questions", ["attempt_id"])
    op.create_index("ix_attempt_questions_question", "attempt_questions", ["question_id"])

    op.create_table(
        "student_answers",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("attempt_question_id", sa.Uuid(as_uuid=True), sa.ForeignKey("attempt_questions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("selected_option_id", sa.Uuid(as_uuid=True), sa.ForeignKey("question_options.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_student_answers_attempt_question_id", "student_answers", ["attempt_question_id"])
    op.create_index("ix_student_answers_selected_option_id", "student_answers", ["selected_option_id"])

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.Uuid(as_uuid=True)),
            sa.column("name", role_name),
        ),
        [
            {"id": uuid4(), "name": "ADMIN"},
            {"id": uuid4(), "name": "TEACHER"},
            {"id": uuid4(), "name": "STUDENT"},
        ],
    )


def downgrade() -> None:
    for table in (
        "student_answers",
        "attempt_questions",
        "quiz_attempts",
        "quiz_questions",
        "quizzes",
        "option_translations",
        "question_options",
        "question_translations",
        "questions",
        "teacher_assignments",
        "student_enrollments",
        "chapters",
        "class_subjects",
        "subjects",
        "academic_classes",
        "user_roles",
        "roles",
        "users",
        "schools",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for enum_type in (
        sa.Enum(name="attempt_status"),
        sa.Enum(name="language_code"),
        sa.Enum(name="question_status"),
        sa.Enum(name="question_difficulty"),
        sa.Enum(name="question_type"),
        sa.Enum(name="role_name"),
    ):
        enum_type.drop(bind, checkfirst=True)

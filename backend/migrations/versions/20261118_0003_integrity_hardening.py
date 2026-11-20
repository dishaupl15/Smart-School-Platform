"""Harden enrollment, snapshot, answer, and score integrity.

Revision ID: 20261118_0003
Revises: 20261118_0002
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0003"
down_revision = "20261118_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_academic_classes_id_school",
        "academic_classes",
        ["id", "school_id"],
    )
    op.create_unique_constraint(
        "uq_subjects_id_school",
        "subjects",
        ["id", "school_id"],
    )
    op.create_unique_constraint(
        "uq_chapters_id_subject",
        "chapters",
        ["id", "subject_id"],
    )
    op.create_unique_constraint(
        "uq_chapters_id_subject_class",
        "chapters",
        ["id", "subject_id", "class_id"],
    )
    op.create_foreign_key(
        "fk_questions_chapter_subject",
        "questions",
        "chapters",
        ["chapter_id", "subject_id"],
        ["id", "subject_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_quizzes_academic_context",
        "quizzes",
        "chapters",
        ["chapter_id", "subject_id", "class_id"],
        ["id", "subject_id", "class_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_student_enrollments_active_year",
        "student_enrollments",
        ["student_id", "school_id", "academic_year"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )

    op.add_column(
        "attempt_questions",
        sa.Column("question_text_snapshot", sa.String(), nullable=False, server_default=""),
    )
    op.alter_column("attempt_questions", "question_snapshot", existing_type=sa.JSON(), nullable=False)
    op.alter_column("attempt_questions", "option_order_snapshot", existing_type=sa.JSON(), nullable=False)

    op.add_column(
        "student_answers",
        sa.Column("question_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE student_answers
        SET question_id = (
            SELECT attempt_questions.question_id
            FROM attempt_questions
            WHERE attempt_questions.id = student_answers.attempt_question_id
        )
        """
    )
    op.alter_column(
        "student_answers",
        "question_id",
        existing_type=sa.Uuid(as_uuid=True),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_attempt_questions_id_question",
        "attempt_questions",
        ["id", "question_id"],
    )
    op.create_foreign_key(
        "fk_student_answers_attempt_question",
        "student_answers",
        "attempt_questions",
        ["attempt_question_id", "question_id"],
        ["id", "question_id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        "uq_question_options_id_question",
        "question_options",
        ["id", "question_id"],
    )
    op.create_foreign_key(
        "fk_student_answers_option_question",
        "student_answers",
        "question_options",
        ["selected_option_id", "question_id"],
        ["id", "question_id"],
        ondelete="RESTRICT",
    )

    op.create_check_constraint(
        "ck_quiz_attempts_total",
        "quiz_attempts",
        "total_questions >= 0",
    )
    op.create_check_constraint(
        "ck_quiz_attempts_count_total",
        "quiz_attempts",
        "correct_answers + incorrect_answers + unanswered_questions = total_questions",
    )
    op.create_check_constraint(
        "ck_quiz_attempts_completed",
        "quiz_attempts",
        "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR (status != 'COMPLETED')",
    )
    op.create_check_constraint(
        "ck_quiz_attempts_score_total",
        "quiz_attempts",
        "score <= total_questions",
    )


def downgrade() -> None:
    op.drop_constraint("fk_quizzes_academic_context", "quizzes", type_="foreignkey")
    op.drop_constraint("fk_questions_chapter_subject", "questions", type_="foreignkey")
    op.drop_constraint("uq_chapters_id_subject_class", "chapters", type_="unique")
    op.drop_constraint("uq_chapters_id_subject", "chapters", type_="unique")
    op.drop_constraint("uq_subjects_id_school", "subjects", type_="unique")
    op.drop_constraint("uq_academic_classes_id_school", "academic_classes", type_="unique")
    op.drop_constraint("ck_quiz_attempts_score_total", "quiz_attempts", type_="check")
    op.drop_constraint("ck_quiz_attempts_completed", "quiz_attempts", type_="check")
    op.drop_constraint("ck_quiz_attempts_count_total", "quiz_attempts", type_="check")
    op.drop_constraint("ck_quiz_attempts_total", "quiz_attempts", type_="check")
    op.drop_constraint("fk_student_answers_option_question", "student_answers", type_="foreignkey")
    op.drop_constraint("uq_question_options_id_question", "question_options", type_="unique")
    op.drop_constraint("fk_student_answers_attempt_question", "student_answers", type_="foreignkey")
    op.drop_constraint("uq_attempt_questions_id_question", "attempt_questions", type_="unique")
    op.drop_column("student_answers", "question_id")
    op.alter_column("attempt_questions", "option_order_snapshot", existing_type=sa.JSON(), nullable=True)
    op.alter_column("attempt_questions", "question_snapshot", existing_type=sa.JSON(), nullable=True)
    op.drop_column("attempt_questions", "question_text_snapshot")
    op.drop_index("uq_student_enrollments_active_year", table_name="student_enrollments")

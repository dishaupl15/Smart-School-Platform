"""Enforce school and assessment context across related records.

Revision ID: 20261118_0004
Revises: 20261118_0003
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0004"
down_revision = "20261118_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "student_answers_attempt_question_id_fkey",
        "student_answers",
        type_="foreignkey",
    )
    op.drop_constraint(
        "student_answers_selected_option_id_fkey",
        "student_answers",
        type_="foreignkey",
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
        server_default=None,
    )
    op.drop_constraint(
        "fk_student_answers_option_question",
        "student_answers",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_student_answers_option_question",
        "student_answers",
        "question_options",
        ["selected_option_id", "question_id"],
        ["id", "question_id"],
        ondelete="RESTRICT",
    )

    op.create_unique_constraint("uq_users_id_school", "users", ["id", "school_id"])
    op.create_foreign_key(
        "fk_student_enrollments_student_school",
        "student_enrollments",
        "users",
        ["student_id", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "ck_student_enrollments_student",
        "student_enrollments",
        type_="check",
    )
    op.create_foreign_key(
        "fk_teacher_assignments_teacher_school",
        "teacher_assignments",
        "users",
        ["teacher_id", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_question_options_order",
        "question_options",
        "display_order >= 1",
    )
    op.create_index(
        "uq_question_options_single_correct",
        "question_options",
        ["question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct"),
        sqlite_where=sa.text("is_correct"),
    )

    op.add_column(
        "class_subjects",
        sa.Column("school_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE class_subjects
        SET school_id = (
            SELECT academic_classes.school_id
            FROM academic_classes
            WHERE academic_classes.id = class_subjects.class_id
        )
        """
    )
    op.alter_column("class_subjects", "school_id", nullable=False)
    op.create_index("ix_class_subjects_school_id", "class_subjects", ["school_id"])
    op.create_foreign_key(
        "class_subjects_school_id_fkey",
        "class_subjects",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_class_subjects_class_school",
        "class_subjects",
        "academic_classes",
        ["class_id", "school_id"],
        ["id", "school_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_class_subjects_subject_school",
        "class_subjects",
        "subjects",
        ["subject_id", "school_id"],
        ["id", "school_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_chapters_class_subject",
        "chapters",
        "class_subjects",
        ["class_id", "subject_id"],
        ["class_id", "subject_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_academic_classes_id_school_year",
        "academic_classes",
        ["id", "school_id", "academic_year"],
    )
    op.create_foreign_key(
        "fk_student_enrollments_class_school_year",
        "student_enrollments",
        "academic_classes",
        ["class_id", "school_id", "academic_year"],
        ["id", "school_id", "academic_year"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_teacher_assignments_class_school_year",
        "teacher_assignments",
        "academic_classes",
        ["class_id", "school_id", "academic_year"],
        ["id", "school_id", "academic_year"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_teacher_assignments_class_subject",
        "teacher_assignments",
        "class_subjects",
        ["class_id", "subject_id"],
        ["class_id", "subject_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "teacher_assignments_class_id_fkey",
        "teacher_assignments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "teacher_assignments_class_id_fkey",
        "teacher_assignments",
        "academic_classes",
        ["class_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "teacher_assignments_subject_id_fkey",
        "teacher_assignments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "teacher_assignments_subject_id_fkey",
        "teacher_assignments",
        "subjects",
        ["subject_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE questions
        SET school_id = (
            SELECT subjects.school_id
            FROM subjects
            WHERE subjects.id = questions.subject_id
        )
        WHERE school_id IS NULL
        """
    )
    op.alter_column("questions", "school_id", nullable=False)
    op.drop_constraint("questions_school_id_fkey", "questions", type_="foreignkey")
    op.create_foreign_key(
        "questions_school_id_fkey",
        "questions",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "questions_created_by_fkey",
        "questions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_created_by_fkey",
        "questions",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "questions_updated_by_fkey",
        "questions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "questions_updated_by_fkey",
        "questions",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_questions_subject_school",
        "questions",
        "subjects",
        ["subject_id", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_questions_created_by_school",
        "questions",
        "users",
        ["created_by", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_questions_updated_by_school",
        "questions",
        "users",
        ["updated_by", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )

    op.create_unique_constraint(
        "uq_questions_id_subject_chapter",
        "questions",
        ["id", "subject_id", "chapter_id"],
    )
    op.create_unique_constraint(
        "uq_quizzes_id_context",
        "quizzes",
        ["id", "class_id", "subject_id", "chapter_id"],
    )
    for column in ("class_id", "subject_id", "chapter_id"):
        op.add_column("quiz_questions", sa.Column(column, sa.Uuid(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE quiz_questions
        SET class_id = quizzes.class_id,
            subject_id = quizzes.subject_id,
            chapter_id = quizzes.chapter_id
        FROM quizzes
        WHERE quizzes.id = quiz_questions.quiz_id
        """
    )
    for column in ("class_id", "subject_id", "chapter_id"):
        op.alter_column("quiz_questions", column, nullable=False)
    op.create_foreign_key(
        "fk_quiz_questions_quiz_context",
        "quiz_questions",
        "quizzes",
        ["quiz_id", "class_id", "subject_id", "chapter_id"],
        ["id", "class_id", "subject_id", "chapter_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_quiz_questions_question_context",
        "quiz_questions",
        "questions",
        ["question_id", "subject_id", "chapter_id"],
        ["id", "subject_id", "chapter_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_quiz_questions_order",
        "quiz_questions",
        "display_order >= 1",
    )

    op.add_column(
        "quiz_attempts",
        sa.Column("school_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE quiz_attempts
        SET school_id = (
            SELECT academic_classes.school_id
            FROM academic_classes
            WHERE academic_classes.id = quiz_attempts.class_id
        )
        """
    )
    op.alter_column("quiz_attempts", "school_id", nullable=False)
    op.create_index("ix_quiz_attempts_school_id", "quiz_attempts", ["school_id"])
    op.create_unique_constraint(
        "uq_quiz_attempts_id_context",
        "quiz_attempts",
        ["id", "class_id", "subject_id", "chapter_id"],
    )
    op.create_foreign_key(
        "fk_quiz_attempts_quiz_context",
        "quiz_attempts",
        "quizzes",
        ["quiz_id", "class_id", "subject_id", "chapter_id"],
        ["id", "class_id", "subject_id", "chapter_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_quiz_attempts_student_school",
        "quiz_attempts",
        "users",
        ["student_id", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_quiz_attempts_class_school",
        "quiz_attempts",
        "academic_classes",
        ["class_id", "school_id"],
        ["id", "school_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "quiz_attempts_school_id_fkey",
        "quiz_attempts",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for column in ("class_id", "subject_id", "chapter_id"):
        op.add_column("attempt_questions", sa.Column(column, sa.Uuid(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE attempt_questions
        SET class_id = quiz_attempts.class_id,
            subject_id = quiz_attempts.subject_id,
            chapter_id = quiz_attempts.chapter_id
        FROM quiz_attempts
        WHERE quiz_attempts.id = attempt_questions.attempt_id
        """
    )
    for column in ("class_id", "subject_id", "chapter_id"):
        op.alter_column("attempt_questions", column, nullable=False)
    op.create_foreign_key(
        "fk_attempt_questions_attempt_context",
        "attempt_questions",
        "quiz_attempts",
        ["attempt_id", "class_id", "subject_id", "chapter_id"],
        ["id", "class_id", "subject_id", "chapter_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_attempt_questions_question_context",
        "attempt_questions",
        "questions",
        ["question_id", "subject_id", "chapter_id"],
        ["id", "subject_id", "chapter_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_attempt_questions_order",
        "attempt_questions",
        "display_order >= 1",
    )

    op.drop_constraint("ck_quiz_attempts_completed", "quiz_attempts", type_="check")
    op.create_check_constraint(
        "ck_quiz_attempts_completion",
        "quiz_attempts",
        "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
        "(status != 'COMPLETED' AND completed_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_quiz_attempts_score_correct",
        "quiz_attempts",
        "score = correct_answers",
    )
    op.create_check_constraint(
        "ck_quiz_attempts_percentage_matches_score",
        "quiz_attempts",
        "(total_questions = 0 AND percentage = 0) OR "
        "(total_questions > 0 AND percentage BETWEEN "
        "(100.0 * score / total_questions - 0.005) AND "
        "(100.0 * score / total_questions + 0.005))",
    )
    op.alter_column(
        "attempt_questions",
        "question_text_snapshot",
        existing_type=sa.String(),
        server_default=None,
    )
    op.execute(
        """
        UPDATE attempt_questions
        SET question_text_snapshot = question_translations.question_text
        FROM question_translations
        WHERE attempt_questions.question_translation_id = question_translations.id
          AND attempt_questions.question_text_snapshot = ''
        """
    )


def downgrade() -> None:
    op.create_foreign_key(
        "student_answers_selected_option_id_fkey",
        "student_answers",
        "question_options",
        ["selected_option_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "student_answers_attempt_question_id_fkey",
        "student_answers",
        "attempt_questions",
        ["attempt_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "student_answers",
        "question_id",
        existing_type=sa.Uuid(as_uuid=True),
        server_default=None,
    )
    op.alter_column(
        "attempt_questions",
        "question_text_snapshot",
        existing_type=sa.String(),
        server_default="",
    )
    op.drop_constraint("ck_quiz_attempts_percentage_matches_score", "quiz_attempts", type_="check")
    op.drop_constraint("ck_quiz_attempts_score_correct", "quiz_attempts", type_="check")
    op.drop_constraint("ck_quiz_attempts_completion", "quiz_attempts", type_="check")
    op.create_check_constraint(
        "ck_quiz_attempts_completed",
        "quiz_attempts",
        "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR (status != 'COMPLETED')",
    )
    op.drop_constraint("ck_attempt_questions_order", "attempt_questions", type_="check")
    op.drop_constraint("fk_attempt_questions_question_context", "attempt_questions", type_="foreignkey")
    op.drop_constraint("fk_attempt_questions_attempt_context", "attempt_questions", type_="foreignkey")
    for column in ("chapter_id", "subject_id", "class_id"):
        op.drop_column("attempt_questions", column)
    op.drop_constraint("fk_quiz_attempts_class_school", "quiz_attempts", type_="foreignkey")
    op.drop_constraint("quiz_attempts_school_id_fkey", "quiz_attempts", type_="foreignkey")
    op.drop_constraint("fk_quiz_attempts_student_school", "quiz_attempts", type_="foreignkey")
    op.drop_constraint("fk_quiz_attempts_quiz_context", "quiz_attempts", type_="foreignkey")
    op.drop_constraint("uq_quiz_attempts_id_context", "quiz_attempts", type_="unique")
    op.drop_index("ix_quiz_attempts_school_id", table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "school_id")
    op.drop_constraint("ck_quiz_questions_order", "quiz_questions", type_="check")
    op.drop_constraint("fk_quiz_questions_question_context", "quiz_questions", type_="foreignkey")
    op.drop_constraint("fk_quiz_questions_quiz_context", "quiz_questions", type_="foreignkey")
    for column in ("chapter_id", "subject_id", "class_id"):
        op.drop_column("quiz_questions", column)
    op.drop_constraint("uq_quizzes_id_context", "quizzes", type_="unique")
    op.drop_constraint("uq_questions_id_subject_chapter", "questions", type_="unique")
    op.drop_constraint("fk_questions_subject_school", "questions", type_="foreignkey")
    op.drop_constraint("fk_questions_updated_by_school", "questions", type_="foreignkey")
    op.drop_constraint("fk_questions_created_by_school", "questions", type_="foreignkey")
    op.drop_constraint("questions_school_id_fkey", "questions", type_="foreignkey")
    op.create_foreign_key(
        "questions_school_id_fkey",
        "questions",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("questions_created_by_fkey", "questions", type_="foreignkey")
    op.create_foreign_key(
        "questions_created_by_fkey",
        "questions",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("questions_updated_by_fkey", "questions", type_="foreignkey")
    op.create_foreign_key(
        "questions_updated_by_fkey",
        "questions",
        "users",
        ["updated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("questions", "school_id", nullable=True)
    op.drop_constraint("fk_teacher_assignments_class_subject", "teacher_assignments", type_="foreignkey")
    op.drop_constraint("fk_teacher_assignments_class_school_year", "teacher_assignments", type_="foreignkey")
    op.drop_constraint("fk_teacher_assignments_teacher_school", "teacher_assignments", type_="foreignkey")
    op.drop_constraint("fk_student_enrollments_class_school_year", "student_enrollments", type_="foreignkey")
    op.drop_constraint("fk_student_enrollments_student_school", "student_enrollments", type_="foreignkey")
    op.drop_constraint("uq_academic_classes_id_school_year", "academic_classes", type_="unique")
    op.drop_constraint("uq_users_id_school", "users", type_="unique")
    op.drop_constraint("fk_chapters_class_subject", "chapters", type_="foreignkey")
    op.drop_constraint("fk_class_subjects_subject_school", "class_subjects", type_="foreignkey")
    op.drop_constraint("fk_class_subjects_class_school", "class_subjects", type_="foreignkey")
    op.drop_constraint("class_subjects_school_id_fkey", "class_subjects", type_="foreignkey")
    op.drop_index("ix_class_subjects_school_id", table_name="class_subjects")
    op.drop_column("class_subjects", "school_id")
    op.create_check_constraint(
        "ck_student_enrollments_student",
        "student_enrollments",
        "student_id IS NOT NULL",
    )
    op.drop_constraint(
        "teacher_assignments_subject_id_fkey",
        "teacher_assignments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "teacher_assignments_subject_id_fkey",
        "teacher_assignments",
        "subjects",
        ["subject_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "teacher_assignments_class_id_fkey",
        "teacher_assignments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "teacher_assignments_class_id_fkey",
        "teacher_assignments",
        "academic_classes",
        ["class_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("uq_question_options_single_correct", table_name="question_options")
    op.drop_constraint("ck_question_options_order", "question_options", type_="check")

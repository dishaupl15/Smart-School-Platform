from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import (
    AttemptQuestion,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    StudentAnswer,
)
from app.models.enrollment import StudentEnrollment, TeacherAssignment
from app.models.enums import (
    AttemptStatus,
    LanguageCode,
    QuestionDifficulty,
    QuestionStatus,
    QuestionType,
    RoleName,
)
from app.models.question import OptionTranslation, Question, QuestionOption, QuestionTranslation
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


def create_academic_context(
    db_session: Session,
    school_code: str = "EX-001",
) -> tuple[School, AcademicClass, Subject, Chapter]:
    school = School(name=f"School {school_code}", school_code=school_code)
    db_session.add(school)
    db_session.flush()

    academic_class = AcademicClass(
        school_id=school.id,
        name="Class 8",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    subject = Subject(
        school_id=school.id,
        name="Mathematics",
        code="MATH",
    )
    db_session.add_all([academic_class, subject])
    db_session.flush()

    association = ClassSubject(
        class_id=academic_class.id,
        subject_id=subject.id,
        school_id=school.id,
    )
    db_session.add(association)
    db_session.flush()
    chapter = Chapter(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_number=1,
        title="Integers",
    )
    db_session.add(chapter)
    db_session.flush()
    return school, academic_class, subject, chapter


def test_uuid_generation_and_academic_relationships(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    db_session.commit()

    assert isinstance(school.id, UUID)
    assert academic_class.school_id == school.id
    assert subject.school_id == school.id
    assert chapter.class_id == academic_class.id
    assert chapter.subject_id == subject.id


def test_academic_class_duplicate_identity_is_rejected(db_session: Session) -> None:
    school = School(name="Test School", school_code="TEST")
    db_session.add(school)
    db_session.flush()
    db_session.add_all(
        [
            AcademicClass(
                school_id=school.id,
                name="Class 8",
                grade_number=8,
                academic_year="2026-27",
                section="A",
            ),
            AcademicClass(
                school_id=school.id,
                name="Another name",
                grade_number=8,
                academic_year="2026-27",
                section="A",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_academic_class_without_section_is_unique(db_session: Session) -> None:
    school = School(name="No Section School", school_code="NO-SECTION")
    db_session.add(school)
    db_session.flush()
    db_session.add_all(
        [
            AcademicClass(
                school_id=school.id,
                name="Grade 4",
                grade_number=4,
                academic_year="2026-27",
                section=None,
            ),
            AcademicClass(
                school_id=school.id,
                name="Another Grade 4",
                grade_number=4,
                academic_year="2026-27",
                section=None,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_identifiers_and_subject_codes_are_case_insensitive_per_school(
    db_session: Session,
) -> None:
    school, _, subject, _ = create_academic_context(db_session, "CASE-UNIQUE")
    db_session.commit()
    duplicate_subject = Subject(
        school_id=school.id,
        name="mathematics",
        code=subject.code.lower(),
    )
    db_session.add(duplicate_subject)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        User(
            school_id=school.id,
            full_name="First",
            username="CaseUser",
        )
    )
    db_session.flush()
    db_session.add(
        User(
            school_id=school.id,
            full_name="Duplicate",
            username="caseuser",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_role_association_supports_one_user_with_multiple_roles(db_session: Session) -> None:
    school = School(name="Role School", school_code="ROLE")
    student = User(school_id=None, full_name="Student One", username="student-1")
    db_session.add_all([school, student])
    db_session.flush()

    roles = [
        Role(name=RoleName.ADMIN),
        Role(name=RoleName.STUDENT),
    ]
    db_session.add_all(roles)
    db_session.flush()
    db_session.add_all(
        [
            UserRole(user_id=student.id, role_id=roles[0].id),
            UserRole(user_id=student.id, role_id=roles[1].id),
        ]
    )
    db_session.commit()

    assert len(student.user_roles) == 2


def test_enrollment_and_teacher_assignment_constraints(db_session: Session) -> None:
    school, academic_class, subject, _ = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Student", username="S-001")
    teacher = User(school_id=school.id, full_name="Teacher", username="T-001")
    db_session.add_all([student, teacher])
    db_session.flush()

    db_session.add_all(
        [
            StudentEnrollment(
                student_id=student.id,
                class_id=academic_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
            TeacherAssignment(
                teacher_id=teacher.id,
                class_id=academic_class.id,
                subject_id=subject.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
        ]
    )
    db_session.commit()

    duplicate_enrollment = StudentEnrollment(
        student_id=student.id,
        class_id=academic_class.id,
        school_id=school.id,
        academic_year="2026-27",
    )
    db_session.add(duplicate_enrollment)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_enrollments_support_history_and_class_transfers(db_session: Session) -> None:
    school, current_class, _, _ = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Transfer Student")
    next_class = AcademicClass(
        school_id=school.id,
        name="Class 8 - B",
        grade_number=8,
        academic_year="2026-27",
        section="B",
    )
    next_year_class = AcademicClass(
        school_id=school.id,
        name="Class 9",
        grade_number=9,
        academic_year="2027-28",
        section="A",
    )
    db_session.add_all([student, next_class, next_year_class])
    db_session.flush()
    original = StudentEnrollment(
        student_id=student.id,
        class_id=current_class.id,
        school_id=school.id,
        academic_year="2026-27",
        is_active=False,
    )
    db_session.add_all(
        [
            original,
            StudentEnrollment(
                student_id=student.id,
                class_id=next_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
            StudentEnrollment(
                student_id=student.id,
                class_id=next_year_class.id,
                school_id=school.id,
                academic_year="2027-28",
            ),
        ]
    )
    db_session.commit()

    assert db_session.query(StudentEnrollment).filter_by(student_id=student.id).count() == 3
    conflicting_active = AcademicClass(
        school_id=school.id,
        name="Class 8 - C",
        grade_number=8,
        academic_year="2026-27",
        section="C",
    )
    db_session.add(conflicting_active)
    db_session.flush()
    db_session.add(
        StudentEnrollment(
            student_id=student.id,
            class_id=conflicting_active.id,
            school_id=school.id,
            academic_year="2026-27",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_school_owned_academic_relations_reject_cross_school_links(db_session: Session) -> None:
    first_school, first_class, _, _ = create_academic_context(db_session)
    _, _, second_subject, second_chapter = create_academic_context(
        db_session,
        school_code="EX-002",
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                ClassSubject(
                    class_id=first_class.id,
                    subject_id=second_subject.id,
                    school_id=first_school.id,
                )
            )
            db_session.flush()
    mismatched_question = Question(
        school_id=first_school.id,
        subject_id=second_subject.id,
        chapter_id=second_chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.DRAFT,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(mismatched_question)
            db_session.flush()


def test_question_translation_and_option_translation_uniqueness(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.MEDIUM,
        status=QuestionStatus.APPROVED,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add_all(
        [
            QuestionTranslation(
                question_id=question.id,
                language_code=LanguageCode.EN,
                question_text="What is 2 + 2?",
            ),
            QuestionOption(
                question_id=question.id,
                option_key="A",
                display_order=1,
                is_correct=False,
            ),
            QuestionOption(
                question_id=question.id,
                option_key="B",
                display_order=2,
                is_correct=True,
            ),
        ]
    )
    db_session.flush()
    db_session.refresh(question)

    option = question.options[0]
    db_session.add(
        OptionTranslation(
            option_id=option.id,
            language_code=LanguageCode.EN,
            option_text="Three",
        )
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                QuestionTranslation(
                    question_id=question.id,
                    language_code=LanguageCode.EN,
                    question_text="Duplicate translation",
                )
            )
            db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                QuestionOption(
                    question_id=question.id,
                    option_key="C",
                    display_order=3,
                    is_correct=True,
                )
            )
            db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                OptionTranslation(
                    option_id=option.id,
                    language_code=LanguageCode.EN,
                    option_text="Duplicate",
                )
            )
            db_session.flush()


def test_attempt_question_and_answer_uniqueness(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Attempt Student", username="S-100")
    db_session.add(student)
    db_session.flush()
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.APPROVED,
    )
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Integers practice",
        total_questions=1,
    )
    db_session.add_all([question, quiz])
    db_session.flush()
    option = QuestionOption(question_id=question.id, option_key="A", display_order=1, is_correct=True)
    db_session.add(option)
    db_session.flush()
    db_session.add(
        QuizQuestion(
            quiz_id=quiz.id,
            question_id=question.id,
            class_id=academic_class.id,
            subject_id=subject.id,
            chapter_id=chapter.id,
            display_order=1,
        )
    )
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=school.id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        attempt_number=1,
        started_at=datetime.now(timezone.utc),
        status=AttemptStatus.IN_PROGRESS,
        total_questions=1,
        unanswered_questions=1,
    )
    db_session.add(attempt)
    db_session.flush()
    attempt_question = AttemptQuestion(
        attempt_id=attempt.id,
        question_id=question.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        display_order=1,
        selected_language=LanguageCode.EN,
        question_text_snapshot="Historical text",
        question_snapshot={"text": "Historical text"},
        option_order_snapshot=[{"option_id": str(option.id), "key": "A"}],
    )
    db_session.add(attempt_question)
    db_session.flush()
    db_session.add(
        StudentAnswer(
            attempt_question_id=attempt_question.id,
            question_id=question.id,
            selected_option_id=option.id,
            answered_at=datetime.now(timezone.utc),
            is_correct=None,
        )
    )
    db_session.commit()

    duplicate_answer = StudentAnswer(
        attempt_question_id=attempt_question.id,
        question_id=question.id,
        answered_at=datetime.now(timezone.utc),
        is_correct=None,
    )
    db_session.add(duplicate_answer)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_question_can_be_reused_across_quizzes_in_its_chapter(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.MEDIUM,
        status=QuestionStatus.APPROVED,
    )
    first_quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Practice",
        total_questions=1,
    )
    second_quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Random chapter quiz",
        total_questions=1,
    )
    db_session.add_all([question, first_quiz, second_quiz])
    db_session.flush()
    db_session.add_all(
        [
            QuizQuestion(
                quiz_id=first_quiz.id,
                question_id=question.id,
                class_id=academic_class.id,
                subject_id=subject.id,
                chapter_id=chapter.id,
                display_order=1,
            ),
            QuizQuestion(
                quiz_id=second_quiz.id,
                question_id=question.id,
                class_id=academic_class.id,
                subject_id=subject.id,
                chapter_id=chapter.id,
                display_order=1,
            ),
        ]
    )
    db_session.commit()

    assert db_session.query(QuizQuestion).filter_by(question_id=question.id).count() == 2


def test_unanswered_question_is_representable(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Unanswered Student")
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.APPROVED,
    )
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Unanswered question",
        total_questions=1,
    )
    db_session.add_all([student, question, quiz])
    db_session.flush()
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=school.id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        attempt_number=1,
        started_at=datetime.now(timezone.utc),
        status=AttemptStatus.IN_PROGRESS,
        total_questions=1,
        unanswered_questions=1,
    )
    db_session.add(attempt)
    db_session.flush()
    attempt_question = AttemptQuestion(
        attempt_id=attempt.id,
        question_id=question.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        display_order=1,
        selected_language=LanguageCode.EN,
        question_text_snapshot="Snapshot text",
        question_snapshot={"text": "Snapshot text"},
        option_order_snapshot=[],
    )
    db_session.add(attempt_question)
    db_session.flush()
    db_session.add(
        StudentAnswer(
            attempt_question_id=attempt_question.id,
            question_id=question.id,
            selected_option_id=None,
            answered_at=datetime.now(timezone.utc),
            is_correct=None,
        )
    )
    db_session.commit()


def test_attempt_snapshot_survives_question_and_translation_edits(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Snapshot Student")
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.APPROVED,
    )
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Snapshot quiz",
        total_questions=1,
    )
    db_session.add_all([student, question, quiz])
    db_session.flush()
    translation = QuestionTranslation(
        question_id=question.id,
        language_code=LanguageCode.EN,
        question_text="Original question",
    )
    option = QuestionOption(
        question_id=question.id,
        option_key="A",
        display_order=1,
        is_correct=True,
    )
    second_option = QuestionOption(
        question_id=question.id,
        option_key="B",
        display_order=2,
        is_correct=False,
    )
    db_session.add_all([translation, option, second_option])
    db_session.flush()
    option_translation = OptionTranslation(
        option_id=option.id,
        language_code=LanguageCode.EN,
        option_text="Original option",
    )
    second_option_translation = OptionTranslation(
        option_id=second_option.id,
        language_code=LanguageCode.EN,
        option_text="Original second option",
    )
    db_session.add_all([option_translation, second_option_translation])
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=school.id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        attempt_number=1,
        started_at=datetime.now(timezone.utc),
        status=AttemptStatus.IN_PROGRESS,
        total_questions=1,
        unanswered_questions=1,
    )
    db_session.add(attempt)
    db_session.flush()
    attempt_question = AttemptQuestion(
        attempt_id=attempt.id,
        question_id=question.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_translation_id=translation.id,
        display_order=1,
        selected_language=LanguageCode.EN,
        question_text_snapshot="Original question",
        question_snapshot={"text": "Original question"},
        option_order_snapshot=[
            {
                "option_id": str(second_option.id),
                "key": "B",
                "display_order": 1,
                "text": "Original second option",
            },
            {
                "option_id": str(option.id),
                "key": "A",
                "display_order": 2,
                "text": "Original option",
            }
        ],
    )
    db_session.add(attempt_question)
    db_session.commit()

    translation.question_text = "Edited question"
    option_translation.option_text = "Edited option"
    second_option_translation.option_text = "Edited second option"
    db_session.commit()
    db_session.refresh(attempt_question)

    assert attempt_question.selected_language == LanguageCode.EN
    assert attempt_question.display_order == 1
    assert attempt_question.question_text_snapshot == "Original question"
    assert [option["display_order"] for option in attempt_question.option_order_snapshot] == [1, 2]
    assert [option["text"] for option in attempt_question.option_order_snapshot] == [
        "Original second option",
        "Original option",
    ]


def test_student_answer_rejects_an_option_from_another_question(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Answer Student")
    first_question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.APPROVED,
    )
    second_question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.EASY,
        status=QuestionStatus.APPROVED,
    )
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Answer quiz",
        total_questions=1,
    )
    db_session.add_all([student, first_question, second_question, quiz])
    db_session.flush()
    other_option = QuestionOption(
        question_id=second_question.id,
        option_key="A",
        display_order=1,
        is_correct=True,
    )
    db_session.add(other_option)
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=school.id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        attempt_number=1,
        started_at=datetime.now(timezone.utc),
        status=AttemptStatus.IN_PROGRESS,
        total_questions=1,
        unanswered_questions=1,
    )
    db_session.add(attempt)
    db_session.flush()
    attempt_question = AttemptQuestion(
        attempt_id=attempt.id,
        question_id=first_question.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        display_order=1,
        selected_language=LanguageCode.EN,
        question_text_snapshot="Question",
        question_snapshot={"text": "Question"},
        option_order_snapshot=[],
    )
    db_session.add(attempt_question)
    db_session.flush()
    db_session.add(
        StudentAnswer(
            attempt_question_id=attempt_question.id,
            question_id=first_question.id,
            selected_option_id=other_option.id,
            answered_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_question_cascades_translations_and_options(db_session: Session) -> None:
    school, _, subject, chapter = create_academic_context(db_session)
    question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty=QuestionDifficulty.HARD,
        status=QuestionStatus.DRAFT,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add_all(
        [
            QuestionTranslation(
                question_id=question.id,
                language_code=LanguageCode.MR,
                question_text="प्रश्न",
            ),
            QuestionOption(
                question_id=question.id,
                option_key="A",
                display_order=1,
                is_correct=True,
            ),
        ]
    )
    db_session.commit()

    db_session.delete(question)
    db_session.commit()

    assert db_session.get(Question, question.id) is None
    assert db_session.query(QuestionTranslation).count() == 0
    assert db_session.query(QuestionOption).count() == 0


def test_foreign_key_constraint_rejects_unknown_school(db_session: Session) -> None:
    invalid_class = AcademicClass(
        school_id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Class 8",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    db_session.add(invalid_class)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_enum_value_is_rejected(db_session: Session) -> None:
    school, _, subject, chapter = create_academic_context(db_session)
    invalid_question = Question(
        school_id=school.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        question_type=QuestionType.SINGLE_CHOICE,
        difficulty="IMPOSSIBLE",
        status=QuestionStatus.DRAFT,
    )

    db_session.add(invalid_question)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_attempt_score_and_percentage_must_match_counts(db_session: Session) -> None:
    school, academic_class, subject, chapter = create_academic_context(db_session)
    student = User(school_id=school.id, full_name="Scoring Student")
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Scoring quiz",
        total_questions=2,
    )
    db_session.add_all([student, quiz])
    db_session.flush()
    attempt_values = dict(
        student_id=student.id,
        school_id=school.id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        started_at=datetime.now(timezone.utc),
        status=AttemptStatus.IN_PROGRESS,
        total_questions=2,
        correct_answers=1,
        incorrect_answers=1,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                QuizAttempt(
                    **attempt_values,
                    attempt_number=1,
                    score=0,
                    percentage=0,
                )
            )
            db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                QuizAttempt(
                    **attempt_values,
                    attempt_number=2,
                    score=1,
                    percentage=0,
                )
            )
            db_session.flush()

    db_session.add(
        QuizAttempt(
            **attempt_values,
            attempt_number=3,
            score=1,
            percentage=50,
        )
    )
    db_session.commit()

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import AttemptQuestion, Quiz, QuizQuestion, QuizAttempt
from app.models.enrollment import StudentEnrollment
from app.models.enums import (
    AttemptStatus,
    LanguageCode,
    QuestionDifficulty,
    QuestionStatus,
    QuestionType,
)
from app.models.question import (
    OptionTranslation,
    Question,
    QuestionOption,
    QuestionTranslation,
)
from app.models.user import User
from app.models.role import Role, UserRole
from app.models.school import School


@pytest.fixture
def quiz_student_context(auth_client, db_session):
    school = School(name="Quiz School", school_code=f"Q-{uuid4().hex[:8]}")
    db_session.add(school)
    db_session.flush()
    academic_class = AcademicClass(
        school_id=school.id,
        name="Class 8 - A",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    subject = Subject(school_id=school.id, name="Mathematics", code="MATH")
    student = User(
        school_id=school.id,
        full_name="Quiz Student",
        username=f"student-{uuid4().hex[:8]}",
        password_hash=hash_password("student password"),
    )
    db_session.add_all([academic_class, subject, student])
    db_session.flush()
    db_session.add(
        ClassSubject(
            class_id=academic_class.id,
            subject_id=subject.id,
            school_id=school.id,
        )
    )
    db_session.flush()
    chapter = Chapter(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_number=1,
        title="Numbers",
    )
    db_session.add(chapter)
    db_session.flush()
    db_session.add_all(
        [
            StudentEnrollment(
                student_id=student.id,
                class_id=academic_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
            UserRole(
                user_id=student.id,
                role_id=db_session.query(Role).filter_by(name="STUDENT").one().id,
            ),
        ]
    )
    db_session.commit()
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Number quiz",
        total_questions=5,
    )
    db_session.add(quiz)
    db_session.commit()
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": student.username, "password": "student password"},
    )
    assert login.status_code == 200
    auth_client.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    yield auth_client, db_session, student, academic_class, subject, chapter
    auth_client.headers.clear()


def _add_approved_questions(
    db: Session,
    quiz: Quiz,
    school_id,
    *,
    count: int = 20,
) -> None:
    starting_order = (
        db.query(QuizQuestion).filter_by(quiz_id=quiz.id).count()
    )
    for index in range(count):
        question = Question(
            school_id=school_id,
            subject_id=quiz.subject_id,
            chapter_id=quiz.chapter_id,
            question_type=QuestionType.SINGLE_CHOICE,
            difficulty=QuestionDifficulty.EASY,
            status=QuestionStatus.APPROVED,
        )
        db.add(question)
        db.flush()
        db.add(
            QuestionTranslation(
                question_id=question.id,
                language_code=LanguageCode.EN,
                question_text=f"Question {index + 1}",
                explanation=f"Explanation {index + 1}",
            )
        )
        db.flush()
        options = []
        for order, label in enumerate(("A", "B", "C", "D"), start=1):
            option = QuestionOption(
                question_id=question.id,
                option_key=label,
                display_order=order,
                is_correct=label == "B",
            )
            db.add(option)
            db.flush()
            db.add(
                OptionTranslation(
                    option_id=option.id,
                    language_code=LanguageCode.EN,
                    option_text=f"Option {label} for {index + 1}",
                )
            )
            options.append(option)
        db.add(
            QuizQuestion(
                quiz_id=quiz.id,
                question_id=question.id,
                class_id=quiz.class_id,
                subject_id=quiz.subject_id,
                chapter_id=quiz.chapter_id,
                display_order=starting_order + index + 1,
            )
        )
    db.commit()


def _start_quiz(client: TestClient, chapter_id) -> dict:
    response = client.post(
        f"/api/v1/student/chapters/{chapter_id}/quiz/start",
        json={"language_code": "en"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _record_completed_attempt(
    db: Session,
    student: User,
    quiz: Quiz,
    *,
    attempt_number: int,
    completed_at: datetime,
    score: int,
    question_id=None,
) -> QuizAttempt:
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=student.school_id,
        quiz_id=quiz.id,
        class_id=quiz.class_id,
        subject_id=quiz.subject_id,
        chapter_id=quiz.chapter_id,
        attempt_number=attempt_number,
        started_at=completed_at - timedelta(minutes=10),
        completed_at=completed_at,
        status=AttemptStatus.COMPLETED,
        total_questions=20,
        correct_answers=score,
        incorrect_answers=20 - score,
        unanswered_questions=0,
        score=score,
        percentage=Decimal(str(score * 5)),
    )
    db.add(attempt)
    db.flush()
    if question_id is not None:
        correct_option_id = str(uuid4())
        db.add(
            AttemptQuestion(
                attempt_id=attempt.id,
                question_id=question_id,
                class_id=quiz.class_id,
                subject_id=quiz.subject_id,
                chapter_id=quiz.chapter_id,
                display_order=1,
                selected_language=LanguageCode.EN,
                question_text_snapshot="Snapshot question text",
                question_snapshot={
                    "options": [
                        {"id": correct_option_id, "text": "Snapshot answer"}
                    ],
                    "correct_option_id": correct_option_id,
                    "explanation": "Snapshot explanation",
                },
                option_order_snapshot=[correct_option_id],
            )
        )
    return attempt


def test_quiz_starts_with_exact_private_snapshot_and_resumes(
    quiz_student_context,
) -> None:
    client, db, student, _, _, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id)

    started = _start_quiz(client, chapter.id)
    assert started["status"] == "IN_PROGRESS"
    assert started["total_questions"] == 15
    assert len(started["questions"]) == 15
    assert len({question["attempt_question_id"] for question in started["questions"]}) == 15
    assert started["remaining_seconds"] <= 20 * 60
    assert all(len(question["options"]) == 4 for question in started["questions"])
    assert "correct_option_id" not in started
    assert "is_correct" not in started
    assert "explanation" not in started
    assert "correct_option_id" not in started["questions"][0]

    first_question = started["questions"][0]
    chosen = first_question["options"][0]["id"]
    answer = client.put(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
        f"/answers/{first_question['attempt_question_id']}",
        json={"selected_option_id": chosen},
    )
    assert answer.status_code == 200, answer.text
    feedback = answer.json()["questions"][0]["feedback"]
    assert feedback["correct_option_id"]
    assert feedback["is_correct"] == (
        chosen == feedback["correct_option_id"]
    )
    assert feedback["explanation"].startswith("Explanation")
    repeated = client.put(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
        f"/answers/{first_question['attempt_question_id']}",
        json={"selected_option_id": chosen},
    )
    assert repeated.status_code == 200
    changed = client.put(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
        f"/answers/{first_question['attempt_question_id']}",
        json={
            "selected_option_id": next(
                option["id"]
                for option in first_question["options"]
                if option["id"] != chosen
            )
        },
    )
    assert changed.status_code == 409
    current = client.get(
        f"/api/v1/student/chapters/{chapter.id}/quiz/current"
    )
    assert current.status_code == 200
    assert current.json()["attempt_id"] == started["attempt_id"]
    assert current.json()["questions"][0]["selected_option_id"] == chosen
    resumed = _start_quiz(client, chapter.id)
    assert resumed["attempt_id"] == started["attempt_id"]


def test_quiz_answers_grade_and_submission_is_idempotent(quiz_student_context) -> None:
    client, db, student, _, _, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id)
    started = _start_quiz(client, chapter.id)
    attempt_questions = (
        db.query(AttemptQuestion)
        .filter_by(attempt_id=UUID(started["attempt_id"]))
        .order_by(AttemptQuestion.display_order)
        .all()
    )
    for index, question in enumerate(attempt_questions[:3]):
        correct_id = question.question_snapshot["correct_option_id"]
        wrong_id = next(
            option["id"]
            for option in question.question_snapshot["options"]
            if option["id"] != correct_id
        )
        selected_id = wrong_id if index in {0, 2} else correct_id
        if index == 0:
            answer = client.put(
                f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
                f"/answers/{question.id}",
                json={"selected_option_id": selected_id},
            )
            assert answer.status_code == 200, answer.text
            assert answer.json()["questions"][0]["feedback"]["is_correct"] is False
            changed = client.put(
                f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
                f"/answers/{question.id}",
                json={"selected_option_id": correct_id},
            )
            assert changed.status_code == 409
            continue
        response = client.put(
            f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
            f"/answers/{question.id}",
            json={"selected_option_id": selected_id},
        )
        assert response.status_code == 200, response.text

    submitted = client.post(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}/submit"
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["status"] == "COMPLETED"
    assert result["total_questions"] == 15
    assert result["correct_answers"] == 1
    assert result["incorrect_answers"] == 2
    assert result["unanswered_questions"] == 12
    assert result["score"] == 1
    assert result["percentage"] == 6.67
    assert result["questions"][0]["correct_option_id"]
    assert result["questions"][0]["explanation"].startswith("Explanation")

    repeated = client.post(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}/submit"
    )
    assert repeated.status_code == 200
    assert repeated.json()["score"] == result["score"]
    repeated_completed_at = datetime.fromisoformat(
        repeated.json()["completed_at"].replace("Z", "+00:00")
    )
    initial_completed_at = datetime.fromisoformat(
        result["completed_at"].replace("Z", "+00:00")
    )
    assert repeated_completed_at.replace(tzinfo=timezone.utc) == initial_completed_at.replace(
        tzinfo=timezone.utc
    )
    assert repeated.json()["questions"] == result["questions"]
    saved_result = client.get(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}/result"
    )
    assert saved_result.status_code == 200
    assert saved_result.json()["score"] == result["score"]
    assert saved_result.json()["questions"] == result["questions"]


def test_quiz_rejects_insufficient_questions_and_expires_on_access(
    quiz_student_context,
) -> None:
    client, db, student, _, _, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id, count=14)
    insufficient = client.post(
        f"/api/v1/student/chapters/{chapter.id}/quiz/start",
        json={"language_code": "en"},
    )
    assert insufficient.status_code == 409

    _add_approved_questions(db, quiz, student.school_id, count=1)
    started = _start_quiz(client, chapter.id)
    attempt = db.get(QuizAttempt, UUID(started["attempt_id"]))
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=21)
    db.commit()

    expired = client.get(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
    )
    assert expired.status_code == 200, expired.text
    assert expired.json()["status"] == "COMPLETED"
    assert expired.json()["unanswered_questions"] == 15
    assert db.get(QuizAttempt, UUID(started["attempt_id"])).status == AttemptStatus.COMPLETED


def test_attempt_is_hidden_from_another_student_and_options_are_scoped(
    quiz_student_context,
) -> None:
    client, db, student, _, _, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id)
    started = _start_quiz(client, chapter.id)
    other_question = started["questions"][1]
    invalid_option = client.put(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
        f"/answers/{started['questions'][0]['attempt_question_id']}",
        json={"selected_option_id": other_question["options"][0]["id"]},
    )
    assert invalid_option.status_code == 422

    attempt = db.get(QuizAttempt, UUID(started["attempt_id"]))
    other_student = User(
        school_id=student.school_id,
        full_name="Different student",
        username=f"different-{uuid4().hex[:8]}",
    )
    db.add(other_student)
    db.flush()
    attempt.student_id = other_student.id
    db.commit()
    hidden = client.get(
        f"/api/v1/student/quiz/attempts/{started['attempt_id']}"
    )
    assert hidden.status_code == 404


def test_quiz_history_filters_paginates_and_analytics_uses_completed_attempts(
    quiz_student_context,
) -> None:
    client, db, student, academic_class, subject, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id)
    question_id = (
        db.query(QuizQuestion.question_id)
        .filter_by(quiz_id=quiz.id)
        .order_by(QuizQuestion.display_order)
        .first()[0]
    )
    now = datetime.now(timezone.utc)
    timestamps = [
        datetime(2026, 4, day, 12, tzinfo=timezone.utc) for day in (4, 5, 6)
    ]
    math_scores = [4, 8, 18]
    math_attempts = [
        _record_completed_attempt(
            db,
            student,
            quiz,
            attempt_number=index,
            completed_at=completed_at,
            score=score,
            question_id=question_id,
        )
        for index, (completed_at, score) in enumerate(
            zip(timestamps, math_scores, strict=True),
            start=1,
        )
    ]
    incomplete = QuizAttempt(
        student_id=student.id,
        school_id=student.school_id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        attempt_number=4,
        started_at=now,
        status=AttemptStatus.IN_PROGRESS,
        total_questions=20,
        correct_answers=0,
        incorrect_answers=0,
        unanswered_questions=20,
        score=0,
        percentage=0,
    )
    db.add(incomplete)

    science = Subject(
        school_id=student.school_id,
        name="Science",
        code=f"SCI-{uuid4().hex[:6]}",
    )
    db.add(science)
    db.flush()
    db.add(
        ClassSubject(
            class_id=academic_class.id,
            subject_id=science.id,
            school_id=student.school_id,
        )
    )
    db.flush()
    science_chapter = Chapter(
        class_id=academic_class.id,
        subject_id=science.id,
        chapter_number=1,
        title="Matter",
    )
    db.add(science_chapter)
    db.flush()
    science_quiz = Quiz(
        class_id=academic_class.id,
        subject_id=science.id,
        chapter_id=science_chapter.id,
        title="Matter quiz",
        total_questions=20,
    )
    db.add(science_quiz)
    db.flush()
    science_attempt = _record_completed_attempt(
        db,
        student,
        science_quiz,
        attempt_number=1,
        completed_at=datetime(2026, 4, 7, 12, tzinfo=timezone.utc),
        score=19,
    )

    other_student = User(
        school_id=student.school_id,
        full_name="Another student",
        username=f"other-{uuid4().hex[:8]}",
    )
    db.add(other_student)
    db.flush()
    other_attempt = _record_completed_attempt(
        db,
        other_student,
        quiz,
        attempt_number=1,
        completed_at=datetime(2026, 4, 8, 12, tzinfo=timezone.utc),
        score=20,
    )
    db.commit()

    first_page = client.get(
        "/api/v1/student/quiz/history",
        params={"subject_id": str(subject.id), "page": 1, "page_size": 1},
    )
    assert first_page.status_code == 200, first_page.text
    first_data = first_page.json()
    assert first_data["total_items"] == 3
    assert first_data["total_pages"] == 3
    assert first_data["items"][0]["attempt_id"] == str(math_attempts[-1].id)
    assert first_data["items"][0]["percentage"] == 90

    date_filter = client.get(
        "/api/v1/student/quiz/history",
        params={
            "chapter_id": str(chapter.id),
            "date_from": "2026-04-05",
            "date_to": "2026-04-05",
        },
    )
    assert date_filter.status_code == 200, date_filter.text
    assert [item["attempt_id"] for item in date_filter.json()["items"]] == [
        str(math_attempts[1].id)
    ]
    assert (
        client.get(
            "/api/v1/student/quiz/history",
            params={"date_from": "2026-04-07", "date_to": "2026-04-01"},
        ).status_code
        == 422
    )

    analytics = client.get("/api/v1/student/quiz/analytics")
    assert analytics.status_code == 200, analytics.text
    data = analytics.json()
    assert data["total_completed_quizzes"] == 4
    assert data["total_questions"] == 80
    assert data["total_correct_answers"] == 49
    assert data["average_percentage"] == 61.25
    assert data["highest_percentage"] == 95
    assert [item["attempt_id"] for item in data["recent_activity"]] == [
        str(science_attempt.id),
        str(math_attempts[-1].id),
        str(math_attempts[-2].id),
        str(math_attempts[-3].id),
    ]
    assert [item["subject_name"] for item in data["strongest_subjects"]] == [
        "Science"
    ]
    assert [item["subject_name"] for item in data["needs_improvement_subjects"]] == [
        "Mathematics"
    ]
    assert [item["chapter_title"] for item in data["strongest_chapters"]] == [
        "Matter"
    ]
    assert [
        item["chapter_title"] for item in data["needs_improvement_chapters"]
    ] == ["Numbers"]

    snapshot = client.get(
        f"/api/v1/student/quiz/attempts/{math_attempts[-1].id}/result"
    )
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json()["questions"][0]["question_text"] == "Snapshot question text"
    assert (
        snapshot.json()["questions"][0]["options"][0]["text"] == "Snapshot answer"
    )
    assert snapshot.json()["score"] == 18
    hidden = client.get(
        f"/api/v1/student/quiz/attempts/{other_attempt.id}/result"
    )
    assert hidden.status_code == 404


def test_quizzes_require_an_active_enrollment_and_enrolled_class(
    quiz_student_context,
) -> None:
    client, db, student, _, subject, chapter = quiz_student_context
    enrollment = db.query(StudentEnrollment).filter_by(student_id=student.id).one()
    enrollment.is_active = False
    db.commit()
    denied = client.get(
        f"/api/v1/student/chapters/{chapter.id}/quiz/current"
    )
    assert denied.status_code == 403
    assert client.get("/api/v1/student/quiz/history").status_code == 403
    assert client.get("/api/v1/student/quiz/analytics").status_code == 403

    enrollment.is_active = True
    other_school = School(
        name="Other quiz school",
        school_code=f"O-{uuid4().hex[:8]}",
    )
    db.add(other_school)
    db.flush()
    other_class = AcademicClass(
        school_id=other_school.id,
        name="Other class",
        grade_number=7,
        academic_year="2026-27",
    )
    other_subject = Subject(
        school_id=other_school.id,
        name="Other subject",
        code="OTHER",
    )
    db.add_all([other_class, other_subject])
    db.flush()
    db.add(
        ClassSubject(
            class_id=other_class.id,
            subject_id=other_subject.id,
            school_id=other_school.id,
        )
    )
    db.flush()
    other_chapter = Chapter(
        class_id=other_class.id,
        subject_id=other_subject.id,
        chapter_number=1,
        title="Other school's chapter",
    )
    db.add(other_chapter)
    db.flush()
    db.add(
        Quiz(
            class_id=other_class.id,
            subject_id=other_subject.id,
            chapter_id=other_chapter.id,
            title="Other school's quiz",
            total_questions=20,
        )
    )
    db.commit()
    hidden = client.get(
        f"/api/v1/student/chapters/{other_chapter.id}/quiz/current"
    )
    assert hidden.status_code == 404
    unassigned_class = client.get(
        f"/api/v1/student/chapters/{chapter.id}/quiz/current",
        params={"class_id": str(other_class.id)},
    )
    assert unassigned_class.status_code == 404


def test_questions_in_an_active_attempt_cannot_be_edited(quiz_student_context) -> None:
    client, db, student, _, _, chapter = quiz_student_context
    quiz = db.query(Quiz).filter_by(chapter_id=chapter.id).one()
    _add_approved_questions(db, quiz, student.school_id)
    started = _start_quiz(client, chapter.id)
    attempt_question = (
        db.query(AttemptQuestion)
        .filter_by(attempt_id=UUID(started["attempt_id"]))
        .first()
    )
    admin = User(
        school_id=student.school_id,
        full_name="Quiz administrator",
        username=f"admin-{uuid4().hex[:8]}",
        password_hash=hash_password("admin password"),
    )
    db.add(admin)
    db.flush()
    db.add(
        UserRole(
            user_id=admin.id,
            role_id=db.query(Role).filter_by(name="ADMIN").one().id,
        )
    )
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": admin.username, "password": "admin password"},
    )
    assert login.status_code == 200
    response = client.patch(
        f"/api/v1/admin/questions/{attempt_question.question_id}",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"difficulty": "HARD"},
    )
    assert response.status_code == 409

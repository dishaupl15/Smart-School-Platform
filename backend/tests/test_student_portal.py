from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import Quiz, QuizAttempt
from app.models.enrollment import StudentEnrollment
from app.models.enums import AttemptStatus, RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


@pytest.fixture
def student_context(
    auth_client: TestClient,
    db_session: Session,
) -> Iterator[tuple[TestClient, Session, User, AcademicClass, Subject, Chapter]]:
    school = School(name="North School", school_code=f"N-{uuid4().hex[:8]}")
    db_session.add(school)
    db_session.flush()
    academic_class = AcademicClass(
        school_id=school.id,
        name="Class 8 - A",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    db_session.add(academic_class)
    db_session.flush()
    subject = Subject(
        school_id=school.id,
        name="Mathematics",
        code="MATH",
        description="Build confidence with numbers.",
    )
    db_session.add(subject)
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
        title="Rational numbers",
        description="A foundation for working with fractions.",
    )
    inactive_chapter = Chapter(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_number=2,
        title="Hidden chapter",
        is_active=False,
    )
    student = User(
        school_id=school.id,
        full_name="Maya Student",
        email="maya@example.test",
        phone="+1 555 555 1234",
        username="maya-8",
        password_hash=hash_password("student password"),
    )
    db_session.add_all([chapter, inactive_chapter, student])
    db_session.flush()
    db_session.add_all(
        [
            UserRole(
                user_id=student.id,
                role_id=db_session.query(Role).filter_by(name=RoleName.STUDENT).one().id,
            ),
            StudentEnrollment(
                student_id=student.id,
                class_id=academic_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
        ]
    )
    db_session.commit()
    quiz = Quiz(
        class_id=academic_class.id,
        subject_id=subject.id,
        chapter_id=chapter.id,
        title="Rational numbers review",
        total_questions=5,
    )
    db_session.add(quiz)
    db_session.flush()
    completed_at = datetime.now(timezone.utc)
    db_session.add(
        QuizAttempt(
            student_id=student.id,
            school_id=school.id,
            quiz_id=quiz.id,
            class_id=academic_class.id,
            subject_id=subject.id,
            chapter_id=chapter.id,
            attempt_number=1,
            started_at=completed_at,
            completed_at=completed_at,
            status=AttemptStatus.COMPLETED,
            total_questions=5,
            correct_answers=4,
            incorrect_answers=1,
            unanswered_questions=0,
            score=4,
            percentage=Decimal("80.00"),
        )
    )
    db_session.commit()
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "maya-8", "password": "student password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    auth_client.headers.update(headers)
    yield auth_client, db_session, student, academic_class, subject, chapter
    auth_client.headers.clear()


def test_student_portal_returns_only_enrolled_class_content(
    student_context: tuple[
        TestClient, Session, User, AcademicClass, Subject, Chapter
    ],
) -> None:
    client, db, student, academic_class, subject, chapter = student_context

    profile = client.get("/api/v1/student/profile")
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Maya Student"
    assert profile.json()["identifier"] == "maya-8"
    assert profile.json()["school_name"] == "North School"
    assert profile.json()["enrollment"]["class_name"] == academic_class.name

    dashboard = client.get("/api/v1/student/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["subject_count"] == 1
    assert dashboard.json()["chapter_count"] == 1
    assert dashboard.json()["subjects"][0]["id"] == str(subject.id)
    assert dashboard.json()["school_name"] == "North School"
    assert dashboard.json()["completed_quiz_count"] == 1
    assert dashboard.json()["recent_activity"][0]["score"] == 4
    assert dashboard.json()["recent_activity"][0]["percentage"] == 80

    subject_list = client.get("/api/v1/student/subjects")
    assert subject_list.status_code == 200
    assert [item["id"] for item in subject_list.json()] == [str(subject.id)]

    subject_detail = client.get(f"/api/v1/student/subjects/{subject.id}")
    assert subject_detail.status_code == 200
    assert [item["title"] for item in subject_detail.json()["chapters"]] == [
        "Rational numbers"
    ]
    assert subject_detail.json()["chapters"][0]["has_available_quiz"] is True

    chapter_detail = client.get(f"/api/v1/student/chapters/{chapter.id}")
    assert chapter_detail.status_code == 200
    assert chapter_detail.json()["subject_name"] == "Mathematics"
    assert chapter_detail.json()["has_available_quiz"] is True
    assert "question" not in chapter_detail.json()
    assert "answer" not in chapter_detail.json()

    other_class = AcademicClass(
        school_id=student.school_id,
        name="Class 7 - C",
        grade_number=7,
        academic_year="2025-26",
        section="C",
    )
    db.add(other_class)
    db.flush()
    db.add(
        ClassSubject(
            class_id=other_class.id,
            subject_id=subject.id,
            school_id=student.school_id,
        )
    )
    db.flush()
    other_class_chapter = Chapter(
        class_id=other_class.id,
        subject_id=subject.id,
        chapter_number=1,
        title="Other class chapter",
    )
    db.add(other_class_chapter)
    hidden_chapter = (
        db.query(Chapter)
        .filter_by(class_id=academic_class.id, title="Hidden chapter")
        .one()
    )
    db.commit()
    assert client.get(
        f"/api/v1/student/chapters/{other_class_chapter.id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/student/chapters/{hidden_chapter.id}"
    ).status_code == 404

    other_school = School(
        name="South School",
        school_code=f"S-{uuid4().hex[:8]}",
    )
    db.add(other_school)
    db.flush()
    other_school_class = AcademicClass(
        school_id=other_school.id,
        name="Class 8 - A",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    other_school_subject = Subject(
        school_id=other_school.id,
        name="Mathematics",
        code="MATH",
    )
    db.add_all([other_school_class, other_school_subject])
    db.flush()
    db.add(
        ClassSubject(
            class_id=other_school_class.id,
            subject_id=other_school_subject.id,
            school_id=other_school.id,
        )
    )
    db.flush()
    other_school_chapter = Chapter(
        class_id=other_school_class.id,
        subject_id=other_school_subject.id,
        chapter_number=1,
        title="Other school chapter",
    )
    db.add(other_school_chapter)
    db.commit()
    assert client.get(
        f"/api/v1/student/subjects/{other_school_subject.id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/student/chapters/{other_school_chapter.id}"
    ).status_code == 404

    next_class = AcademicClass(
        school_id=student.school_id,
        name="Class 9 - B",
        grade_number=9,
        academic_year="2027-28",
        section="B",
    )
    db.add(next_class)
    db.flush()
    db.add(
        StudentEnrollment(
            student_id=student.id,
            class_id=next_class.id,
            school_id=student.school_id,
            academic_year="2027-28",
        )
    )
    db.commit()
    current_dashboard = client.get("/api/v1/student/dashboard")
    assert current_dashboard.status_code == 200
    assert current_dashboard.json()["enrollment"]["class_name"] == next_class.name


def test_student_portal_requires_student_role_active_enrollment_and_denies_admin_data(
    student_context: tuple[
        TestClient, Session, User, AcademicClass, Subject, Chapter
    ],
) -> None:
    client, db, student, _, _, _ = student_context

    assert client.get("/api/v1/student/dashboard").status_code == 200
    assert client.get("/api/v1/admin/questions").status_code == 403

    enrollment = db.query(StudentEnrollment).filter_by(student_id=student.id).one()
    enrollment.is_active = False
    db.commit()
    assert client.get("/api/v1/student/dashboard").status_code == 403

    client.headers.clear()
    assert client.get("/api/v1/student/dashboard").status_code == 401


def test_student_portal_rejects_accounts_without_student_role(
    student_context: tuple[
        TestClient, Session, User, AcademicClass, Subject, Chapter
    ],
) -> None:
    client, db, student, _, _, _ = student_context
    admin = User(
        school_id=student.school_id,
        full_name="School Admin",
        username="portal-admin",
        password_hash=hash_password("admin password"),
    )
    db.add(admin)
    db.flush()
    admin_role = db.query(Role).filter_by(name=RoleName.ADMIN).one()
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "portal-admin", "password": "admin password"},
    )
    assert login.status_code == 200
    response = client.get(
        "/api/v1/student/dashboard",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403

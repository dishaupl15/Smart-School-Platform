from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import Quiz, QuizAttempt
from app.models.enrollment import StudentEnrollment, TeacherAssignment
from app.models.enums import AttemptStatus, RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


@pytest.fixture
def teacher_context(
    auth_client: TestClient,
    db_session: Session,
) -> tuple[TestClient, Session, User, User, AcademicClass, AcademicClass, AcademicClass]:
    school = School(name="Teacher School", school_code=f"T-{uuid4().hex[:8]}")
    other_school = School(name="Other School", school_code=f"O-{uuid4().hex[:8]}")
    db_session.add_all([school, other_school])
    db_session.flush()

    def class_context(school_id, grade: int, name: str):
        academic_class = AcademicClass(
            school_id=school_id,
            name=name,
            grade_number=grade,
            academic_year="2026-27",
        )
        db_session.add(academic_class)
        db_session.flush()
        subject = (
            db_session.query(Subject).filter_by(school_id=school_id).one_or_none()
        )
        if subject is None:
            subject = Subject(
                school_id=school_id,
                name="Mathematics",
                code="MATH",
            )
            db_session.add(subject)
            db_session.flush()
        db_session.add(
            ClassSubject(
                class_id=academic_class.id,
                subject_id=subject.id,
                school_id=school_id,
            )
        )
        db_session.flush()
        chapter = Chapter(
            class_id=academic_class.id,
            subject_id=subject.id,
            chapter_number=1,
            title=f"{name} chapter",
        )
        db_session.add(chapter)
        db_session.flush()
        quiz = Quiz(
            class_id=academic_class.id,
            subject_id=subject.id,
            chapter_id=chapter.id,
            title=f"{name} quiz",
            total_questions=5,
        )
        db_session.add(quiz)
        db_session.flush()
        return academic_class, subject, quiz

    assigned_class, assigned_subject, assigned_quiz = class_context(
        school.id, 8, "Class 8"
    )
    unassigned_class, _, unassigned_quiz = class_context(
        school.id, 7, "Class 7"
    )
    foreign_class, _, foreign_quiz = class_context(
        other_school.id, 8, "Foreign Class"
    )

    teacher = User(
        school_id=school.id,
        full_name="Taylor Teacher",
        email="teacher@example.test",
        username="taylor",
        password_hash=hash_password("teacher password"),
    )
    assigned_student = User(
        school_id=school.id,
        full_name="Assigned Student",
        email="assigned@example.test",
        username="assigned",
        password_hash=hash_password("student password"),
    )
    unassigned_student = User(
        school_id=school.id,
        full_name="Unassigned Student",
        username="unassigned",
        password_hash=hash_password("student password"),
    )
    foreign_student = User(
        school_id=other_school.id,
        full_name="Foreign Student",
        username="foreign",
        password_hash=hash_password("student password"),
    )
    db_session.add_all(
        [teacher, assigned_student, unassigned_student, foreign_student]
    )
    db_session.flush()
    role_ids = {
        role.name: role.id for role in db_session.query(Role).all()
    }
    db_session.add_all(
        [
            UserRole(user_id=teacher.id, role_id=role_ids[RoleName.TEACHER]),
            UserRole(
                user_id=assigned_student.id,
                role_id=role_ids[RoleName.STUDENT],
            ),
            UserRole(
                user_id=unassigned_student.id,
                role_id=role_ids[RoleName.STUDENT],
            ),
            UserRole(
                user_id=foreign_student.id,
                role_id=role_ids[RoleName.STUDENT],
            ),
            StudentEnrollment(
                student_id=assigned_student.id,
                class_id=assigned_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
            StudentEnrollment(
                student_id=unassigned_student.id,
                class_id=unassigned_class.id,
                school_id=school.id,
                academic_year="2026-27",
            ),
            StudentEnrollment(
                student_id=foreign_student.id,
                class_id=foreign_class.id,
                school_id=other_school.id,
                academic_year="2026-27",
            ),
            TeacherAssignment(
                teacher_id=teacher.id,
                class_id=assigned_class.id,
                subject_id=assigned_subject.id,
                school_id=school.id,
                academic_year="2026-27",
                is_active=True,
            ),
        ]
    )
    db_session.flush()
    now = datetime.now(timezone.utc)

    def attempt(student, academic_class, quiz, status, attempt_number=1):
        completed = status == AttemptStatus.COMPLETED
        db_session.add(
            QuizAttempt(
                student_id=student.id,
                school_id=academic_class.school_id,
                quiz_id=quiz.id,
                class_id=academic_class.id,
                subject_id=quiz.subject_id,
                chapter_id=quiz.chapter_id,
                attempt_number=attempt_number,
                started_at=now,
                completed_at=now if completed else None,
                status=status,
                total_questions=5,
                correct_answers=4 if completed else 0,
                incorrect_answers=1 if completed else 0,
                unanswered_questions=0 if completed else 5,
                score=4 if completed else 0,
                percentage=Decimal("80.00") if completed else Decimal("0.00"),
            )
        )

    attempt(assigned_student, assigned_class, assigned_quiz, AttemptStatus.COMPLETED)
    attempt(
        assigned_student,
        assigned_class,
        assigned_quiz,
        AttemptStatus.IN_PROGRESS,
        attempt_number=2,
    )
    attempt(unassigned_student, unassigned_class, unassigned_quiz, AttemptStatus.COMPLETED)
    attempt(foreign_student, foreign_class, foreign_quiz, AttemptStatus.COMPLETED)
    db_session.commit()

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "taylor", "password": "teacher password"},
    )
    assert login.status_code == 200
    auth_client.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    yield (
        auth_client,
        db_session,
        teacher,
        assigned_student,
        assigned_class,
        unassigned_class,
        foreign_class,
    )
    auth_client.headers.clear()


def test_teacher_scope_is_limited_to_active_assignments_and_school(
    teacher_context,
) -> None:
    client, _, _, student, assigned_class, unassigned_class, foreign_class = (
        teacher_context
    )

    dashboard = client.get("/api/v1/teacher/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["assigned_class_count"] == 1
    assert dashboard.json()["student_count"] == 1
    assert dashboard.json()["completed_quiz_count"] == 1
    assert dashboard.json()["average_percentage"] == 80

    classes = client.get("/api/v1/teacher/classes")
    assert classes.status_code == 200
    assert [item["class_id"] for item in classes.json()] == [
        str(assigned_class.id)
    ]

    students = client.get("/api/v1/teacher/students")
    assert students.status_code == 200
    assert [item["student_id"] for item in students.json()] == [str(student.id)]
    assert client.get(
        f"/api/v1/teacher/classes/{unassigned_class.id}/students"
    ).status_code == 404
    assert client.get(
        f"/api/v1/teacher/classes/{foreign_class.id}/students"
    ).status_code == 404


def test_teacher_results_include_completed_attempts_only_and_deny_unassigned_student(
    teacher_context,
) -> None:
    client, _, _, student, _, unassigned_class, foreign_class = teacher_context

    results = client.get("/api/v1/teacher/results")
    assert results.status_code == 200
    assert results.json()["total_items"] == 1
    assert len(results.json()["items"]) == 1
    assert results.json()["items"][0]["student_id"] == str(student.id)
    assert results.json()["items"][0]["percentage"] == 80

    analytics = client.get("/api/v1/teacher/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["completed_quiz_count"] == 1

    for denied_class in (unassigned_class, foreign_class):
        assert client.get(
            "/api/v1/teacher/results",
            params={"class_id": str(denied_class.id)},
        ).status_code == 404
        assert client.get(
            f"/api/v1/teacher/students/{uuid4()}/performance",
            params={"class_id": str(denied_class.id)},
        ).status_code == 404


def test_student_performance_uses_only_the_assigned_class_context(
    teacher_context,
) -> None:
    client, _, _, student, assigned_class, _, _ = teacher_context

    response = client.get(
        f"/api/v1/teacher/students/{student.id}/performance",
        params={"class_id": str(assigned_class.id)},
    )
    assert response.status_code == 200
    assert response.json()["completed_quiz_count"] == 1
    assert response.json()["total_correct_answers"] == 4
    assert response.json()["recent_results"][0]["student_id"] == str(student.id)


def test_inactive_teacher_assignment_grants_no_class_or_results_access(
    teacher_context,
) -> None:
    client, db, teacher, _, _, _, _ = teacher_context
    assignment = (
        db.query(TeacherAssignment)
        .filter_by(teacher_id=teacher.id)
        .one()
    )
    assignment.is_active = False
    db.commit()

    assert client.get("/api/v1/teacher/classes").json() == []
    assert client.get("/api/v1/teacher/students").json() == []
    results = client.get("/api/v1/teacher/results")
    assert results.status_code == 200
    assert results.json()["total_items"] == 0


def test_student_role_cannot_access_teacher_portal(teacher_context) -> None:
    client, _, _, _, _, _, _ = teacher_context
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "assigned", "password": "student password"},
    )
    assert login.status_code == 200
    client.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"}
    )

    assert client.get("/api/v1/teacher/dashboard").status_code == 403

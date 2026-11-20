from uuid import uuid4
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


@pytest.fixture
def admin_context(
    auth_client: TestClient,
    db_session: Session,
) -> tuple[TestClient, Session, School, School, dict[str, str]]:
    school = School(name="North School", school_code=f"N-{uuid4().hex[:8]}")
    other_school = School(name="South School", school_code=f"S-{uuid4().hex[:8]}")
    db_session.add_all([school, other_school])
    db_session.flush()
    admin = User(
        school_id=school.id,
        full_name="School Admin",
        email="admin@example.test",
        username="admin",
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    admin_role = db_session.query(Role).filter_by(name=RoleName.ADMIN).one()
    db_session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    db_session.commit()
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return auth_client, db_session, school, other_school, headers


def create_class(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Class 8 - A",
    year: str = "2026-27",
    section: str = "A",
) -> dict:
    response = client.post(
        "/api/v1/admin/classes",
        headers=headers,
        json={
            "name": name,
            "grade_number": 8,
            "academic_year": year,
            "section": section,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_student(
    client: TestClient,
    headers: dict[str, str],
    class_id: str,
    identifier: str = "STU-1",
) -> dict:
    response = client.post(
        "/api/v1/admin/students",
        headers=headers,
        json={
            "full_name": "A Student",
            "student_identifier": identifier,
            "class_id": class_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_apis_require_admin_and_school_context(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    assert auth_client.get("/api/v1/admin/dashboard/stats").status_code == 401
    school = School(name="No Admin School", school_code=f"N-{uuid4().hex[:8]}")
    db_session.add(school)
    db_session.flush()
    admin = User(
        school_id=None,
        full_name="School-less Admin",
        username="global-admin",
        password_hash=hash_password("correct horse battery staple"),
    )
    db_session.add(admin)
    db_session.flush()
    role = db_session.query(Role).filter_by(name=RoleName.ADMIN).one()
    db_session.add(UserRole(user_id=admin.id, role_id=role.id))
    db_session.commit()
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": "global-admin", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    response = auth_client.get(
        "/api/v1/admin/dashboard/stats",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403


def test_students_are_created_with_role_enrollment_and_one_time_password(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, db, school, _, headers = admin_context
    academic_class = create_class(client, headers)
    created = create_student(client, headers, academic_class["id"])

    assert created["temporary_password"]
    assert "password_hash" not in created
    stored = db.query(User).filter_by(id=UUID(created["id"])).one()
    assert stored.password_hash != created["temporary_password"]
    roles = {
        row.role.name
        for row in db.query(UserRole).filter_by(user_id=stored.id).all()
    }
    assert roles == {RoleName.STUDENT}
    assert stored.school_id == school.id
    details = client.get(
        f"/api/v1/admin/students/{stored.id}",
        headers=headers,
    ).json()
    assert details["current_enrollment"]["class_id"] == academic_class["id"]
    assert details["current_enrollment"]["academic_year"] == "2026-27"


def test_students_support_search_pagination_update_and_deactivation(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, _, _, _, headers = admin_context
    academic_class = create_class(client, headers)
    first = create_student(client, headers, academic_class["id"], "STU-1")
    create_student(client, headers, academic_class["id"], "STU-2")

    listed = client.get(
        "/api/v1/admin/students?search=stu-1&page=1&page_size=1",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["identifier"] == "stu-1"

    updated = client.patch(
        f"/api/v1/admin/students/{first['id']}",
        headers=headers,
        json={"full_name": "Updated Student", "student_identifier": "STU-NEW"},
    )
    assert updated.status_code == 200
    assert updated.json()["identifier"] == "stu-new"
    deactivated = client.patch(
        f"/api/v1/admin/students/{first['id']}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False


def test_duplicate_student_identifier_and_bad_class_are_rejected(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, db, _, _, headers = admin_context
    academic_class = create_class(client, headers)
    create_student(client, headers, academic_class["id"], "same-id")
    duplicate = client.post(
        "/api/v1/admin/students",
        headers=headers,
        json={
            "full_name": "Duplicate",
            "student_identifier": "SAME-ID",
            "class_id": academic_class["id"],
        },
    )
    assert duplicate.status_code == 409
    assert db.query(User).filter(User.username == "same-id").count() == 1

    invalid = client.post(
        "/api/v1/admin/students",
        headers=headers,
        json={
            "full_name": "Invalid",
            "student_identifier": "new-id",
            "class_id": str(uuid4()),
        },
    )
    assert invalid.status_code == 404


def test_cross_school_student_records_are_not_disclosed(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, db, _, other_school, headers = admin_context
    student_role = db.query(Role).filter_by(name=RoleName.STUDENT).one()
    student = User(
        school_id=other_school.id,
        full_name="Private Student",
        username="private-1",
        password_hash=hash_password("not-used"),
    )
    db.add(student)
    db.flush()
    db.add(UserRole(user_id=student.id, role_id=student_role.id))
    db.commit()
    response = client.get(
        f"/api/v1/admin/students/{student.id}",
        headers=headers,
    )
    assert response.status_code == 404


def test_classes_subjects_and_chapters_validate_academic_context(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, _, _, _, headers = admin_context
    academic_class = create_class(client, headers)
    duplicate = client.post(
        "/api/v1/admin/classes",
        headers=headers,
        json={
            "name": "Duplicate class",
            "grade_number": 8,
            "academic_year": "2026-27",
            "section": "A",
        },
    )
    assert duplicate.status_code == 409

    subject_response = client.post(
        "/api/v1/admin/subjects",
        headers=headers,
        json={"name": "Mathematics", "code": "MATH"},
    )
    assert subject_response.status_code == 201
    subject = subject_response.json()
    assignment = client.post(
        f"/api/v1/admin/classes/{academic_class['id']}/subjects",
        headers=headers,
        json={"subject_id": subject["id"]},
    )
    assert assignment.status_code == 201
    assert assignment.json()["subjects"][0]["id"] == subject["id"]

    chapter = client.post(
        "/api/v1/admin/chapters",
        headers=headers,
        json={
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "chapter_number": 1,
            "title": "Numbers",
        },
    )
    assert chapter.status_code == 201
    invalid = client.post(
        "/api/v1/admin/chapters",
        headers=headers,
        json={
            "class_id": academic_class["id"],
            "subject_id": str(uuid4()),
            "chapter_number": 2,
            "title": "Invalid",
        },
    )
    assert invalid.status_code == 404
    not_assigned = client.post(
        "/api/v1/admin/chapters",
        headers=headers,
        json={
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "chapter_number": 1,
            "title": "Duplicate",
        },
    )
    assert not_assigned.status_code == 409


def test_teacher_provisioning_assignments_and_dashboard_counts(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, db, _, _, headers = admin_context
    academic_class = create_class(client, headers)
    subject = client.post(
        "/api/v1/admin/subjects",
        headers=headers,
        json={"name": "Science", "code": "SCI"},
    ).json()
    assert client.post(
        f"/api/v1/admin/classes/{academic_class['id']}/subjects",
        headers=headers,
        json={"subject_id": subject["id"]},
    ).status_code == 201
    teacher_response = client.post(
        "/api/v1/admin/teachers",
        headers=headers,
        json={
            "full_name": "A Teacher",
            "teacher_identifier": "T-1",
            "email": "teacher@example.test",
        },
    )
    assert teacher_response.status_code == 201
    teacher = teacher_response.json()
    assert teacher["temporary_password"]
    assert "password_hash" not in teacher
    assignment = client.post(
        "/api/v1/admin/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": teacher["id"],
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "academic_year": "2026-27",
        },
    )
    assert assignment.status_code == 201, assignment.text
    duplicate = client.post(
        "/api/v1/admin/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": teacher["id"],
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "academic_year": "2026-27",
        },
    )
    assert duplicate.status_code == 409
    assert client.get(
        f"/api/v1/admin/teachers?class_id={academic_class['id']}",
        headers=headers,
    ).json()["total"] == 1
    stats = client.get("/api/v1/admin/dashboard/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["active_teachers"] == 1
    assert stats.json()["classes"] == 1
    assert stats.json()["subjects"] == 1
    assert db.query(User).filter_by(username="t-1").one().password_hash != teacher["temporary_password"]


def test_enrollment_transfers_preserve_history_and_allow_returning_to_class(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, _, _, _, headers = admin_context
    class_a = create_class(client, headers, name="Class 8 A", section="A")
    class_b = create_class(client, headers, name="Class 8 B", section="B")
    student = create_student(client, headers, class_a["id"])
    enrollment = client.get(
        f"/api/v1/admin/enrollments?student_id={student['id']}",
        headers=headers,
    ).json()["items"][0]

    transferred = client.post(
        f"/api/v1/admin/enrollments/{enrollment['id']}/transfer",
        headers=headers,
        json={"target_class_id": class_b["id"]},
    )
    assert transferred.status_code == 201, transferred.text
    returned = client.post(
        f"/api/v1/admin/enrollments/{transferred.json()['id']}/transfer",
        headers=headers,
        json={"target_class_id": class_a["id"]},
    )
    assert returned.status_code == 201, returned.text

    history = client.get(
        f"/api/v1/admin/students/{student['id']}",
        headers=headers,
    ).json()["enrollments"]
    assert len(history) == 3
    assert sum(item["is_active"] for item in history) == 1


def test_invalid_teacher_subject_assignment_and_inactive_class_are_rejected(
    admin_context: tuple[TestClient, Session, School, School, dict[str, str]],
) -> None:
    client, _, _, _, headers = admin_context
    academic_class = create_class(client, headers)
    subject = client.post(
        "/api/v1/admin/subjects",
        headers=headers,
        json={"name": "History", "code": "HIST"},
    ).json()
    teacher = client.post(
        "/api/v1/admin/teachers",
        headers=headers,
        json={
            "full_name": "Teacher",
            "teacher_identifier": "T-HIST",
            "email": "teacher-history@example.test",
        },
    ).json()
    active_class = create_class(
        client,
        headers,
        name="Class 8 B",
        section="B",
    )
    student = create_student(client, headers, active_class["id"], "INACTIVE-CLASS-STUDENT")
    invalid = client.post(
        "/api/v1/admin/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": teacher["id"],
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "academic_year": "2026-27",
        },
    )
    assert invalid.status_code == 400
    deactivated = client.patch(
        f"/api/v1/admin/classes/{academic_class['id']}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    enrollment = client.post(
        "/api/v1/admin/enrollments",
        headers=headers,
        json={
            "student_id": student["id"],
            "class_id": academic_class["id"],
            "academic_year": "2026-27",
        },
    )
    assert enrollment.status_code == 404

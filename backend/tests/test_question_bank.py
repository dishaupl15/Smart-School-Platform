import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import AttemptQuestion, Quiz, QuizAttempt, StudentAnswer
from app.models.enums import AttemptStatus, LanguageCode, RoleName
from app.models.question import Question, QuestionOption
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User
from app.services.question_bank import (
    IMPORT_COLUMNS,
    MAX_IMPORT_ROWS,
    import_report_csv,
)


def _admin(
    auth_client: TestClient,
    db: Session,
    *,
    school: School | None = None,
) -> tuple[dict[str, str], User]:
    school = school or School(name="Question School", school_code=f"Q-{uuid4().hex[:8]}")
    db.add(school)
    db.flush()
    user = User(
        school_id=school.id,
        full_name="Question Admin",
        email=f"{uuid4().hex}@example.test",
        username=f"qa-{uuid4().hex[:10]}",
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    admin_role = db.query(Role).filter_by(name=RoleName.ADMIN).one()
    db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"identifier": user.username, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user


def _academic_context(
    client: TestClient,
    headers: dict[str, str],
    *,
    class_id: str | None = None,
    subject_id: str | None = None,
) -> tuple[dict, dict, dict]:
    academic_class = (
        client.get(f"/api/v1/admin/classes/{class_id}", headers=headers).json()
        if class_id
        else client.post(
            "/api/v1/admin/classes",
            headers=headers,
            json={
                "name": f"Class {uuid4().hex[:4]}",
                "grade_number": 8,
                "academic_year": "2026-27",
                "section": "A",
            },
        ).json()
    )
    if not class_id:
        assert academic_class["id"]
    subject = (
        client.get(f"/api/v1/admin/subjects/{subject_id}", headers=headers).json()
        if subject_id
        else client.post(
            "/api/v1/admin/subjects",
            headers=headers,
            json={"name": f"Science {uuid4().hex[:4]}", "code": f"S{uuid4().hex[:6]}"},
        ).json()
    )
    if not subject_id:
        assert subject["id"]
        response = client.post(
            f"/api/v1/admin/classes/{academic_class['id']}/subjects",
            headers=headers,
            json={"subject_id": subject["id"]},
        )
        assert response.status_code == 201, response.text
    chapter = client.post(
        "/api/v1/admin/chapters",
        headers=headers,
        json={
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "chapter_number": 1,
            "title": f"Chapter {uuid4().hex[:4]}",
        },
    )
    assert chapter.status_code == 201, chapter.text
    return academic_class, subject, chapter.json()


def _payload(class_id: str, subject_id: str, chapter_id: str, *, all_languages: bool = True) -> dict:
    languages = ["en", "hi", "mr"] if all_languages else ["en"]
    translations = [
        {
            "language_code": language,
            "question_text": {
                "en": "What is 2 + 2?",
                "hi": "दो और दो कितने होते हैं?",
                "mr": "दोन अधिक दोन किती?",
            }[language],
            "explanation": {"en": "Add the numbers.", "hi": "संख्याएँ जोड़ें।", "mr": "संख्या जोडा."}[language],
        }
        for language in languages
    ]
    return {
        "class_id": class_id,
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "difficulty": "EASY",
        "translations": translations,
        "options": [
            {
                "option_key": key,
                "display_order": order,
                "is_correct": key == "B",
                "translations": [
                    {
                        "language_code": language,
                        "option_text": f"answer {key.lower()} ({language})",
                    }
                    for language in languages
                ],
            }
            for order, key in enumerate(("A", "B", "C", "D"), start=1)
        ],
    }


def _import_csv(class_id: str, subject_id: str, chapter_id: str, *, include_blank_row: bool = False) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=IMPORT_COLUMNS)
    writer.writeheader()
    row = {column: "" for column in IMPORT_COLUMNS}
    row.update(
        {
            "class_id": class_id,
            "subject_id": subject_id,
            "chapter_id": chapter_id,
            "difficulty": "MEDIUM",
            "question_en": "How many sides does a triangle have?",
            "option_a_en": "Two",
            "option_b_en": "Three",
            "option_c_en": "Four",
            "option_d_en": "Five",
            "correct_option": "B",
        }
    )
    writer.writerow(row)
    if include_blank_row:
        invalid = {column: "" for column in IMPORT_COLUMNS}
        invalid.update(
            {
                "class_id": class_id,
                "subject_id": subject_id,
                "chapter_id": chapter_id,
                "difficulty": "EASY",
                "correct_option": "A",
            }
        )
        writer.writerow(invalid)
    return output.getvalue().encode("utf-8")


def test_question_crud_filter_paging_stats_and_school_scope(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, _ = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    payload = _payload(academic_class["id"], subject["id"], chapter["id"])
    created = auth_client.post("/api/v1/admin/questions", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    question = created.json()
    assert question["status"] == "DRAFT"
    assert len(question["options"]) == 4
    assert sum(option["is_correct"] for option in question["options"]) == 1

    listed = auth_client.get(
        "/api/v1/admin/questions?search=2%20%2B%202&status=DRAFT&page=1&page_size=1",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == question["id"]
    assert auth_client.get(f"/api/v1/admin/questions/{question['id']}").status_code == 401

    stats = auth_client.get("/api/v1/admin/questions/stats", headers=headers)
    assert {
        key: stats.json()[key]
        for key in ("total", "draft", "review", "approved", "archived")
    } == {"total": 1, "draft": 1, "review": 0, "approved": 0, "archived": 0}
    assert stats.json()["by_subject"][0]["subject_id"] == subject["id"]
    assert auth_client.get(
        "/api/v1/admin/question-bank/stats", headers=headers
    ).json()["total"] == 1
    review = auth_client.patch(
        f"/api/v1/admin/questions/{question['id']}/status",
        headers=headers,
        json={"status": "REVIEW"},
    )
    assert review.status_code == 200, review.text
    approved = auth_client.patch(
        f"/api/v1/admin/questions/{question['id']}/status",
        headers=headers,
        json={"status": "APPROVED"},
    )
    assert approved.status_code == 200, approved.text
    archived = auth_client.post(
        f"/api/v1/admin/questions/{question['id']}/archive", headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"


def test_approval_requires_all_translations_four_options_and_one_correct(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, _ = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    payload = _payload(academic_class["id"], subject["id"], chapter["id"], all_languages=False)
    payload["options"] = payload["options"][:3]
    created = auth_client.post("/api/v1/admin/questions", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    review = auth_client.patch(
        f"/api/v1/admin/questions/{created.json()['id']}/status",
        headers=headers,
        json={"status": "REVIEW"},
    )
    assert review.status_code == 422

    english_only = _payload(academic_class["id"], subject["id"], chapter["id"], all_languages=False)
    english_only["translations"][0]["question_text"] = "English-only translated question."
    english_question = auth_client.post(
        "/api/v1/admin/questions", headers=headers, json=english_only
    )
    assert english_question.status_code == 201, english_question.text
    review = auth_client.patch(
        f"/api/v1/admin/questions/{english_question.json()['id']}/status",
        headers=headers,
        json={"status": "REVIEW"},
    )
    assert review.status_code == 200
    approval = auth_client.patch(
        f"/api/v1/admin/questions/{english_question.json()['id']}/status",
        headers=headers,
        json={"status": "APPROVED"},
    )
    assert approval.status_code == 422

    draft = auth_client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={
            **_payload(academic_class["id"], subject["id"], chapter["id"]),
            "translations": [
                {
                    **translation,
                    "question_text": f"Different prompt {translation['language_code']}",
                }
                for translation in _payload(
                    academic_class["id"], subject["id"], chapter["id"]
                )["translations"]
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    approved_directly = auth_client.patch(
        f"/api/v1/admin/questions/{draft.json()['id']}/status",
        headers=headers,
        json={"status": "APPROVED"},
    )
    assert approved_directly.status_code == 409


def test_option_edits_preserve_historical_option_ids(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, admin = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    created = auth_client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json=_payload(academic_class["id"], subject["id"], chapter["id"]),
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    original_ids = {
        option["option_key"]: option["id"] for option in created.json()["options"]
    }

    updated_payload = {
        "options": [
            {
                "option_key": option["option_key"],
                "display_order": 5 - option["display_order"],
                "is_correct": option["is_correct"],
                "translations": [
                    {
                        "language_code": translation["language_code"],
                        "option_text": f"Updated {translation['option_text']}",
                    }
                    for translation in option["translations"]
                ],
            }
            for option in created.json()["options"]
        ]
    }
    updated = auth_client.patch(
        f"/api/v1/admin/questions/{question_id}",
        headers=headers,
        json=updated_payload,
    )
    assert updated.status_code == 200, updated.text
    assert {
        option["option_key"]: option["id"] for option in updated.json()["options"]
    } == original_ids

    question = db_session.query(Question).filter_by(id=UUID(question_id)).one()
    options_by_key = {
        option.option_key: option for option in question.options
    }
    quiz = Quiz(
        class_id=UUID(academic_class["id"]),
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
        title="Historical option test",
        total_questions=1,
    )
    db_session.add(quiz)
    db_session.flush()
    attempt = QuizAttempt(
        student_id=admin.id,
        school_id=admin.school_id,
        quiz_id=quiz.id,
        class_id=UUID(academic_class["id"]),
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
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
        class_id=UUID(academic_class["id"]),
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
        display_order=1,
        selected_language=LanguageCode.EN,
        question_text_snapshot="Snapshot",
        question_snapshot={"text": "Snapshot"},
        option_order_snapshot=[],
    )
    db_session.add(attempt_question)
    db_session.flush()
    db_session.add(
        StudentAnswer(
            attempt_question_id=attempt_question.id,
            question_id=question.id,
            selected_option_id=options_by_key["A"].id,
            answered_at=datetime.now(timezone.utc),
            is_correct=None,
        )
    )
    db_session.commit()

    removal_payload = {
        "options": [
            option
            for option in updated_payload["options"]
            if option["option_key"] != "A"
        ]
    }
    rejected = auth_client.patch(
        f"/api/v1/admin/questions/{question_id}",
        headers=headers,
        json=removal_payload,
    )
    assert rejected.status_code == 409
    assert "historical answers" in rejected.json()["detail"]
    assert db_session.query(QuestionOption).filter_by(id=options_by_key["A"].id).one()


def test_duplicates_cross_school_context_and_archive_workflow(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, _ = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    payload = _payload(academic_class["id"], subject["id"], chapter["id"])
    created = auth_client.post("/api/v1/admin/questions", headers=headers, json=payload)
    assert created.status_code == 201
    duplicate = auth_client.post("/api/v1/admin/questions", headers=headers, json=payload)
    assert duplicate.status_code == 409
    copied = auth_client.post(
        f"/api/v1/admin/questions/{created.json()['id']}/duplicate", headers=headers
    )
    assert copied.status_code == 201, copied.text
    assert copied.json()["status"] == "DRAFT"
    assert copied.json()["id"] != created.json()["id"]

    other_school = School(name="Other School", school_code=f"OS-{uuid4().hex[:8]}")
    db_session.add(other_school)
    db_session.flush()
    other_class = AcademicClass(
        school_id=other_school.id,
        name="Other Class",
        grade_number=8,
        academic_year="2026-27",
        section="A",
    )
    other_subject = Subject(
        school_id=other_school.id,
        name="Other Subject",
        code=f"O-{uuid4().hex[:6]}",
    )
    db_session.add_all([other_class, other_subject])
    db_session.flush()
    db_session.add(ClassSubject(class_id=other_class.id, subject_id=other_subject.id, school_id=other_school.id))
    db_session.flush()
    other_chapter = Chapter(
        class_id=other_class.id,
        subject_id=other_subject.id,
        chapter_number=1,
        title="Other Chapter",
    )
    db_session.add(other_chapter)
    db_session.commit()
    cross_school = _payload(str(other_class.id), str(other_subject.id), str(other_chapter.id))
    response = auth_client.post("/api/v1/admin/questions", headers=headers, json=cross_school)
    assert response.status_code == 422
    other_headers, _ = _admin(auth_client, db_session, school=other_school)
    assert auth_client.get(
        f"/api/v1/admin/questions/{created.json()['id']}",
        headers=other_headers,
    ).status_code == 404

    assert auth_client.post(
        f"/api/v1/admin/questions/{created.json()['id']}/archive",
        headers=headers,
    ).status_code == 200


def test_csv_import_preview_has_no_database_writes_and_valid_rows_confirm(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, _ = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    before = db_session.query(Question).count()
    response = auth_client.post(
        "/api/v1/admin/questions/import/preview",
        headers=headers,
        files={
            "file": (
                "questions.csv",
                _import_csv(
                    academic_class["id"],
                    subject["id"],
                    chapter["id"],
                    include_blank_row=True,
                ),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 1
    assert preview["invalid_rows"] == 1
    assert preview["rows"][0]["question"]
    assert any("question translation is missing for hi" in warning.lower() for warning in preview["rows"][0]["warnings"])
    assert any("option a translation is missing for mr" in warning.lower() for warning in preview["rows"][0]["warnings"])
    assert preview["rows"][1]["valid"] is False
    assert db_session.query(Question).count() == before

    confirmed = auth_client.post(
        "/api/v1/admin/questions/import/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "mode": "valid_rows"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["committed_rows"] == 1
    assert db_session.query(Question).count() == before + 1
    report = auth_client.get(
        f"/api/v1/admin/questions/import/report/{preview['import_id']}",
        headers=headers,
    )
    assert report.status_code == 200
    assert "question_id" in report.text
    csv_report = auth_client.get(
        f"/api/v1/admin/questions/imports/{preview['import_id']}/report/download",
        headers=headers,
    )
    assert csv_report.status_code == 200
    assert "warnings" in csv_report.text
    assert auth_client.post(
        "/api/v1/admin/questions/import/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "mode": "valid_rows"},
    ).status_code == 409
    other_headers, _ = _admin(auth_client, db_session)
    assert auth_client.get(
        f"/api/v1/admin/questions/import/report/{preview['import_id']}",
        headers=other_headers,
    ).status_code == 404


def test_import_report_neutralizes_formulas_in_all_user_fields() -> None:
    report = import_report_csv(
        {
            "rows": [
                {
                    "row_number": 2,
                    "valid": False,
                    "status": "invalid",
                    "question_preview": ' =HYPERLINK("https://example.test")',
                    "question_id": None,
                    "errors": ["+SUM(1,1)"],
                    "warnings": ["@bad"],
                }
            ]
        }
    ).decode("utf-8-sig")
    assert "' =HYPERLINK" in report
    assert "'+SUM(1,1)" in report
    assert "'@bad" in report


def test_atomic_import_and_xlsx_template(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    headers, _ = _admin(auth_client, db_session)
    academic_class, subject, chapter = _academic_context(auth_client, headers)
    before = db_session.query(Question).count()
    preview = auth_client.post(
        "/api/v1/admin/questions/import/preview",
        headers=headers,
        files={
            "file": (
                "questions.csv",
                _import_csv(
                    academic_class["id"],
                    subject["id"],
                    chapter["id"],
                    include_blank_row=True,
                ),
                "text/csv",
            )
        },
    ).json()
    confirmed = auth_client.post(
        "/api/v1/admin/questions/import/confirm",
        headers=headers,
        json={"import_id": preview["import_id"], "mode": "all_or_nothing"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["rejected_atomic"] is True
    assert confirmed.json()["rejected"] == 2
    assert confirmed.json()["committed_rows"] == 0
    assert db_session.query(Question).count() == before

    template = auth_client.get(
        "/api/v1/admin/questions/import/template?format=xlsx", headers=headers
    )
    assert template.status_code == 200
    assert template.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    xlsx = Workbook()
    sheet = xlsx.active
    sheet.append(IMPORT_COLUMNS)
    row = {column: "" for column in IMPORT_COLUMNS}
    row.update(
        {
            "class_id": academic_class["id"],
            "subject_id": subject["id"],
            "chapter_id": chapter["id"],
            "difficulty": "EASY",
            "question_en": "What is 5 + 5?",
            "option_a_en": "Eight",
            "option_b_en": "Ten",
            "option_c_en": "Eleven",
            "option_d_en": "Twelve",
            "correct_option": "B",
        }
    )
    sheet.append([row[column] for column in IMPORT_COLUMNS])
    output = BytesIO()
    xlsx.save(output)
    xlsx.close()
    xlsx_preview = auth_client.post(
        "/api/v1/admin/questions/imports/preview",
        headers=headers,
        files={
            "file": (
                "questions.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert xlsx_preview.status_code == 200, xlsx_preview.text
    assert xlsx_preview.json()["valid_rows"] == 1
    xlsx_confirm = auth_client.post(
        f"/api/v1/admin/questions/imports/{xlsx_preview.json()['import_id']}/confirm",
        headers=headers,
        json={"mode": "valid_rows"},
    )
    assert xlsx_confirm.status_code == 200, xlsx_confirm.text
    assert xlsx_confirm.json()["inserted"] == 1

    oversized = Workbook()
    oversized.active.cell(row=MAX_IMPORT_ROWS + 2, column=1, value="sparse row")
    oversized_output = BytesIO()
    oversized.save(oversized_output)
    oversized.close()
    rejected_xlsx = auth_client.post(
        "/api/v1/admin/questions/import/preview",
        headers=headers,
        files={
            "file": (
                "oversized.xlsx",
                oversized_output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert rejected_xlsx.status_code == 422
    assert "at most 500 data rows" in rejected_xlsx.json()["detail"]


def test_question_routes_require_authentication(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/admin/questions").status_code == 401
    assert auth_client.get("/api/v1/admin/questions/stats").status_code == 401

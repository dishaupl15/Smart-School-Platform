from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import require_student
from app.db.session import get_db
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import Quiz, QuizAttempt
from app.models.enrollment import StudentEnrollment
from app.models.enums import AttemptStatus
from app.models.school import School
from app.models.user import User
from app.schemas.student import (
    StudentChapterDetail,
    StudentDashboard,
    StudentEnrollmentChoice,
    StudentProfile,
    StudentSubjectDetail,
    StudentSubjectSummary,
)

router = APIRouter()


def _active_enrollment(
    db: Session,
    student: User,
    class_id: UUID | None = None,
) -> tuple[StudentEnrollment, AcademicClass, School]:
    if student.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active enrollment is required to access the student portal.",
        )
    result = db.execute(
        select(StudentEnrollment, AcademicClass, School)
        .join(AcademicClass, AcademicClass.id == StudentEnrollment.class_id)
        .join(School, School.id == StudentEnrollment.school_id)
        .where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.school_id == student.school_id,
            StudentEnrollment.is_active.is_(True),
            StudentEnrollment.academic_year == AcademicClass.academic_year,
            AcademicClass.school_id == student.school_id,
            AcademicClass.is_active.is_(True),
            *(
                (StudentEnrollment.class_id == class_id,)
                if class_id is not None
                else ()
            ),
        )
        .order_by(
            StudentEnrollment.academic_year.desc(),
            StudentEnrollment.created_at.desc(),
        )
        .limit(1)
    ).first()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active enrollment is required to access the student portal.",
        )
    return result


def _enrollment_summary(
    enrollment: StudentEnrollment,
    academic_class: AcademicClass,
) -> dict[str, Any]:
    return {
        "class_name": academic_class.name,
        "class_id": academic_class.id,
        "grade_number": academic_class.grade_number,
        "section": academic_class.section,
        "academic_year": enrollment.academic_year,
    }


def _student_profile(
    student: User,
    school: School,
    enrollment: StudentEnrollment,
    academic_class: AcademicClass,
) -> dict[str, Any]:
    return {
        "full_name": student.full_name,
        "identifier": student.username or "",
        "email": student.email,
        "phone": student.phone,
        "school_name": school.name,
        "enrollment": _enrollment_summary(enrollment, academic_class),
    }


@router.get("/enrollments", response_model=list[StudentEnrollmentChoice])
def list_active_enrollments(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if student.school_id is None:
        return []
    records = db.execute(
        select(StudentEnrollment, AcademicClass)
        .join(AcademicClass, AcademicClass.id == StudentEnrollment.class_id)
        .where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.school_id == student.school_id,
            StudentEnrollment.is_active.is_(True),
            StudentEnrollment.academic_year == AcademicClass.academic_year,
            AcademicClass.school_id == student.school_id,
            AcademicClass.is_active.is_(True),
        )
        .order_by(
            StudentEnrollment.academic_year.desc(),
            StudentEnrollment.created_at.desc(),
        )
    ).all()
    return [
        _enrollment_summary(enrollment, academic_class)
        for enrollment, academic_class in records
    ]


def _subject_records(
    db: Session,
    school_id: UUID,
    class_id: UUID,
) -> Sequence[tuple[Subject, int]]:
    return db.execute(
        select(Subject, func.count(Chapter.id))
        .join(
            ClassSubject,
            (ClassSubject.subject_id == Subject.id)
            & (ClassSubject.class_id == class_id)
            & (ClassSubject.school_id == school_id),
        )
        .outerjoin(
            Chapter,
            (Chapter.subject_id == Subject.id)
            & (Chapter.class_id == class_id)
            & (Chapter.is_active.is_(True)),
        )
        .where(
            Subject.school_id == school_id,
            Subject.is_active.is_(True),
        )
        .group_by(Subject.id)
        .order_by(Subject.name)
    ).all()


def _subject_summary(subject: Subject, chapter_count: int) -> dict[str, Any]:
    return {
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "description": subject.description,
        "chapter_count": chapter_count,
    }


def _chapter_quiz_availability(
    db: Session,
    class_id: UUID,
    chapter_ids: list[UUID],
) -> dict[UUID, bool]:
    if not chapter_ids:
        return {}
    available_ids = db.execute(
        select(Quiz.chapter_id)
        .where(
            Quiz.class_id == class_id,
            Quiz.chapter_id.in_(chapter_ids),
            Quiz.is_active.is_(True),
        )
        .distinct()
    ).scalars()
    return {chapter_id: True for chapter_id in available_ids}


def _recent_activity(
    db: Session,
    student_id: UUID,
    school_id: UUID,
    class_id: UUID,
) -> tuple[int, list[dict[str, Any]]]:
    completed_filter = (
        QuizAttempt.student_id == student_id,
        QuizAttempt.school_id == school_id,
        QuizAttempt.class_id == class_id,
        QuizAttempt.status == AttemptStatus.COMPLETED,
    )
    completed_count = db.execute(
        select(func.count(QuizAttempt.id)).where(*completed_filter)
    ).scalar_one()
    recent_records = db.execute(
        select(QuizAttempt, Quiz, Subject, Chapter)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Subject, Subject.id == QuizAttempt.subject_id)
        .join(Chapter, Chapter.id == QuizAttempt.chapter_id)
        .where(*completed_filter)
        .order_by(QuizAttempt.completed_at.desc())
        .limit(5)
    ).all()
    return completed_count, [
        {
            "attempt_id": attempt.id,
            "title": quiz.title,
            "subject_name": subject.name,
            "chapter_title": chapter.title,
            "score": attempt.score,
            "total_questions": attempt.total_questions,
            "percentage": float(attempt.percentage),
            "completed_at": attempt.completed_at,
        }
        for attempt, quiz, subject, chapter in recent_records
        if attempt.completed_at is not None
    ]


def _active_chapters(
    db: Session,
    class_id: UUID,
    subject_id: UUID,
) -> list[Chapter]:
    return list(
        db.execute(
            select(Chapter)
            .where(
                Chapter.class_id == class_id,
                Chapter.subject_id == subject_id,
                Chapter.is_active.is_(True),
            )
            .order_by(Chapter.chapter_number, Chapter.title)
        ).scalars()
    )


@router.get("/profile", response_model=StudentProfile)
def get_profile(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    enrollment, academic_class, school = _active_enrollment(db, student)
    return _student_profile(student, school, enrollment, academic_class)


@router.get("/dashboard", response_model=StudentDashboard)
def get_dashboard(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    enrollment, academic_class, school = _active_enrollment(db, student)
    subjects = [
        _subject_summary(subject, chapter_count)
        for subject, chapter_count in _subject_records(
            db,
            student.school_id,
            academic_class.id,
        )
    ]
    completed_quiz_count, recent_activity = _recent_activity(
        db,
        student.id,
        student.school_id,
        academic_class.id,
    )
    return {
        "student_name": student.full_name,
        "school_name": school.name,
        "enrollment": _enrollment_summary(enrollment, academic_class),
        "subject_count": len(subjects),
        "chapter_count": sum(subject["chapter_count"] for subject in subjects),
        "subjects": subjects,
        "completed_quiz_count": completed_quiz_count,
        "recent_activity": recent_activity,
    }


@router.get("/subjects", response_model=list[StudentSubjectSummary])
def list_subjects(
    class_id: UUID | None = Query(default=None),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    _, academic_class, _ = _active_enrollment(db, student, class_id)
    return [
        _subject_summary(subject, chapter_count)
        for subject, chapter_count in _subject_records(
            db,
            student.school_id,
            academic_class.id,
        )
    ]


@router.get("/subjects/{subject_id}", response_model=StudentSubjectDetail)
def get_subject(
    subject_id: UUID,
    class_id: UUID | None = Query(default=None),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, academic_class, _ = _active_enrollment(db, student, class_id)
    record = db.execute(
        select(Subject)
        .join(
            ClassSubject,
            (ClassSubject.subject_id == Subject.id)
            & (ClassSubject.class_id == academic_class.id)
            & (ClassSubject.school_id == student.school_id),
        )
        .where(
            Subject.id == subject_id,
            Subject.school_id == student.school_id,
            Subject.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    chapters = _active_chapters(db, academic_class.id, record.id)
    quiz_availability = _chapter_quiz_availability(
        db,
        academic_class.id,
        [chapter.id for chapter in chapters],
    )
    return {
        **_subject_summary(record, len(chapters)),
        "chapters": [
            {
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "description": chapter.description,
                "has_available_quiz": quiz_availability.get(chapter.id, False),
            }
            for chapter in chapters
        ],
    }


@router.get("/chapters/{chapter_id}", response_model=StudentChapterDetail)
def get_chapter(
    chapter_id: UUID,
    class_id: UUID | None = Query(default=None),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, academic_class, _ = _active_enrollment(db, student, class_id)
    record = db.execute(
        select(Chapter, Subject)
        .join(Subject, Subject.id == Chapter.subject_id)
        .join(
            ClassSubject,
            (ClassSubject.subject_id == Subject.id)
            & (ClassSubject.class_id == academic_class.id)
            & (ClassSubject.school_id == student.school_id),
        )
        .where(
            Chapter.id == chapter_id,
            Chapter.class_id == academic_class.id,
            Chapter.is_active.is_(True),
            Subject.school_id == student.school_id,
            Subject.is_active.is_(True),
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    chapter, subject = record
    return {
        "id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "description": chapter.description,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "class_name": academic_class.name,
        "has_available_quiz": _chapter_quiz_availability(
            db,
            academic_class.id,
            [chapter.id],
        ).get(chapter.id, False),
    }

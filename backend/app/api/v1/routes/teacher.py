from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import require_teacher
from app.db.session import get_db
from app.models.academic import AcademicClass, Chapter, Subject
from app.models.assessment import Quiz, QuizAttempt
from app.models.enrollment import StudentEnrollment, TeacherAssignment
from app.models.enums import AttemptStatus, RoleName
from app.models.role import Role, UserRole
from app.models.user import User
from app.schemas.teacher import (
    TeacherAnalytics,
    TeacherChapterPerformance,
    TeacherClassItem,
    TeacherDashboard,
    TeacherQuizResult,
    TeacherResultsPage,
    TeacherStudentItem,
    TeacherStudentPerformance,
    TeacherSubjectPerformance,
)

router = APIRouter()


def _assignment_contexts(db: Session, teacher: User):
    if teacher.school_id is None:
        return []
    return list(
        db.execute(
            select(TeacherAssignment, AcademicClass, Subject)
            .join(
                AcademicClass,
                and_(
                    AcademicClass.id == TeacherAssignment.class_id,
                    AcademicClass.school_id == TeacherAssignment.school_id,
                ),
            )
            .join(
                Subject,
                and_(
                    Subject.id == TeacherAssignment.subject_id,
                    Subject.school_id == TeacherAssignment.school_id,
                ),
            )
            .where(
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.school_id == teacher.school_id,
                TeacherAssignment.is_active.is_(True),
                AcademicClass.is_active.is_(True),
                Subject.is_active.is_(True),
            )
            .order_by(
                TeacherAssignment.academic_year.desc(),
                AcademicClass.grade_number,
                AcademicClass.name,
                Subject.name,
            )
        ).all()
    )


def _student_contexts(
    db: Session,
    teacher: User,
    *,
    class_id: UUID | None = None,
    student_id: UUID | None = None,
):
    if teacher.school_id is None:
        return []
    statement = (
        select(User, AcademicClass, StudentEnrollment)
        .join(
            StudentEnrollment,
            and_(
                StudentEnrollment.student_id == User.id,
                StudentEnrollment.school_id == User.school_id,
            ),
        )
        .join(
            AcademicClass,
            and_(
                AcademicClass.id == StudentEnrollment.class_id,
                AcademicClass.school_id == StudentEnrollment.school_id,
                AcademicClass.academic_year == StudentEnrollment.academic_year,
            ),
        )
        .join(
            TeacherAssignment,
            and_(
                TeacherAssignment.class_id == StudentEnrollment.class_id,
                TeacherAssignment.school_id == StudentEnrollment.school_id,
                TeacherAssignment.academic_year == StudentEnrollment.academic_year,
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.is_active.is_(True),
            ),
        )
        .join(
            Subject,
            and_(
                Subject.id == TeacherAssignment.subject_id,
                Subject.school_id == TeacherAssignment.school_id,
                Subject.is_active.is_(True),
            ),
        )
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.school_id == teacher.school_id,
            User.is_active.is_(True),
            StudentEnrollment.school_id == teacher.school_id,
            StudentEnrollment.is_active.is_(True),
            AcademicClass.is_active.is_(True),
            Role.name == RoleName.STUDENT,
        )
        .distinct()
    )
    if class_id is not None:
        statement = statement.where(AcademicClass.id == class_id)
    if student_id is not None:
        statement = statement.where(User.id == student_id)
    return list(
        db.execute(
            statement.order_by(
                AcademicClass.academic_year.desc(),
                AcademicClass.grade_number,
                AcademicClass.name,
                User.full_name,
            )
        ).all()
    )


def _attempt_statement(teacher: User):
    return (
        select(QuizAttempt, User, AcademicClass, Subject, Chapter, Quiz)
        .select_from(QuizAttempt)
        .join(
            AcademicClass,
            and_(
                AcademicClass.id == QuizAttempt.class_id,
                AcademicClass.school_id == QuizAttempt.school_id,
            ),
        )
        .join(
            TeacherAssignment,
            and_(
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.school_id == teacher.school_id,
                TeacherAssignment.class_id == QuizAttempt.class_id,
                TeacherAssignment.subject_id == QuizAttempt.subject_id,
                TeacherAssignment.academic_year
                == AcademicClass.academic_year,
                TeacherAssignment.is_active.is_(True),
            ),
        )
        .join(
            Subject,
            and_(
                Subject.id == QuizAttempt.subject_id,
                Subject.school_id == QuizAttempt.school_id,
            ),
        )
        .join(
            Chapter,
            and_(
                Chapter.id == QuizAttempt.chapter_id,
                Chapter.class_id == QuizAttempt.class_id,
                Chapter.subject_id == QuizAttempt.subject_id,
            ),
        )
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(
            User,
            and_(
                User.id == QuizAttempt.student_id,
                User.school_id == QuizAttempt.school_id,
            ),
        )
        .join(
            StudentEnrollment,
            and_(
                StudentEnrollment.student_id == QuizAttempt.student_id,
                StudentEnrollment.school_id == QuizAttempt.school_id,
                StudentEnrollment.class_id == QuizAttempt.class_id,
                StudentEnrollment.academic_year == AcademicClass.academic_year,
                StudentEnrollment.is_active.is_(True),
            ),
        )
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            QuizAttempt.school_id == teacher.school_id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
            QuizAttempt.completed_at.is_not(None),
            AcademicClass.is_active.is_(True),
            Subject.is_active.is_(True),
            User.is_active.is_(True),
            Role.name == RoleName.STUDENT,
        )
    )


def _filtered_attempts(
    teacher: User,
    *,
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    student_id: UUID | None = None,
):
    statement = _attempt_statement(teacher)
    if class_id is not None:
        statement = statement.where(QuizAttempt.class_id == class_id)
    if subject_id is not None:
        statement = statement.where(QuizAttempt.subject_id == subject_id)
    if student_id is not None:
        statement = statement.where(QuizAttempt.student_id == student_id)
    return statement


def _result(row) -> TeacherQuizResult:
    attempt, student, academic_class, subject, chapter, quiz = row
    return TeacherQuizResult(
        attempt_id=attempt.id,
        student_id=student.id,
        student_name=student.full_name,
        class_id=academic_class.id,
        class_name=academic_class.name,
        subject_id=subject.id,
        subject_name=subject.name,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        quiz_title=quiz.title,
        score=attempt.score,
        total_questions=attempt.total_questions,
        percentage=float(attempt.percentage),
        completed_at=attempt.completed_at,
    )


def _attempt_summary(db: Session, statement):
    summary = statement.with_only_columns(
        func.count(func.distinct(QuizAttempt.id)),
        func.avg(QuizAttempt.percentage),
        func.max(QuizAttempt.percentage),
        func.sum(QuizAttempt.correct_answers),
        maintain_column_froms=True,
    )
    count, average, highest, correct = db.execute(summary).one()
    return {
        "count": count or 0,
        "average": float(average or 0),
        "highest": float(highest or 0),
        "correct": correct or 0,
    }


def _recent_results(db: Session, statement, limit: int = 8):
    rows = db.execute(
        statement.order_by(
            QuizAttempt.completed_at.desc(),
            QuizAttempt.id,
        ).limit(limit)
    ).all()
    return [_result(row) for row in rows]


def _subject_performance(db: Session, statement):
    rows = db.execute(
        statement.with_only_columns(
            Subject.id,
            Subject.name,
            func.count(func.distinct(QuizAttempt.id)),
            func.avg(QuizAttempt.percentage),
            maintain_column_froms=True,
        )
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    ).all()
    return [
        TeacherSubjectPerformance(
            subject_id=subject_id,
            subject_name=name,
            completed_quiz_count=count,
            average_percentage=float(average or 0),
        )
        for subject_id, name, count, average in rows
    ]


def _chapter_performance(db: Session, statement):
    rows = db.execute(
        statement.with_only_columns(
            Chapter.id,
            Chapter.title,
            Subject.id,
            Subject.name,
            func.count(func.distinct(QuizAttempt.id)),
            func.avg(QuizAttempt.percentage),
            maintain_column_froms=True,
        )
        .group_by(Chapter.id, Chapter.title, Subject.id, Subject.name)
        .order_by(Subject.name, Chapter.title)
    ).all()
    return [
        TeacherChapterPerformance(
            chapter_id=chapter_id,
            chapter_title=title,
            subject_id=subject_id,
            subject_name=subject_name,
            completed_quiz_count=count,
            average_percentage=float(average or 0),
        )
        for chapter_id, title, subject_id, subject_name, count, average in rows
    ]


def _validate_filters(
    contexts,
    *,
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> None:
    if class_id is not None and not any(
        assignment.class_id == class_id for assignment, _, _ in contexts
    ):
        raise HTTPException(status_code=404, detail="Assigned class not found.")
    if subject_id is not None and not any(
        assignment.subject_id == subject_id
        and (class_id is None or assignment.class_id == class_id)
        for assignment, _, _ in contexts
    ):
        raise HTTPException(status_code=404, detail="Assigned subject not found.")


@router.get("/dashboard", response_model=TeacherDashboard)
def teacher_dashboard(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> TeacherDashboard:
    contexts = _assignment_contexts(db, teacher)
    students = _student_contexts(db, teacher)
    attempts = _attempt_statement(teacher)
    summary = _attempt_summary(db, attempts)
    return TeacherDashboard(
        assigned_class_count=len({assignment.class_id for assignment, _, _ in contexts}),
        assigned_subject_count=len(
            {(assignment.class_id, assignment.subject_id) for assignment, _, _ in contexts}
        ),
        student_count=len({(student.id, enrollment.class_id) for student, _, enrollment in students}),
        completed_quiz_count=summary["count"],
        average_percentage=round(summary["average"], 2),
        recent_results=_recent_results(db, attempts),
    )


@router.get("/classes", response_model=list[TeacherClassItem])
def teacher_classes(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[TeacherClassItem]:
    contexts = _assignment_contexts(db, teacher)
    response = []
    for assignment, academic_class, subject in contexts:
        students = _student_contexts(db, teacher, class_id=academic_class.id)
        # A class may have several assigned subjects; count this class roster once.
        enrolled_students = {
            student.id
            for student, _, enrollment in students
            if enrollment.academic_year == assignment.academic_year
        }
        attempts = _filtered_attempts(
            teacher,
            class_id=academic_class.id,
            subject_id=subject.id,
        )
        summary = _attempt_summary(db, attempts)
        response.append(
            TeacherClassItem(
                class_id=academic_class.id,
                class_name=academic_class.name,
                grade_number=academic_class.grade_number,
                section=academic_class.section,
                academic_year=assignment.academic_year,
                subject_id=subject.id,
                subject_name=subject.name,
                student_count=len(enrolled_students),
                completed_quiz_count=summary["count"],
                average_percentage=round(summary["average"], 2),
            )
        )
    return response


@router.get("/classes/{class_id}/students", response_model=list[TeacherStudentItem])
def teacher_class_students(
    class_id: UUID,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[TeacherStudentItem]:
    contexts = _assignment_contexts(db, teacher)
    _validate_filters(contexts, class_id=class_id)
    results = []
    for student, academic_class, enrollment in _student_contexts(
        db, teacher, class_id=class_id
    ):
        attempts = _filtered_attempts(
            teacher,
            class_id=class_id,
            student_id=student.id,
        ).where(TeacherAssignment.academic_year == enrollment.academic_year)
        summary = _attempt_summary(db, attempts)
        results.append(
            TeacherStudentItem(
                student_id=student.id,
                full_name=student.full_name,
                email=student.email,
                class_id=academic_class.id,
                class_name=academic_class.name,
                grade_number=academic_class.grade_number,
                section=academic_class.section,
                academic_year=enrollment.academic_year,
                completed_quiz_count=summary["count"],
                average_percentage=round(summary["average"], 2),
            )
        )
    return results


@router.get("/students", response_model=list[TeacherStudentItem])
def teacher_students(
    class_id: UUID | None = None,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[TeacherStudentItem]:
    if class_id is not None:
        return teacher_class_students(class_id, teacher, db)
    contexts = _assignment_contexts(db, teacher)
    results: dict[tuple[UUID, UUID], TeacherStudentItem] = {}
    for assignment, academic_class, _ in contexts:
        for student, enrolled_class, enrollment in _student_contexts(
            db, teacher, class_id=academic_class.id
        ):
            if enrollment.academic_year != assignment.academic_year:
                continue
            key = (student.id, enrollment.class_id)
            if key in results:
                continue
            attempts = _filtered_attempts(
                teacher,
                class_id=enrollment.class_id,
                student_id=student.id,
            ).where(TeacherAssignment.academic_year == enrollment.academic_year)
            summary = _attempt_summary(db, attempts)
            results[key] = TeacherStudentItem(
                student_id=student.id,
                full_name=student.full_name,
                email=student.email,
                class_id=enrolled_class.id,
                class_name=enrolled_class.name,
                grade_number=enrolled_class.grade_number,
                section=enrolled_class.section,
                academic_year=enrollment.academic_year,
                completed_quiz_count=summary["count"],
                average_percentage=round(summary["average"], 2),
            )
    return list(results.values())


@router.get("/results", response_model=TeacherResultsPage)
def teacher_results(
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    student_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> TeacherResultsPage:
    contexts = _assignment_contexts(db, teacher)
    _validate_filters(contexts, class_id=class_id, subject_id=subject_id)
    if student_id is not None and not _student_contexts(
        db, teacher, class_id=class_id, student_id=student_id
    ):
        raise HTTPException(status_code=404, detail="Assigned student not found.")
    statement = _filtered_attempts(
        teacher,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
    )
    total_items = _attempt_summary(db, statement)["count"]
    items = _recent_results(db, statement.offset((page - 1) * page_size).limit(page_size), page_size)
    return TeacherResultsPage(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=ceil(total_items / page_size) if total_items else 0,
    )


@router.get(
    "/students/{student_id}/performance",
    response_model=TeacherStudentPerformance,
)
def teacher_student_performance(
    student_id: UUID,
    class_id: UUID | None = None,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> TeacherStudentPerformance:
    student_contexts = _student_contexts(
        db,
        teacher,
        class_id=class_id,
        student_id=student_id,
    )
    if not student_contexts:
        raise HTTPException(status_code=404, detail="Assigned student not found.")
    student, academic_class, enrollment = student_contexts[0]
    statement = _filtered_attempts(
        teacher,
        class_id=academic_class.id,
        student_id=student.id,
    ).where(TeacherAssignment.academic_year == enrollment.academic_year)
    summary = _attempt_summary(db, statement)
    return TeacherStudentPerformance(
        student_id=student.id,
        full_name=student.full_name,
        class_id=academic_class.id,
        class_name=academic_class.name,
        academic_year=enrollment.academic_year,
        completed_quiz_count=summary["count"],
        total_correct_answers=summary["correct"],
        average_percentage=round(summary["average"], 2),
        subject_performance=_subject_performance(db, statement),
        chapter_performance=_chapter_performance(db, statement),
        recent_results=_recent_results(db, statement),
    )


@router.get("/analytics", response_model=TeacherAnalytics)
def teacher_analytics(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> TeacherAnalytics:
    statement = _attempt_statement(teacher)
    summary = _attempt_summary(db, statement)
    students = _student_contexts(db, teacher)
    return TeacherAnalytics(
        student_count=len({(student.id, enrollment.class_id) for student, _, enrollment in students}),
        completed_quiz_count=summary["count"],
        average_percentage=round(summary["average"], 2),
        highest_percentage=round(summary["highest"], 2),
        subject_performance=_subject_performance(db, statement),
        chapter_performance=_chapter_performance(db, statement),
        recent_results=_recent_results(db, statement),
    )

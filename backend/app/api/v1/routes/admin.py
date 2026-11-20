from collections import defaultdict
from math import ceil
import secrets
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.enrollment import StudentEnrollment, TeacherAssignment
from app.models.enums import RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User
from app.schemas.admin import (
    AcademicClassCreate,
    AcademicClassPatch,
    AcademicClassResponse,
    ChapterCreate,
    ChapterPatch,
    ChapterResponse,
    ClassSubjectCreate,
    DashboardStats,
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentTransfer,
    PageResponse,
    PersonCreate,
    PersonPatch,
    PersonSummary,
    ProvisionedPerson,
    StatusUpdate,
    StudentCreate,
    StudentDetail,
    StudentEnrollmentSummary,
    StudentListItem,
    SubjectCreate,
    SubjectPatch,
    SubjectResponse,
    TeacherAssignmentCreate,
    TeacherAssignmentPatch,
    TeacherAssignmentResponse,
    TeacherCreate,
    TeacherDetail,
    TeacherListItem,
    TeacherPatch,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _school_id(user: User = Depends(require_admin)) -> UUID:
    if user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assign this administrator to a school before using school management.",
        )
    return user.school_id


def _commit(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_message) from None


def _require_role_id(db: Session, role_name: RoleName) -> UUID:
    role_id = db.execute(select(Role.id).where(Role.name == role_name)).scalar_one_or_none()
    if role_id is None:
        raise HTTPException(status_code=500, detail="Required account role is not configured.")
    return role_id


def _get_class(
    db: Session,
    school_id: UUID,
    class_id: UUID,
    *,
    active_only: bool = False,
) -> AcademicClass:
    statement = select(AcademicClass).where(
        AcademicClass.id == class_id,
        AcademicClass.school_id == school_id,
    )
    if active_only:
        statement = statement.where(AcademicClass.is_active.is_(True))
    result = db.execute(statement).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Class not found.")
    return result


def _get_subject(
    db: Session,
    school_id: UUID,
    subject_id: UUID,
    *,
    active_only: bool = False,
) -> Subject:
    statement = select(Subject).where(
        Subject.id == subject_id,
        Subject.school_id == school_id,
    )
    if active_only:
        statement = statement.where(Subject.is_active.is_(True))
    result = db.execute(statement).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return result


def _get_person(
    db: Session,
    school_id: UUID,
    person_id: UUID,
    role_name: RoleName,
    *,
    active_only: bool = False,
) -> User:
    statement = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.id == person_id,
            User.school_id == school_id,
            Role.name == role_name,
        )
    )
    if active_only:
        statement = statement.where(User.is_active.is_(True))
    person = db.execute(statement).scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail=f"{role_name.value.title()} not found.")
    return person


def _person_summary(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "identifier": user.username or "",
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def _enrollment_summary(enrollment: StudentEnrollment, academic_class: AcademicClass) -> dict[str, Any]:
    return {
        "id": enrollment.id,
        "class_id": academic_class.id,
        "class_name": academic_class.name,
        "grade_number": academic_class.grade_number,
        "section": academic_class.section,
        "academic_year": enrollment.academic_year,
        "is_active": enrollment.is_active,
    }


def _assignment_summary(
    assignment: TeacherAssignment,
    academic_class: AcademicClass,
    subject: Subject,
) -> dict[str, Any]:
    return {
        "id": assignment.id,
        "class_id": academic_class.id,
        "class_name": academic_class.name,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "academic_year": assignment.academic_year,
        "is_active": assignment.is_active,
    }


def _page(items: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


def _student_enrollments(
    db: Session,
    school_id: UUID,
    student_ids: list[UUID],
) -> dict[UUID, list[dict[str, Any]]]:
    result: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    if not student_ids:
        return result
    records = db.execute(
        select(StudentEnrollment, AcademicClass)
        .join(AcademicClass, AcademicClass.id == StudentEnrollment.class_id)
        .where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.student_id.in_(student_ids),
        )
        .order_by(
            StudentEnrollment.academic_year.desc(),
            StudentEnrollment.created_at.desc(),
        )
    ).all()
    for enrollment, academic_class in records:
        result[enrollment.student_id].append(
            _enrollment_summary(enrollment, academic_class)
        )
    return result


def _teacher_assignments(
    db: Session,
    school_id: UUID,
    teacher_ids: list[UUID],
) -> dict[UUID, list[dict[str, Any]]]:
    result: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    if not teacher_ids:
        return result
    records = db.execute(
        select(TeacherAssignment, AcademicClass, Subject)
        .join(AcademicClass, AcademicClass.id == TeacherAssignment.class_id)
        .join(Subject, Subject.id == TeacherAssignment.subject_id)
        .where(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.teacher_id.in_(teacher_ids),
        )
        .order_by(
            TeacherAssignment.academic_year.desc(),
            AcademicClass.grade_number,
            AcademicClass.section,
            Subject.name,
        )
    ).all()
    for assignment, academic_class, subject in records:
        result[assignment.teacher_id].append(
            _assignment_summary(assignment, academic_class, subject)
        )
    return result


def _student_item(
    user: User,
    enrollments: list[dict[str, Any]],
) -> dict[str, Any]:
    active = next((item for item in enrollments if item["is_active"]), None)
    return {**_person_summary(user), "enrollment": active}


def _teacher_item(
    user: User,
    assignments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {**_person_summary(user), "assignments": assignments}


def _class_items(
    db: Session,
    school_id: UUID,
    classes: list[AcademicClass],
) -> list[dict[str, Any]]:
    if not classes:
        return []
    class_ids = [record.id for record in classes]
    counts = dict(
        db.execute(
            select(StudentEnrollment.class_id, func.count(StudentEnrollment.id))
            .where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.class_id.in_(class_ids),
                StudentEnrollment.is_active.is_(True),
            )
            .group_by(StudentEnrollment.class_id)
        ).all()
    )
    associations = db.execute(
        select(ClassSubject.class_id, Subject)
        .join(Subject, Subject.id == ClassSubject.subject_id)
        .where(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id.in_(class_ids),
        )
        .order_by(Subject.name)
    ).all()
    subjects_by_class: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for class_id, subject in associations:
        subjects_by_class[class_id].append(
            {
                "id": subject.id,
                "name": subject.name,
                "code": subject.code,
                "is_active": subject.is_active,
            }
        )
    return [
        {
            "id": academic_class.id,
            "name": academic_class.name,
            "grade_number": academic_class.grade_number,
            "academic_year": academic_class.academic_year,
            "section": academic_class.section,
            "is_active": academic_class.is_active,
            "student_count": counts.get(academic_class.id, 0),
            "subjects": subjects_by_class[academic_class.id],
            "created_at": academic_class.created_at,
        }
        for academic_class in classes
    ]


def _subject_items(
    db: Session,
    school_id: UUID,
    subjects: list[Subject],
) -> list[dict[str, Any]]:
    if not subjects:
        return []
    subject_ids = [subject.id for subject in subjects]
    records = db.execute(
        select(ClassSubject.subject_id, AcademicClass)
        .join(AcademicClass, AcademicClass.id == ClassSubject.class_id)
        .where(
            ClassSubject.school_id == school_id,
            ClassSubject.subject_id.in_(subject_ids),
        )
        .order_by(AcademicClass.academic_year.desc(), AcademicClass.grade_number, AcademicClass.section)
    ).all()
    classes_by_subject: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for subject_id, academic_class in records:
        classes_by_subject[subject_id].append(
            {
                "id": academic_class.id,
                "name": academic_class.name,
                "grade_number": academic_class.grade_number,
                "section": academic_class.section,
                "academic_year": academic_class.academic_year,
            }
        )
    return [
        {
            "id": subject.id,
            "name": subject.name,
            "code": subject.code,
            "description": subject.description,
            "is_active": subject.is_active,
            "classes": classes_by_subject[subject.id],
            "created_at": subject.created_at,
        }
        for subject in subjects
    ]


def _chapter_item(chapter: Chapter, academic_class: AcademicClass, subject: Subject) -> dict[str, Any]:
    return {
        "id": chapter.id,
        "class_id": chapter.class_id,
        "class_name": academic_class.name,
        "subject_id": chapter.subject_id,
        "subject_name": subject.name,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "description": chapter.description,
        "is_active": chapter.is_active,
        "created_at": chapter.created_at,
    }


def _enrollment_item(
    enrollment: StudentEnrollment,
    student: User,
    academic_class: AcademicClass,
) -> dict[str, Any]:
    return {
        "id": enrollment.id,
        "student_id": student.id,
        "student_name": student.full_name,
        "student_identifier": student.username or "",
        "class_id": academic_class.id,
        "class_name": academic_class.name,
        "grade_number": academic_class.grade_number,
        "section": academic_class.section,
        "academic_year": enrollment.academic_year,
        "is_active": enrollment.is_active,
        "created_at": enrollment.created_at,
    }


def _assignment_item(
    assignment: TeacherAssignment,
    teacher: User,
    academic_class: AcademicClass,
    subject: Subject,
) -> dict[str, Any]:
    return {
        **_assignment_summary(assignment, academic_class, subject),
        "teacher_id": teacher.id,
        "teacher_name": teacher.full_name,
        "teacher_identifier": teacher.username or "",
        "created_at": assignment.created_at,
    }


def _validate_pair(
    db: Session,
    school_id: UUID,
    class_id: UUID,
    subject_id: UUID,
    *,
    active_only: bool = True,
) -> tuple[AcademicClass, Subject]:
    academic_class = _get_class(db, school_id, class_id, active_only=active_only)
    subject = _get_subject(db, school_id, subject_id, active_only=active_only)
    association = db.execute(
        select(ClassSubject.id).where(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
        )
    ).scalar_one_or_none()
    if association is None:
        raise HTTPException(
            status_code=400,
            detail="The subject must be assigned to the selected class first.",
        )
    return academic_class, subject


def _validate_identifiers(
    db: Session,
    school_id: UUID,
    *,
    username: str,
    email: str | None,
    exclude_user_id: UUID | None = None,
) -> None:
    statement = select(User.id).where(User.school_id == school_id)
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    conditions = [func.lower(User.username) == username.casefold()]
    if email:
        conditions.append(func.lower(User.email) == email.casefold())
    if db.execute(statement.where(or_(*conditions)).limit(1)).first():
        raise HTTPException(status_code=409, detail="An account already uses that identifier or email.")


def _create_person(
    db: Session,
    school_id: UUID,
    *,
    role_name: RoleName,
    full_name: str,
    identifier: str,
    email: str | None,
    phone: str | None,
    is_active: bool,
) -> tuple[User, str]:
    _validate_identifiers(
        db,
        school_id,
        username=identifier,
        email=email,
    )
    temporary_password = secrets.token_urlsafe(18)
    user = User(
        school_id=school_id,
        full_name=full_name,
        username=identifier,
        email=email,
        phone=phone,
        password_hash=hash_password(temporary_password),
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=_require_role_id(db, role_name)))
    return user, temporary_password


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    def active_people(role_name: RoleName) -> int:
        return db.execute(
            select(func.count(func.distinct(User.id)))
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.school_id == school_id,
                User.is_active.is_(True),
                Role.name == role_name,
            )
        ).scalar_one()

    active_students = active_people(RoleName.STUDENT)
    active_teachers = active_people(RoleName.TEACHER)
    enrolled_students = (
        select(StudentEnrollment.student_id)
        .where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.is_active.is_(True),
        )
        .distinct()
    )
    unenrolled = db.execute(
        select(func.count(func.distinct(User.id)))
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.school_id == school_id,
            User.is_active.is_(True),
            Role.name == RoleName.STUDENT,
            User.id.not_in(enrolled_students),
        )
    ).scalar_one()
    class_count = db.execute(
        select(func.count(AcademicClass.id)).where(
            AcademicClass.school_id == school_id,
            AcademicClass.is_active.is_(True),
        )
    ).scalar_one()
    subject_count = db.execute(
        select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.is_active.is_(True),
        )
    ).scalar_one()
    chapter_count = db.execute(
        select(func.count(Chapter.id))
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .where(
            AcademicClass.school_id == school_id,
            Chapter.is_active.is_(True),
        )
    ).scalar_one()
    enrollment_count = db.execute(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.is_active.is_(True),
        )
    ).scalar_one()
    recent_students = db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.school_id == school_id, Role.name == RoleName.STUDENT)
        .order_by(User.created_at.desc())
        .limit(5)
    ).scalars().unique().all()
    recent_teachers = db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.school_id == school_id, Role.name == RoleName.TEACHER)
        .order_by(User.created_at.desc())
        .limit(5)
    ).scalars().unique().all()
    return {
        "active_students": active_students,
        "active_teachers": active_teachers,
        "classes": class_count,
        "subjects": subject_count,
        "chapters": chapter_count,
        "active_enrollments": enrollment_count,
        "unenrolled_active_students": unenrolled,
        "recent_students": [_person_summary(person) for person in recent_students],
        "recent_teachers": [_person_summary(person) for person in recent_teachers],
    }


@router.get("/students", response_model=PageResponse[StudentListItem])
def list_students(
    search: str | None = Query(default=None, max_length=200),
    class_id: UUID | None = None,
    is_active: bool | None = None,
    enrollment_status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.school_id == school_id, Role.name == RoleName.STUDENT)
    )
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(User.full_name.ilike(term), User.username.ilike(term))
        )
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))
    if class_id is not None:
        _get_class(db, school_id, class_id)
        statement = statement.where(
            User.id.in_(
                select(StudentEnrollment.student_id).where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.class_id == class_id,
                    StudentEnrollment.is_active.is_(True),
                )
            )
        )
    if enrollment_status == "active":
        statement = statement.where(
            User.id.in_(
                select(StudentEnrollment.student_id).where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.is_active.is_(True),
                )
            )
        )
    elif enrollment_status == "inactive":
        statement = statement.where(
            User.id.not_in(
                select(StudentEnrollment.student_id).where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.is_active.is_(True),
                )
            )
        )
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    users = db.execute(
        statement.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().unique().all()
    enrollment_map = _student_enrollments(
        db,
        school_id,
        [person.id for person in users],
    )
    items = [
        _student_item(person, enrollment_map.get(person.id, []))
        for person in users
    ]
    return _page(items, total, page, page_size)


@router.post("/students", response_model=ProvisionedPerson, status_code=201)
def create_student(
    payload: StudentCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = _get_class(db, school_id, payload.class_id, active_only=True)
    user, temporary_password = _create_person(
        db,
        school_id,
        role_name=RoleName.STUDENT,
        full_name=payload.full_name,
        identifier=payload.student_identifier,
        email=payload.email,
        phone=payload.phone,
        is_active=payload.is_active,
    )
    db.add(
        StudentEnrollment(
            student_id=user.id,
            class_id=academic_class.id,
            school_id=school_id,
            academic_year=academic_class.academic_year,
            is_active=True,
        )
    )
    _commit(db, "Student identifier or enrollment already exists.")
    db.refresh(user)
    return {**_person_summary(user), "temporary_password": temporary_password}


@router.get("/students/{student_id}", response_model=StudentDetail)
def get_student(
    student_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    student = _get_person(db, school_id, student_id, RoleName.STUDENT)
    enrollments = _student_enrollments(db, school_id, [student.id]).get(student.id, [])
    return {
        **_person_summary(student),
        "current_enrollment": next(
            (item for item in enrollments if item["is_active"]),
            None,
        ),
        "enrollments": enrollments,
    }


def _update_person(
    db: Session,
    school_id: UUID,
    person: User,
    updates: dict[str, Any],
    *,
    identifier_key: str,
    email_required: bool,
) -> None:
    if identifier_key in updates:
        updates["username"] = updates.pop(identifier_key)
    new_identifier = updates.get("username", person.username)
    new_email = updates.get("email", person.email)
    if email_required and not new_email:
        raise HTTPException(status_code=422, detail="Teacher email is required.")
    if new_identifier is not None:
        _validate_identifiers(
            db,
            school_id,
            username=new_identifier,
            email=new_email,
            exclude_user_id=person.id,
        )
    for key, value in updates.items():
        setattr(person, key, value)
    _commit(db, "Account identifier or email already exists.")


@router.patch("/students/{student_id}", response_model=PersonSummary)
def update_student(
    student_id: UUID,
    payload: PersonPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    student = _get_person(db, school_id, student_id, RoleName.STUDENT)
    _update_person(
        db,
        school_id,
        student,
        payload.model_dump(exclude_unset=True),
        identifier_key="student_identifier",
        email_required=False,
    )
    db.refresh(student)
    return _person_summary(student)


@router.patch("/students/{student_id}/status", response_model=PersonSummary)
def update_student_status(
    student_id: UUID,
    payload: StatusUpdate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    student = _get_person(db, school_id, student_id, RoleName.STUDENT)
    student.is_active = payload.is_active
    _commit(db, "Student status could not be updated.")
    db.refresh(student)
    return _person_summary(student)


@router.get("/teachers", response_model=PageResponse[TeacherListItem])
def list_teachers(
    search: str | None = Query(default=None, max_length=200),
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.school_id == school_id, Role.name == RoleName.TEACHER)
    )
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(User.full_name.ilike(term), User.username.ilike(term), User.email.ilike(term))
        )
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))
    if class_id is not None or subject_id is not None:
        _get_class(db, school_id, class_id) if class_id else None
        _get_subject(db, school_id, subject_id) if subject_id else None
        assignment_filter = select(TeacherAssignment.teacher_id).where(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.is_active.is_(True),
        )
        if class_id is not None:
            assignment_filter = assignment_filter.where(TeacherAssignment.class_id == class_id)
        if subject_id is not None:
            assignment_filter = assignment_filter.where(TeacherAssignment.subject_id == subject_id)
        statement = statement.where(User.id.in_(assignment_filter))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    users = db.execute(
        statement.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().unique().all()
    assignment_map = _teacher_assignments(
        db,
        school_id,
        [person.id for person in users],
    )
    items = [
        _teacher_item(person, assignment_map.get(person.id, []))
        for person in users
    ]
    return _page(items, total, page, page_size)


@router.post("/teachers", response_model=ProvisionedPerson, status_code=201)
def create_teacher(
    payload: TeacherCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user, temporary_password = _create_person(
        db,
        school_id,
        role_name=RoleName.TEACHER,
        full_name=payload.full_name,
        identifier=payload.teacher_identifier,
        email=payload.email,
        phone=payload.phone,
        is_active=payload.is_active,
    )
    _commit(db, "Teacher identifier or email already exists.")
    db.refresh(user)
    return {**_person_summary(user), "temporary_password": temporary_password}


@router.get("/teachers/{teacher_id}", response_model=TeacherDetail)
def get_teacher(
    teacher_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    teacher = _get_person(db, school_id, teacher_id, RoleName.TEACHER)
    assignments = _teacher_assignments(db, school_id, [teacher.id]).get(teacher.id, [])
    return _teacher_item(teacher, assignments)


@router.patch("/teachers/{teacher_id}", response_model=PersonSummary)
def update_teacher(
    teacher_id: UUID,
    payload: TeacherPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    teacher = _get_person(db, school_id, teacher_id, RoleName.TEACHER)
    _update_person(
        db,
        school_id,
        teacher,
        payload.model_dump(exclude_unset=True),
        identifier_key="teacher_identifier",
        email_required=True,
    )
    db.refresh(teacher)
    return _person_summary(teacher)


@router.patch("/teachers/{teacher_id}/status", response_model=PersonSummary)
def update_teacher_status(
    teacher_id: UUID,
    payload: StatusUpdate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    teacher = _get_person(db, school_id, teacher_id, RoleName.TEACHER)
    teacher.is_active = payload.is_active
    _commit(db, "Teacher status could not be updated.")
    db.refresh(teacher)
    return _person_summary(teacher)


@router.get("/classes", response_model=PageResponse[AcademicClassResponse])
def list_classes(
    academic_year: str | None = Query(default=None, max_length=20),
    is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(AcademicClass).where(AcademicClass.school_id == school_id)
    if academic_year:
        statement = statement.where(AcademicClass.academic_year == academic_year)
    if is_active is not None:
        statement = statement.where(AcademicClass.is_active.is_(is_active))
    if search:
        statement = statement.where(AcademicClass.name.ilike(f"%{search.strip()}%"))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    classes = db.execute(
        statement.order_by(
            AcademicClass.academic_year.desc(),
            AcademicClass.grade_number,
            AcademicClass.section,
            AcademicClass.name,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return _page(_class_items(db, school_id, classes), total, page, page_size)


@router.post("/classes", response_model=AcademicClassResponse, status_code=201)
def create_class(
    payload: AcademicClassCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = AcademicClass(school_id=school_id, **payload.model_dump())
    db.add(academic_class)
    _commit(db, "A class with this grade, section, and academic year already exists.")
    db.refresh(academic_class)
    return _class_items(db, school_id, [academic_class])[0]


@router.get("/classes/{class_id}", response_model=AcademicClassResponse)
def get_class(
    class_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = _get_class(db, school_id, class_id)
    return _class_items(db, school_id, [academic_class])[0]


@router.patch("/classes/{class_id}", response_model=AcademicClassResponse)
def update_class(
    class_id: UUID,
    payload: AcademicClassPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = _get_class(db, school_id, class_id)
    updates = payload.model_dump(exclude_unset=True)
    if "academic_year" in updates:
        used = db.execute(
            select(StudentEnrollment.id).where(
                StudentEnrollment.class_id == class_id,
                StudentEnrollment.academic_year != updates["academic_year"],
            ).limit(1)
        ).first()
        if used:
            raise HTTPException(
                status_code=409,
                detail="A class academic year cannot change after enrollment history exists.",
            )
    for key, value in updates.items():
        setattr(academic_class, key, value)
    _commit(db, "Class conflicts with an existing class in this academic year.")
    db.refresh(academic_class)
    return _class_items(db, school_id, [academic_class])[0]


@router.patch("/classes/{class_id}/status", response_model=AcademicClassResponse)
def update_class_status(
    class_id: UUID,
    payload: StatusUpdate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = _get_class(db, school_id, class_id)
    academic_class.is_active = payload.is_active
    _commit(db, "Class status could not be updated.")
    db.refresh(academic_class)
    return _class_items(db, school_id, [academic_class])[0]


@router.post("/classes/{class_id}/subjects", response_model=AcademicClassResponse, status_code=201)
def assign_subject_to_class(
    class_id: UUID,
    payload: ClassSubjectCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _get_class(db, school_id, class_id, active_only=True)
    _get_subject(db, school_id, payload.subject_id, active_only=True)
    existing = db.execute(
        select(ClassSubject.id).where(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == payload.subject_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            ClassSubject(
                school_id=school_id,
                class_id=class_id,
                subject_id=payload.subject_id,
            )
        )
        _commit(db, "Subject is already assigned to this class.")
    return _class_items(db, school_id, [_get_class(db, school_id, class_id)])[0]


@router.get("/subjects", response_model=PageResponse[SubjectResponse])
def list_subjects(
    search: str | None = Query(default=None, max_length=150),
    class_id: UUID | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(Subject).where(Subject.school_id == school_id)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(or_(Subject.name.ilike(term), Subject.code.ilike(term)))
    if class_id is not None:
        _get_class(db, school_id, class_id)
        statement = statement.where(
            Subject.id.in_(
                select(ClassSubject.subject_id).where(
                    ClassSubject.school_id == school_id,
                    ClassSubject.class_id == class_id,
                )
            )
        )
    if is_active is not None:
        statement = statement.where(Subject.is_active.is_(is_active))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    subjects = db.execute(
        statement.order_by(Subject.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return _page(_subject_items(db, school_id, subjects), total, page, page_size)


@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(
    payload: SubjectCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    subject = Subject(school_id=school_id, **payload.model_dump())
    db.add(subject)
    _commit(db, "A subject with this name or code already exists.")
    db.refresh(subject)
    return _subject_items(db, school_id, [subject])[0]


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    subject = _get_subject(db, school_id, subject_id)
    return _subject_items(db, school_id, [subject])[0]


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: UUID,
    payload: SubjectPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    subject = _get_subject(db, school_id, subject_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(subject, key, value)
    _commit(db, "A subject with this name or code already exists.")
    db.refresh(subject)
    return _subject_items(db, school_id, [subject])[0]


@router.patch("/subjects/{subject_id}/status", response_model=SubjectResponse)
def update_subject_status(
    subject_id: UUID,
    payload: StatusUpdate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    subject = _get_subject(db, school_id, subject_id)
    subject.is_active = payload.is_active
    _commit(db, "Subject status could not be updated.")
    db.refresh(subject)
    return _subject_items(db, school_id, [subject])[0]


@router.get("/chapters", response_model=PageResponse[ChapterResponse])
def list_chapters(
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(Chapter, AcademicClass, Subject)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(AcademicClass.school_id == school_id, Subject.school_id == school_id)
    )
    if class_id is not None:
        _get_class(db, school_id, class_id)
        statement = statement.where(Chapter.class_id == class_id)
    if subject_id is not None:
        _get_subject(db, school_id, subject_id)
        statement = statement.where(Chapter.subject_id == subject_id)
    if is_active is not None:
        statement = statement.where(Chapter.is_active.is_(is_active))
    if search:
        statement = statement.where(Chapter.title.ilike(f"%{search.strip()}%"))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    records = db.execute(
        statement.order_by(AcademicClass.grade_number, AcademicClass.section, Chapter.chapter_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return _page(
        [_chapter_item(*record) for record in records],
        total,
        page,
        page_size,
    )


@router.post("/chapters", response_model=ChapterResponse, status_code=201)
def create_chapter(
    payload: ChapterCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class, subject = _validate_pair(
        db,
        school_id,
        payload.class_id,
        payload.subject_id,
    )
    chapter = Chapter(**payload.model_dump())
    db.add(chapter)
    _commit(db, "A chapter with this number or title already exists for the class and subject.")
    db.refresh(chapter)
    return _chapter_item(chapter, academic_class, subject)


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse)
def get_chapter(
    chapter_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record = db.execute(
        select(Chapter, AcademicClass, Subject)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(
            Chapter.id == chapter_id,
            AcademicClass.school_id == school_id,
            Subject.school_id == school_id,
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    return _chapter_item(*record)


@router.patch("/chapters/{chapter_id}", response_model=ChapterResponse)
def update_chapter(
    chapter_id: UUID,
    payload: ChapterPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    chapter_record = db.execute(
        select(Chapter, AcademicClass, Subject)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(
            Chapter.id == chapter_id,
            AcademicClass.school_id == school_id,
            Subject.school_id == school_id,
        )
    ).one_or_none()
    if chapter_record is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    chapter, _, _ = chapter_record
    updates = payload.model_dump(exclude_unset=True)
    class_id = updates.pop("class_id", chapter.class_id)
    subject_id = updates.pop("subject_id", chapter.subject_id)
    academic_class, subject = _validate_pair(
        db,
        school_id,
        class_id,
        subject_id,
        active_only=False,
    )
    chapter.class_id = class_id
    chapter.subject_id = subject_id
    for key, value in updates.items():
        setattr(chapter, key, value)
    _commit(db, "A chapter with this number or title already exists for the class and subject.")
    db.refresh(chapter)
    return _chapter_item(chapter, academic_class, subject)


@router.patch("/chapters/{chapter_id}/status", response_model=ChapterResponse)
def update_chapter_status(
    chapter_id: UUID,
    payload: StatusUpdate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    chapter_record = db.execute(
        select(Chapter, AcademicClass, Subject)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(
            Chapter.id == chapter_id,
            AcademicClass.school_id == school_id,
            Subject.school_id == school_id,
        )
    ).one_or_none()
    if chapter_record is None:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    chapter, academic_class, subject = chapter_record
    chapter.is_active = payload.is_active
    _commit(db, "Chapter status could not be updated.")
    db.refresh(chapter)
    return _chapter_item(chapter, academic_class, subject)


@router.get("/enrollments", response_model=PageResponse[EnrollmentResponse])
def list_enrollments(
    student_id: UUID | None = None,
    class_id: UUID | None = None,
    academic_year: str | None = Query(default=None, max_length=20),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(StudentEnrollment, User, AcademicClass)
        .join(User, User.id == StudentEnrollment.student_id)
        .join(AcademicClass, AcademicClass.id == StudentEnrollment.class_id)
        .where(
            StudentEnrollment.school_id == school_id,
            User.school_id == school_id,
            AcademicClass.school_id == school_id,
        )
    )
    if student_id is not None:
        _get_person(db, school_id, student_id, RoleName.STUDENT)
        statement = statement.where(StudentEnrollment.student_id == student_id)
    if class_id is not None:
        _get_class(db, school_id, class_id)
        statement = statement.where(StudentEnrollment.class_id == class_id)
    if academic_year:
        statement = statement.where(StudentEnrollment.academic_year == academic_year)
    if is_active is not None:
        statement = statement.where(StudentEnrollment.is_active.is_(is_active))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    records = db.execute(
        statement.order_by(StudentEnrollment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return _page(
        [_enrollment_item(*record) for record in records],
        total,
        page,
        page_size,
    )


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201)
def create_enrollment(
    payload: EnrollmentCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    student = _get_person(db, school_id, payload.student_id, RoleName.STUDENT, active_only=True)
    academic_class = _get_class(db, school_id, payload.class_id, active_only=True)
    if academic_class.academic_year != payload.academic_year:
        raise HTTPException(status_code=400, detail="Academic year must match the selected class.")
    enrollment = StudentEnrollment(
        student_id=student.id,
        class_id=academic_class.id,
        school_id=school_id,
        academic_year=payload.academic_year,
        is_active=True,
    )
    db.add(enrollment)
    _commit(db, "Student already has an active enrollment for this academic year.")
    db.refresh(enrollment)
    return _enrollment_item(enrollment, student, academic_class)


@router.post("/enrollments/{enrollment_id}/transfer", response_model=EnrollmentResponse, status_code=201)
def transfer_enrollment(
    enrollment_id: UUID,
    payload: EnrollmentTransfer,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    enrollment = db.execute(
        select(StudentEnrollment)
        .where(
            StudentEnrollment.id == enrollment_id,
            StudentEnrollment.school_id == school_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found.")
    if not enrollment.is_active:
        raise HTTPException(status_code=400, detail="Only an active enrollment can be transferred.")
    target_class = _get_class(db, school_id, payload.target_class_id, active_only=True)
    if target_class.academic_year != enrollment.academic_year:
        raise HTTPException(status_code=400, detail="Transfer target must be in the same academic year.")
    if target_class.id == enrollment.class_id:
        raise HTTPException(status_code=400, detail="Student is already enrolled in this class.")
    student = _get_person(db, school_id, enrollment.student_id, RoleName.STUDENT)
    enrollment.is_active = False
    replacement = StudentEnrollment(
        student_id=student.id,
        class_id=target_class.id,
        school_id=school_id,
        academic_year=enrollment.academic_year,
        is_active=True,
    )
    db.add(replacement)
    _commit(db, "Transfer conflicts with an active enrollment or historical data constraint.")
    db.refresh(replacement)
    return _enrollment_item(replacement, student, target_class)


@router.get("/teacher-assignments", response_model=PageResponse[TeacherAssignmentResponse])
def list_teacher_assignments(
    teacher_id: UUID | None = None,
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    academic_year: str | None = Query(default=None, max_length=20),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(TeacherAssignment, User, AcademicClass, Subject)
        .join(User, User.id == TeacherAssignment.teacher_id)
        .join(AcademicClass, AcademicClass.id == TeacherAssignment.class_id)
        .join(Subject, Subject.id == TeacherAssignment.subject_id)
        .where(
            TeacherAssignment.school_id == school_id,
            User.school_id == school_id,
            AcademicClass.school_id == school_id,
            Subject.school_id == school_id,
        )
    )
    if teacher_id is not None:
        _get_person(db, school_id, teacher_id, RoleName.TEACHER)
        statement = statement.where(TeacherAssignment.teacher_id == teacher_id)
    if class_id is not None:
        _get_class(db, school_id, class_id)
        statement = statement.where(TeacherAssignment.class_id == class_id)
    if subject_id is not None:
        _get_subject(db, school_id, subject_id)
        statement = statement.where(TeacherAssignment.subject_id == subject_id)
    if academic_year:
        statement = statement.where(TeacherAssignment.academic_year == academic_year)
    if is_active is not None:
        statement = statement.where(TeacherAssignment.is_active.is_(is_active))
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    records = db.execute(
        statement.order_by(TeacherAssignment.academic_year.desc(), User.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return _page(
        [_assignment_item(*record) for record in records],
        total,
        page,
        page_size,
    )


def _validate_assignment(
    db: Session,
    school_id: UUID,
    teacher_id: UUID,
    class_id: UUID,
    subject_id: UUID,
    academic_year: str,
) -> tuple[User, AcademicClass, Subject]:
    teacher = _get_person(
        db,
        school_id,
        teacher_id,
        RoleName.TEACHER,
        active_only=True,
    )
    academic_class, subject = _validate_pair(
        db,
        school_id,
        class_id,
        subject_id,
        active_only=True,
    )
    if academic_class.academic_year != academic_year:
        raise HTTPException(status_code=400, detail="Academic year must match the selected class.")
    return teacher, academic_class, subject


@router.post("/teacher-assignments", response_model=TeacherAssignmentResponse, status_code=201)
def create_teacher_assignment(
    payload: TeacherAssignmentCreate,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    teacher, academic_class, subject = _validate_assignment(
        db,
        school_id,
        payload.teacher_id,
        payload.class_id,
        payload.subject_id,
        payload.academic_year,
    )
    existing = db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher.id,
            TeacherAssignment.class_id == academic_class.id,
            TeacherAssignment.subject_id == subject.id,
            TeacherAssignment.academic_year == payload.academic_year,
            TeacherAssignment.school_id == school_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="Teacher is already assigned to this class and subject.")
        existing.is_active = True
        _commit(db, "Teacher assignment could not be reactivated.")
        assignment = existing
    else:
        assignment = TeacherAssignment(
            teacher_id=teacher.id,
            class_id=academic_class.id,
            subject_id=subject.id,
            school_id=school_id,
            academic_year=payload.academic_year,
            is_active=True,
        )
        db.add(assignment)
        _commit(db, "Teacher is already assigned to this class and subject.")
        db.refresh(assignment)
    return _assignment_item(assignment, teacher, academic_class, subject)


@router.patch("/teacher-assignments/{assignment_id}", response_model=TeacherAssignmentResponse)
def update_teacher_assignment(
    assignment_id: UUID,
    payload: TeacherAssignmentPatch,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    assignment = db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.school_id == school_id,
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teacher assignment not found.")
    updates = payload.model_dump(exclude_unset=True)
    teacher_id = updates.pop("teacher_id", assignment.teacher_id)
    class_id = updates.pop("class_id", assignment.class_id)
    subject_id = updates.pop("subject_id", assignment.subject_id)
    academic_year = updates.pop("academic_year", assignment.academic_year)
    if updates.get("is_active", assignment.is_active):
        teacher, academic_class, subject = _validate_assignment(
            db,
            school_id,
            teacher_id,
            class_id,
            subject_id,
            academic_year,
        )
    else:
        teacher = _get_person(db, school_id, teacher_id, RoleName.TEACHER)
        academic_class, subject = _validate_pair(
            db,
            school_id,
            class_id,
            subject_id,
            active_only=False,
        )
        if academic_class.academic_year != academic_year:
            raise HTTPException(status_code=400, detail="Academic year must match the selected class.")
    assignment.teacher_id = teacher_id
    assignment.class_id = class_id
    assignment.subject_id = subject_id
    assignment.academic_year = academic_year
    for key, value in updates.items():
        setattr(assignment, key, value)
    _commit(db, "Teacher assignment conflicts with an existing assignment.")
    db.refresh(assignment)
    return _assignment_item(assignment, teacher, academic_class, subject)


@router.delete("/teacher-assignments/{assignment_id}", status_code=204)
def deactivate_teacher_assignment(
    assignment_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> None:
    assignment = db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.school_id == school_id,
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teacher assignment not found.")
    assignment.is_active = False
    _commit(db, "Teacher assignment could not be deactivated.")

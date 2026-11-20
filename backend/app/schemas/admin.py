import re
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_YEAR = re.compile(r"^(20\d{2})[-/](\d{2})$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9(). -]{7,30}$")


def _validate_year(value: str) -> str:
    value = value.strip()
    match = _YEAR.fullmatch(value)
    if not match or int(match.group(2)) != (int(match.group(1)) + 1) % 100:
        raise ValueError("Academic year must be formatted like 2026-27 or 2026/27.")
    return value.replace("/", "-")


def _validate_identifier(value: str) -> str:
    value = value.strip()
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("Use 1-100 letters, numbers, dots, underscores, or hyphens.")
    return value.casefold()


def _validate_email(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    value = value.strip().casefold()
    if len(value) > 320 or not _EMAIL.fullmatch(value):
        raise ValueError("Enter a valid email address.")
    return value


def _validate_phone(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    value = value.strip()
    digits = sum(character.isdigit() for character in value)
    if not _PHONE.fullmatch(value) or not 7 <= digits <= 15:
        raise ValueError("Enter a valid phone number.")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageQuery(StrictModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PersonCreate(StrictModel):
    full_name: str = Field(min_length=1, max_length=200)
    student_identifier: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = True

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("student_identifier")
    @classmethod
    def identifier_is_normalized(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        return _validate_email(value)

    @field_validator("phone")
    @classmethod
    def phone_is_valid(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class StudentCreate(PersonCreate):
    class_id: UUID


class TeacherCreate(StrictModel):
    full_name: str = Field(min_length=1, max_length=200)
    teacher_identifier: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = True

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("teacher_identifier")
    @classmethod
    def identifier_is_normalized(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        result = _validate_email(value)
        if result is None:
            raise ValueError("Teacher email is required.")
        return result

    @field_validator("phone")
    @classmethod
    def phone_is_valid(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class PersonPatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    student_identifier: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("student_identifier")
    @classmethod
    def identifier_is_normalized(cls, value: str | None) -> str | None:
        return _validate_identifier(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        return _validate_email(value)

    @field_validator("phone")
    @classmethod
    def phone_is_valid(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class TeacherPatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    teacher_identifier: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("teacher_identifier")
    @classmethod
    def identifier_is_normalized(cls, value: str | None) -> str | None:
        return _validate_identifier(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        result = _validate_email(value)
        if value is not None and result is None:
            raise ValueError("Teacher email is required.")
        return result

    @field_validator("phone")
    @classmethod
    def phone_is_valid(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class StatusUpdate(StrictModel):
    is_active: bool


class AcademicClassCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    grade_number: int = Field(ge=1, le=12)
    academic_year: str = Field(min_length=5, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Class name is required.")
        return value

    @field_validator("academic_year")
    @classmethod
    def year_is_valid(cls, value: str) -> str:
        return _validate_year(value)

    @field_validator("section")
    @classmethod
    def section_not_blank(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value is not None else None


class AcademicClassPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    grade_number: int | None = Field(default=None, ge=1, le=12)
    academic_year: str | None = Field(default=None, min_length=5, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Class name is required.")
        return value

    @field_validator("academic_year")
    @classmethod
    def year_is_valid(cls, value: str | None) -> str | None:
        return _validate_year(value) if value is not None else None

    @field_validator("section")
    @classmethod
    def section_not_blank(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value is not None else None


class SubjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True

    @field_validator("name", "code")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class SubjectPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("name", "code")
    @classmethod
    def text_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class ClassSubjectCreate(StrictModel):
    subject_id: UUID


class ChapterCreate(StrictModel):
    class_id: UUID
    subject_id: UUID
    chapter_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Chapter title is required.")
        return value


class ChapterPatch(StrictModel):
    class_id: UUID | None = None
    subject_id: UUID | None = None
    chapter_number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Chapter title is required.")
        return value


class EnrollmentCreate(StrictModel):
    student_id: UUID
    class_id: UUID
    academic_year: str = Field(min_length=5, max_length=20)

    @field_validator("academic_year")
    @classmethod
    def year_is_valid(cls, value: str) -> str:
        return _validate_year(value)


class EnrollmentTransfer(StrictModel):
    target_class_id: UUID


class TeacherAssignmentCreate(StrictModel):
    teacher_id: UUID
    class_id: UUID
    subject_id: UUID
    academic_year: str = Field(min_length=5, max_length=20)

    @field_validator("academic_year")
    @classmethod
    def year_is_valid(cls, value: str) -> str:
        return _validate_year(value)


class TeacherAssignmentPatch(StrictModel):
    teacher_id: UUID | None = None
    class_id: UUID | None = None
    subject_id: UUID | None = None
    academic_year: str | None = Field(default=None, min_length=5, max_length=20)
    is_active: bool | None = None

    @field_validator("academic_year")
    @classmethod
    def year_is_valid(cls, value: str | None) -> str | None:
        return _validate_year(value) if value is not None else None


class PersonSummary(BaseModel):
    id: UUID
    full_name: str
    identifier: str
    email: str | None
    phone: str | None
    is_active: bool
    created_at: datetime


class StudentEnrollmentSummary(BaseModel):
    id: UUID
    class_id: UUID
    class_name: str
    grade_number: int
    section: str | None
    academic_year: str
    is_active: bool


class StudentListItem(PersonSummary):
    enrollment: StudentEnrollmentSummary | None


class StudentDetail(PersonSummary):
    current_enrollment: StudentEnrollmentSummary | None
    enrollments: list[StudentEnrollmentSummary]


class ProvisionedPerson(PersonSummary):
    temporary_password: str


class SubjectSummary(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool


class AcademicClassResponse(BaseModel):
    id: UUID
    name: str
    grade_number: int
    academic_year: str
    section: str | None
    is_active: bool
    student_count: int
    subjects: list[SubjectSummary]
    created_at: datetime


class SubjectClassSummary(BaseModel):
    id: UUID
    name: str
    grade_number: int
    section: str | None
    academic_year: str


class SubjectResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    is_active: bool
    classes: list[SubjectClassSummary]
    created_at: datetime


class ChapterResponse(BaseModel):
    id: UUID
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    chapter_number: int
    title: str
    description: str | None
    is_active: bool
    created_at: datetime


class TeacherAssignmentSummary(BaseModel):
    id: UUID
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    academic_year: str
    is_active: bool


class TeacherListItem(PersonSummary):
    assignments: list[TeacherAssignmentSummary]


class TeacherDetail(TeacherListItem):
    pass


class EnrollmentResponse(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str
    student_identifier: str
    class_id: UUID
    class_name: str
    grade_number: int
    section: str | None
    academic_year: str
    is_active: bool
    created_at: datetime


class TeacherAssignmentResponse(TeacherAssignmentSummary):
    teacher_id: UUID
    teacher_name: str
    teacher_identifier: str
    created_at: datetime


class DashboardStats(BaseModel):
    active_students: int
    active_teachers: int
    classes: int
    subjects: int
    chapters: int
    active_enrollments: int
    unenrolled_active_students: int
    recent_students: list[PersonSummary]
    recent_teachers: list[PersonSummary]

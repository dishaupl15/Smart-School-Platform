from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StudentEnrollmentContext(BaseModel):
    class_id: UUID
    class_name: str
    grade_number: int
    section: str | None
    academic_year: str


class StudentEnrollmentChoice(StudentEnrollmentContext):
    pass


class StudentProfile(BaseModel):
    full_name: str
    identifier: str
    email: str | None
    phone: str | None
    school_name: str
    enrollment: StudentEnrollmentContext


class StudentSubjectSummary(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    chapter_count: int


class StudentChapterSummary(BaseModel):
    id: UUID
    chapter_number: int
    title: str
    description: str | None
    has_available_quiz: bool


class StudentQuizActivity(BaseModel):
    attempt_id: UUID
    title: str
    subject_name: str
    chapter_title: str
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime


class StudentSubjectDetail(StudentSubjectSummary):
    chapters: list[StudentChapterSummary]


class StudentDashboard(BaseModel):
    student_name: str
    school_name: str
    enrollment: StudentEnrollmentContext
    subject_count: int
    chapter_count: int
    subjects: list[StudentSubjectSummary]
    completed_quiz_count: int
    recent_activity: list[StudentQuizActivity]


class StudentChapterDetail(StudentChapterSummary):
    subject_id: UUID
    subject_name: str
    class_name: str

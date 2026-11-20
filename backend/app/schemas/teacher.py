from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TeacherQuizResult(BaseModel):
    attempt_id: UUID
    student_id: UUID
    student_name: str
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    chapter_id: UUID
    chapter_title: str
    quiz_title: str
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime


class TeacherClassItem(BaseModel):
    class_id: UUID
    class_name: str
    grade_number: int
    section: str | None
    academic_year: str
    subject_id: UUID
    subject_name: str
    student_count: int
    completed_quiz_count: int
    average_percentage: float


class TeacherStudentItem(BaseModel):
    student_id: UUID
    full_name: str
    email: str | None
    class_id: UUID
    class_name: str
    grade_number: int
    section: str | None
    academic_year: str
    completed_quiz_count: int
    average_percentage: float


class TeacherSubjectPerformance(BaseModel):
    subject_id: UUID
    subject_name: str
    completed_quiz_count: int
    average_percentage: float


class TeacherChapterPerformance(BaseModel):
    chapter_id: UUID
    chapter_title: str
    subject_id: UUID
    subject_name: str
    completed_quiz_count: int
    average_percentage: float


class TeacherDashboard(BaseModel):
    assigned_class_count: int
    assigned_subject_count: int
    student_count: int
    completed_quiz_count: int
    average_percentage: float
    recent_results: list[TeacherQuizResult]


class TeacherResultsPage(BaseModel):
    items: list[TeacherQuizResult]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class TeacherStudentPerformance(BaseModel):
    student_id: UUID
    full_name: str
    class_id: UUID
    class_name: str
    academic_year: str
    completed_quiz_count: int
    total_correct_answers: int
    average_percentage: float
    subject_performance: list[TeacherSubjectPerformance]
    chapter_performance: list[TeacherChapterPerformance]
    recent_results: list[TeacherQuizResult]


class TeacherAnalytics(BaseModel):
    student_count: int
    completed_quiz_count: int
    average_percentage: float
    highest_percentage: float
    subject_performance: list[TeacherSubjectPerformance]
    chapter_performance: list[TeacherChapterPerformance]
    recent_results: list[TeacherQuizResult]

"""Domain model registration for SQLAlchemy and Alembic."""

from app.models.assessment import (
    AttemptQuestion,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    StudentAnswer,
)
from app.models.auth_session import AuthSession
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.enrollment import StudentEnrollment, TeacherAssignment
from app.models.question import (
    OptionTranslation,
    Question,
    QuestionOption,
    QuestionTranslation,
)
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User

__all__ = [
    "AcademicClass",
    "AuthSession",
    "AttemptQuestion",
    "Chapter",
    "ClassSubject",
    "OptionTranslation",
    "Question",
    "QuestionOption",
    "QuestionTranslation",
    "Quiz",
    "QuizAttempt",
    "QuizQuestion",
    "Role",
    "School",
    "StudentAnswer",
    "StudentEnrollment",
    "Subject",
    "TeacherAssignment",
    "User",
    "UserRole",
]

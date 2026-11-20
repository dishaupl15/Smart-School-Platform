from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LanguageCode


class QuizStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_code: LanguageCode = LanguageCode.EN


class QuizAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_option_id: UUID


class QuizOption(BaseModel):
    id: UUID
    text: str


class QuizAttemptQuestion(BaseModel):
    attempt_question_id: UUID
    display_order: int
    question_text: str
    options: list[QuizOption]
    selected_option_id: UUID | None
    language_code: LanguageCode
    feedback: "QuizAnswerFeedback | None" = None


class QuizAnswerFeedback(BaseModel):
    is_correct: bool
    correct_option_id: UUID
    explanation: str | None


class QuizAttemptResponse(BaseModel):
    status: Literal["IN_PROGRESS"] = "IN_PROGRESS"
    attempt_id: UUID
    quiz_title: str
    started_at: datetime
    expires_at: datetime
    remaining_seconds: int = Field(ge=0)
    total_questions: int
    language_code: LanguageCode
    questions: list[QuizAttemptQuestion]


class QuizResultOption(BaseModel):
    id: UUID
    text: str
    is_correct: bool


class QuizResultQuestion(BaseModel):
    attempt_question_id: UUID
    display_order: int
    question_text: str
    options: list[QuizResultOption]
    selected_option_id: UUID | None
    correct_option_id: UUID
    explanation: str | None
    is_correct: bool
    language_code: LanguageCode


class QuizResultResponse(BaseModel):
    status: Literal["COMPLETED"] = "COMPLETED"
    attempt_id: UUID
    quiz_title: str
    started_at: datetime
    completed_at: datetime
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered_questions: int
    score: int
    percentage: float
    time_taken_seconds: int
    language_code: LanguageCode
    questions: list[QuizResultQuestion]


class QuizReadyResponse(BaseModel):
    status: Literal["NOT_STARTED"] = "NOT_STARTED"
    quiz_id: UUID
    quiz_title: str
    total_questions: int = Field(ge=1)
    duration_minutes: int


class QuizHistoryItem(BaseModel):
    attempt_id: UUID
    quiz_title: str
    subject_id: UUID
    subject_name: str
    chapter_id: UUID
    chapter_title: str
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime


class QuizHistoryResponse(BaseModel):
    items: list[QuizHistoryItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class QuizSubjectPerformance(BaseModel):
    subject_id: UUID
    subject_name: str
    completed_quizzes: int
    average_percentage: float


class QuizChapterPerformance(BaseModel):
    chapter_id: UUID
    chapter_title: str
    subject_id: UUID
    subject_name: str
    completed_quizzes: int
    average_percentage: float


class QuizAnalyticsResponse(BaseModel):
    total_completed_quizzes: int
    total_questions: int
    total_correct_answers: int
    average_percentage: float
    highest_percentage: float
    recent_activity: list[QuizHistoryItem]
    subject_performance: list[QuizSubjectPerformance]
    chapter_performance: list[QuizChapterPerformance]
    strongest_subjects: list[QuizSubjectPerformance]
    needs_improvement_subjects: list[QuizSubjectPerformance]
    strongest_chapters: list[QuizChapterPerformance]
    needs_improvement_chapters: list[QuizChapterPerformance]

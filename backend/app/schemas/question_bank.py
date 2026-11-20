from enum import Enum
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LanguageCode, QuestionDifficulty, QuestionStatus, QuestionType


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionTranslationInput(StrictModel):
    language_code: LanguageCode
    question_text: str = Field(min_length=1, max_length=10000)
    explanation: str | None = Field(default=None, max_length=10000)

    @field_validator("question_text", "explanation")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank.")
        return value


class OptionTranslationInput(StrictModel):
    language_code: LanguageCode
    option_text: str = Field(min_length=1, max_length=5000)

    @field_validator("option_text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Option text cannot be blank.")
        return value


class QuestionOptionInput(StrictModel):
    option_key: str = Field(min_length=1, max_length=20)
    display_order: int = Field(ge=1, le=20)
    is_correct: bool = False
    translations: list[OptionTranslationInput] = Field(default_factory=list, max_length=3)

    @field_validator("option_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Option key is required.")
        return value

    @model_validator(mode="after")
    def unique_languages(self) -> "QuestionOptionInput":
        codes = [translation.language_code for translation in self.translations]
        if len(codes) != len(set(codes)):
            raise ValueError("An option may have only one translation per language.")
        return self


class QuestionCreate(StrictModel):
    class_id: UUID
    subject_id: UUID
    chapter_id: UUID
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    difficulty: QuestionDifficulty
    status: QuestionStatus = QuestionStatus.DRAFT
    translations: list[QuestionTranslationInput] = Field(default_factory=list, max_length=3)
    options: list[QuestionOptionInput] = Field(default_factory=list, max_length=20)

    @field_validator("status")
    @classmethod
    def creation_status(cls, value: QuestionStatus) -> QuestionStatus:
        if value not in {QuestionStatus.DRAFT, QuestionStatus.REVIEW}:
            raise ValueError("Create questions as DRAFT or REVIEW; approve or archive them later.")
        return value

    @model_validator(mode="after")
    def validate_content_shape(self) -> "QuestionCreate":
        _validate_question_content_shape(self.translations, self.options)
        if self.status == QuestionStatus.REVIEW:
            _validate_review_ready(self.translations, self.options)
        return self


class QuestionPatch(StrictModel):
    class_id: UUID | None = None
    subject_id: UUID | None = None
    chapter_id: UUID | None = None
    question_type: QuestionType | None = None
    difficulty: QuestionDifficulty | None = None
    translations: list[QuestionTranslationInput] | None = Field(default=None, max_length=3)
    options: list[QuestionOptionInput] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_content_shape(self) -> "QuestionPatch":
        if self.translations is not None:
            codes = [translation.language_code for translation in self.translations]
            if len(codes) != len(set(codes)):
                raise ValueError("A question may have only one translation per language.")
        if self.options is not None:
            _validate_question_content_shape([], self.options)
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if any(value is None for value in self.model_dump(exclude_unset=True).values()):
            raise ValueError("Provided fields cannot be null.")
        return self


class QuestionStatusUpdate(StrictModel):
    status: QuestionStatus


class QuestionTranslationResponse(BaseModel):
    language_code: LanguageCode
    question_text: str
    explanation: str | None


class OptionTranslationResponse(BaseModel):
    language_code: LanguageCode
    option_text: str


class QuestionOptionResponse(BaseModel):
    id: UUID
    option_key: str
    display_order: int
    is_correct: bool
    translations: list[OptionTranslationResponse]


class QuestionResponse(BaseModel):
    id: UUID
    school_id: UUID
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    chapter_id: UUID
    chapter_number: int
    chapter_title: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    status: QuestionStatus
    preview: str
    languages: list[LanguageCode]
    option_count: int
    translations: list[QuestionTranslationResponse]
    options: list[QuestionOptionResponse]
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class QuestionListItem(BaseModel):
    id: UUID
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    chapter_id: UUID
    chapter_number: int
    chapter_title: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    status: QuestionStatus
    question_text: str | None
    preview: str
    languages: list[LanguageCode]
    option_count: int
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class QuestionStats(BaseModel):
    total: int
    draft: int
    review: int
    approved: int
    archived: int
    by_subject: list[dict[str, object]]
    by_chapter: list[dict[str, object]]
    language_coverage: list[dict[str, object]]


class ImportConfirmationMode(str, Enum):
    VALID_ROWS = "valid_rows"
    ATOMIC = "atomic"
    ALL_OR_NOTHING = "all_or_nothing"


class ImportConfirmRequest(StrictModel):
    import_id: UUID | None = None
    mode: ImportConfirmationMode = ImportConfirmationMode.VALID_ROWS


class ImportRowReport(BaseModel):
    row_number: int
    question: str | None = None
    valid: bool
    duplicate: bool = False
    status: str
    errors: list[str]
    warnings: list[str] = Field(default_factory=list)
    question_preview: str | None = None
    question_id: UUID | None = None


class ImportSummary(BaseModel):
    import_id: UUID
    expires_at: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    confirmation_mode: ImportConfirmationMode | None = None
    committed_rows: int = 0
    inserted: int = 0
    rejected: int = 0
    rejected_atomic: bool = False
    rows: list[ImportRowReport]


def _validate_question_content_shape(
    translations: list[QuestionTranslationInput],
    options: list[QuestionOptionInput],
) -> None:
    codes = [translation.language_code for translation in translations]
    if len(codes) != len(set(codes)):
        raise ValueError("A question may have only one translation per language.")
    keys = [option.option_key for option in options]
    if len(keys) != len(set(keys)):
        raise ValueError("Option keys must be unique.")
    orders = [option.display_order for option in options]
    if len(orders) != len(set(orders)):
        raise ValueError("Option display orders must be unique.")
    if sum(option.is_correct for option in options) > 1:
        raise ValueError("Single-choice questions may have at most one correct option.")


def _validate_review_ready(
    translations: list[QuestionTranslationInput],
    options: list[QuestionOptionInput],
) -> None:
    if not any(t.language_code == LanguageCode.EN for t in translations):
        raise ValueError("English question text is required for review.")
    if len(options) != 4 or sum(option.is_correct for option in options) != 1:
        raise ValueError("Review requires exactly four options and exactly one correct option.")
    if {option.option_key for option in options} != {"A", "B", "C", "D"}:
        raise ValueError("Review requires option keys A, B, C, and D exactly once.")
    if {option.display_order for option in options} != {1, 2, 3, 4}:
        raise ValueError("Review requires each of the four display positions exactly once.")
    if any(not any(t.language_code == LanguageCode.EN for t in option.translations) for option in options):
        raise ValueError("English text is required for every option before review.")


def _validate_approved(
    translations: list[QuestionTranslationInput],
    options: list[QuestionOptionInput],
) -> None:
    _validate_review_ready(translations, options)
    required = set(LanguageCode)
    question_languages = {translation.language_code for translation in translations}
    if question_languages != required:
        raise ValueError("Approval requires question text in English, Hindi, and Marathi.")
    for option in options:
        option_languages = {translation.language_code for translation in option.translations}
        if option_languages != required:
            raise ValueError("Approval requires all three translations for every option.")

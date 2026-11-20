from math import ceil
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.dependencies.auth import require_admin
from app.db.session import get_db
from app.models.academic import AcademicClass, Chapter, Subject
from app.models.assessment import AttemptQuestion, QuizAttempt, StudentAnswer
from app.models.enums import (
    AttemptStatus,
    LanguageCode,
    QuestionDifficulty,
    QuestionStatus,
    QuestionType,
)
from app.models.question import (
    OptionTranslation,
    Question,
    QuestionOption,
    QuestionTranslation,
)
from app.models.user import User
from app.schemas.question_bank import (
    ImportConfirmationMode,
    ImportConfirmRequest,
    ImportSummary,
    PageResponse,
    QuestionCreate,
    QuestionListItem,
    QuestionOptionInput,
    QuestionPatch,
    QuestionResponse,
    QuestionStats,
    QuestionStatusUpdate,
    QuestionTranslationInput,
    _validate_approved,
    _validate_review_ready,
)
from app.services.question_bank import (
    import_preview_store,
    import_report_csv,
    import_row_to_payload,
    parse_question_file,
    csv_template,
    xlsx_template,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _school_id(user: User = Depends(require_admin)) -> UUID:
    if user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assign this administrator to a school before using the question bank.",
        )
    return user.school_id


def _get_question(db: Session, school_id: UUID, question_id: UUID) -> Question:
    question = db.execute(
        select(Question)
        .where(Question.id == question_id, Question.school_id == school_id)
        .options(
            selectinload(Question.translations),
            selectinload(Question.options).selectinload(QuestionOption.translations),
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return question


def _validate_context(
    db: Session,
    school_id: UUID,
    class_id: UUID,
    subject_id: UUID,
    chapter_id: UUID,
    *,
    lock: bool = False,
) -> Chapter:
    statement = (
        select(Chapter)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(
            Chapter.id == chapter_id,
            Chapter.class_id == class_id,
            Chapter.subject_id == subject_id,
            Chapter.is_active.is_(True),
            AcademicClass.school_id == school_id,
            AcademicClass.is_active.is_(True),
            Subject.school_id == school_id,
            Subject.is_active.is_(True),
        )
    )
    if lock:
        statement = statement.with_for_update(of=Chapter)
    context = db.execute(statement).scalar_one_or_none()
    if context is None:
        raise HTTPException(
            status_code=422,
            detail="Class, subject, and active chapter must belong to this school and match each other.",
        )
    return context


def _duplicate_error(
    db: Session,
    school_id: UUID,
    chapter_id: UUID,
    translations: list[Any],
    exclude_id: UUID | None = None,
) -> str | None:
    for translation in translations:
        normalized = translation.question_text.strip().casefold()
        statement = (
            select(QuestionTranslation.id)
            .join(Question, Question.id == QuestionTranslation.question_id)
            .where(
                Question.school_id == school_id,
                Question.chapter_id == chapter_id,
                QuestionTranslation.language_code == translation.language_code,
                func.lower(func.trim(QuestionTranslation.question_text)) == normalized,
            )
        )
        if exclude_id is not None:
            statement = statement.where(Question.id != exclude_id)
        if db.execute(statement.limit(1)).first() is not None:
            return f"A question with the same {translation.language_code.value} text already exists in this chapter."
    return None


def _validate_duplicate_or_raise(
    db: Session,
    school_id: UUID,
    chapter_id: UUID,
    translations: list[Any],
    exclude_id: UUID | None = None,
) -> None:
    error = _duplicate_error(db, school_id, chapter_id, translations, exclude_id)
    if error:
        raise HTTPException(status_code=409, detail=error)


def _replace_translations(
    db: Session,
    question: Question,
    translations: list[QuestionTranslationInput],
) -> None:
    question.translations.clear()
    db.flush()
    question.translations.extend(
        QuestionTranslation(
            language_code=translation.language_code,
            question_text=translation.question_text,
            explanation=translation.explanation,
        )
        for translation in translations
    )


def _replace_options(
    db: Session,
    question: Question,
    options: list[QuestionOptionInput],
) -> None:
    question.options.clear()
    db.flush()
    for option_input in options:
        option = QuestionOption(
            option_key=option_input.option_key,
            display_order=option_input.display_order,
            is_correct=option_input.is_correct,
        )
        option.translations.extend(
            OptionTranslation(
                language_code=translation.language_code,
                option_text=translation.option_text,
            )
            for translation in option_input.translations
        )
        question.options.append(option)


def _update_options_preserving_ids(
    db: Session,
    question: Question,
    options: list[QuestionOptionInput],
) -> None:
    current_by_key = {option.option_key: option for option in question.options}
    incoming_keys = {option.option_key for option in options}
    removed = [
        option
        for key, option in current_by_key.items()
        if key not in incoming_keys
    ]
    removed_ids = [option.id for option in removed]
    if removed_ids and db.execute(
        select(StudentAnswer.id)
        .where(StudentAnswer.selected_option_id.in_(removed_ids))
        .limit(1)
    ).first():
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An option selected in historical answers cannot be removed.",
        )

    order_offset = max(
        (option.display_order for option in question.options),
        default=0,
    ) + 100
    for option in question.options:
        option.display_order += order_offset
        option.is_correct = False
    db.flush()

    for option in removed:
        question.options.remove(option)

    for option_input in options:
        option = current_by_key.get(option_input.option_key)
        if option is None:
            option = QuestionOption(
                option_key=option_input.option_key,
                display_order=option_input.display_order,
                is_correct=option_input.is_correct,
            )
            question.options.append(option)
        else:
            option.option_key = option_input.option_key
            option.display_order = option_input.display_order
            option.is_correct = option_input.is_correct

        translations_by_language = {
            translation.language_code: translation
            for translation in option.translations
        }
        incoming_languages = {
            translation.language_code for translation in option_input.translations
        }
        for translation in list(option.translations):
            if translation.language_code not in incoming_languages:
                option.translations.remove(translation)
        for translation_input in option_input.translations:
            translation = translations_by_language.get(
                translation_input.language_code
            )
            if translation is None:
                option.translations.append(
                    OptionTranslation(
                        language_code=translation_input.language_code,
                        option_text=translation_input.option_text,
                    )
                )
            else:
                translation.option_text = translation_input.option_text
    db.flush()


def _create_question(
    db: Session,
    payload: QuestionCreate,
    school_id: UUID,
    actor_id: UUID,
) -> Question:
    chapter = _validate_context(
        db,
        school_id,
        payload.class_id,
        payload.subject_id,
        payload.chapter_id,
        lock=True,
    )
    _validate_duplicate_or_raise(
        db, school_id, chapter.id, payload.translations
    )
    question = Question(
        school_id=school_id,
        subject_id=payload.subject_id,
        chapter_id=payload.chapter_id,
        question_type=payload.question_type,
        difficulty=payload.difficulty,
        status=payload.status,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(question)
    db.flush()
    _replace_translations(db, question, payload.translations)
    _replace_options(db, question, payload.options)
    db.flush()
    return question


def _get_context_details(db: Session, question: Question) -> tuple[Chapter, Subject, AcademicClass]:
    chapter = db.get(Chapter, question.chapter_id)
    subject = db.get(Subject, question.subject_id)
    academic_class = db.get(AcademicClass, chapter.class_id) if chapter else None
    if chapter is None or subject is None or academic_class is None:
        raise HTTPException(status_code=500, detail="Question academic context is incomplete.")
    return chapter, subject, academic_class


def _question_response(db: Session, question: Question) -> dict[str, Any]:
    chapter, subject, academic_class = _get_context_details(db, question)
    return {
        "id": question.id,
        "school_id": question.school_id,
        "class_id": academic_class.id,
        "class_name": academic_class.name,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "chapter_id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "chapter_title": chapter.title,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "status": question.status,
        "preview": next(
            (
                translation.question_text
                for translation in question.translations
                if translation.language_code == LanguageCode.EN
            ),
            question.translations[0].question_text if question.translations else "",
        ),
        "languages": sorted(
            {translation.language_code for translation in question.translations},
            key=lambda language: language.value,
        ),
        "option_count": len(question.options),
        "translations": [
            {
                "language_code": translation.language_code,
                "question_text": translation.question_text,
                "explanation": translation.explanation,
            }
            for translation in sorted(question.translations, key=lambda item: item.language_code.value)
        ],
        "options": [
            {
                "id": option.id,
                "option_key": option.option_key,
                "display_order": option.display_order,
                "is_correct": option.is_correct,
                "translations": [
                    {
                        "language_code": translation.language_code,
                        "option_text": translation.option_text,
                    }
                    for translation in sorted(option.translations, key=lambda item: item.language_code.value)
                ],
            }
            for option in sorted(question.options, key=lambda item: item.display_order)
        ],
        "created_by": question.created_by,
        "updated_by": question.updated_by,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def _list_item(
    question: Question,
    academic_class: AcademicClass,
    subject: Subject,
    chapter: Chapter,
    language: LanguageCode | None,
) -> dict[str, Any]:
    requested = next(
        (
            translation.question_text
            for translation in question.translations
            if language is not None and translation.language_code == language
        ),
        None,
    )
    english = next(
        (translation.question_text for translation in question.translations if translation.language_code == LanguageCode.EN),
        None,
    )
    return {
        "id": question.id,
        "class_id": academic_class.id,
        "class_name": academic_class.name,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "chapter_id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "chapter_title": chapter.title,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "status": question.status,
        "question_text": requested or english,
        "preview": requested or english or "",
        "languages": sorted(
            {translation.language_code for translation in question.translations},
            key=lambda language: language.value,
        ),
        "option_count": len(question.options),
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def _status_validation(question: Question, target: QuestionStatus) -> None:
    transitions = {
        QuestionStatus.DRAFT: {QuestionStatus.REVIEW, QuestionStatus.ARCHIVED},
        QuestionStatus.REVIEW: {
            QuestionStatus.DRAFT,
            QuestionStatus.APPROVED,
            QuestionStatus.ARCHIVED,
        },
        QuestionStatus.APPROVED: {QuestionStatus.DRAFT, QuestionStatus.ARCHIVED},
        QuestionStatus.ARCHIVED: {QuestionStatus.DRAFT},
    }
    if target not in transitions[question.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot change question status from {question.status.value} to {target.value}.",
        )
    if target in {QuestionStatus.REVIEW, QuestionStatus.APPROVED}:
        try:
            _validate_review_ready(question.translations, question.options)
            if target == QuestionStatus.APPROVED:
                _validate_approved(question.translations, question.options)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None


def _summary(import_id: UUID, entry: dict[str, Any]) -> dict[str, Any]:
    report_rows = entry["rows"]
    rejected = sum(not row["valid"] for row in report_rows)
    return {
        "import_id": import_id,
        "expires_at": entry["expires_at"].isoformat(),
        "total_rows": len(report_rows),
        "valid_rows": sum(row["valid"] for row in report_rows),
        "invalid_rows": sum(not row["valid"] for row in report_rows),
        "duplicate_rows": sum(any("already exists" in error or "duplicate row" in error for error in row["errors"]) for row in report_rows),
        "confirmation_mode": entry["mode"],
        "committed_rows": entry["committed_rows"],
        "inserted": entry["committed_rows"],
        "rejected": rejected + (
            sum(row["valid"] for row in report_rows)
            if entry["rejected"]
            else 0
        ),
        "rejected_atomic": entry["rejected"],
        "rows": [
            {
                **row,
                "question": row["question_preview"],
                "duplicate": any(
                    "duplicate" in error.casefold() or "already exists" in error.casefold()
                    for error in row["errors"]
                ),
                "warnings": list(row.get("warnings", [])),
            }
            for row in report_rows
        ],
    }


def _request_payload(payload: dict[str, Any]) -> QuestionCreate:
    return QuestionCreate.model_validate(payload)


def _rollback_on_integrity_error(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The question conflicts with existing data; no changes were saved.",
        ) from None


@router.get("/stats", response_model=QuestionStats)
def question_stats(
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    counts = dict(
        db.execute(
            select(Question.status, func.count(Question.id))
            .where(Question.school_id == school_id)
            .group_by(Question.status)
        ).all()
    )
    by_subject = db.execute(
        select(Subject.id, Subject.name, func.count(Question.id))
        .join(Question, Question.subject_id == Subject.id)
        .where(Question.school_id == school_id)
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    ).all()
    by_chapter = db.execute(
        select(Chapter.id, Chapter.title, func.count(Question.id))
        .join(Question, Question.chapter_id == Chapter.id)
        .where(Question.school_id == school_id)
        .group_by(Chapter.id, Chapter.title)
        .order_by(Chapter.title)
    ).all()
    language_counts = dict(
        db.execute(
            select(
                QuestionTranslation.language_code,
                func.count(func.distinct(QuestionTranslation.question_id)),
            )
            .join(Question, Question.id == QuestionTranslation.question_id)
            .where(Question.school_id == school_id)
            .group_by(QuestionTranslation.language_code)
        ).all()
    )
    return {
        "total": sum(counts.values()),
        "draft": counts.get(QuestionStatus.DRAFT, 0),
        "review": counts.get(QuestionStatus.REVIEW, 0),
        "approved": counts.get(QuestionStatus.APPROVED, 0),
        "archived": counts.get(QuestionStatus.ARCHIVED, 0),
        "by_subject": [
            {"subject_id": subject_id, "subject_name": name, "count": count}
            for subject_id, name, count in by_subject
        ],
        "by_chapter": [
            {"chapter_id": chapter_id, "chapter_title": title, "count": count}
            for chapter_id, title, count in by_chapter
        ],
        "language_coverage": [
            {"language_code": language, "count": language_counts.get(language, 0)}
            for language in LanguageCode
        ],
    }


@router.get("", response_model=PageResponse[QuestionListItem])
def list_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    status_filter: QuestionStatus | None = Query(default=None, alias="status"),
    difficulty: QuestionDifficulty | None = None,
    question_type: QuestionType | None = None,
    class_id: UUID | None = None,
    subject_id: UUID | None = None,
    chapter_id: UUID | None = None,
    language: LanguageCode | None = None,
    incomplete_translation: bool = False,
    sort_by: str = Query(default="updated_at", pattern="^(created_at|updated_at|difficulty|status)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = (
        select(Question, AcademicClass, Subject, Chapter)
        .join(Chapter, Chapter.id == Question.chapter_id)
        .join(Subject, Subject.id == Question.subject_id)
        .join(AcademicClass, AcademicClass.id == Chapter.class_id)
        .where(Question.school_id == school_id)
    )
    if class_id is not None:
        statement = statement.where(Chapter.class_id == class_id)
    if subject_id is not None:
        statement = statement.where(Question.subject_id == subject_id)
    if chapter_id is not None:
        statement = statement.where(Question.chapter_id == chapter_id)
    if status_filter is not None:
        statement = statement.where(Question.status == status_filter)
    if difficulty is not None:
        statement = statement.where(Question.difficulty == difficulty)
    if question_type is not None:
        statement = statement.where(Question.question_type == question_type)
    if language is not None:
        statement = statement.where(
            Question.id.in_(
                select(QuestionTranslation.question_id).where(
                    QuestionTranslation.language_code == language
                )
            )
        )
    if incomplete_translation:
        complete_question_translations = (
            select(QuestionTranslation.question_id)
            .group_by(QuestionTranslation.question_id)
            .having(func.count(func.distinct(QuestionTranslation.language_code)) == len(LanguageCode))
        )
        incomplete_options = (
            select(QuestionOption.question_id)
            .outerjoin(OptionTranslation, OptionTranslation.option_id == QuestionOption.id)
            .group_by(QuestionOption.id, QuestionOption.question_id)
            .having(func.count(func.distinct(OptionTranslation.language_code)) < len(LanguageCode))
        )
        incomplete_option_count = (
            select(Question.id)
            .outerjoin(QuestionOption, QuestionOption.question_id == Question.id)
            .group_by(Question.id)
            .having(func.count(QuestionOption.id) != 4)
        )
        statement = statement.where(
            or_(
                ~Question.id.in_(complete_question_translations),
                Question.id.in_(incomplete_options),
                Question.id.in_(incomplete_option_count),
            )
        )
    if search:
        pattern = f"%{search.strip()}%"
        matching = (
            select(QuestionTranslation.question_id)
            .where(QuestionTranslation.question_text.ilike(pattern))
        )
        statement = statement.where(
            or_(
                Question.id.in_(matching),
                Question.id.in_(
                    select(QuestionOption.question_id)
                    .join(OptionTranslation, OptionTranslation.option_id == QuestionOption.id)
                    .where(OptionTranslation.option_text.ilike(pattern))
                ),
            )
        )
    total = db.execute(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).scalar_one()
    questions = db.execute(
        statement.options(
            selectinload(Question.translations),
            selectinload(Question.options),
        )
        .order_by(
            getattr(Question, sort_by).asc()
            if sort_order == "asc"
            else getattr(Question, sort_by).desc(),
            Question.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            _list_item(question, academic_class, subject, chapter, language)
            for question, academic_class, subject, chapter in questions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


@router.get("/import-template")
@router.get("/import/template", include_in_schema=False)
def download_import_template(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    _: UUID = Depends(_school_id),
) -> Response:
    if format == "xlsx":
        return Response(
            content=xlsx_template(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="question-bank-template.xlsx"'},
        )
    return Response(
        content=csv_template(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="question-bank-template.csv"'},
    )


@router.post("/imports/preview", response_model=ImportSummary)
@router.post("/import/preview", response_model=ImportSummary, include_in_schema=False)
async def preview_import(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source_rows = await parse_question_file(file)
    report_rows: list[dict[str, Any]] = []
    import_payloads: dict[int, dict[str, Any]] = {}
    seen: set[tuple[UUID, str, str]] = set()
    for offset, row in enumerate(source_rows, start=2):
        issues: list[str] = []
        warnings: list[str] = []
        payload: dict[str, Any] | None = None
        try:
            payload = import_row_to_payload(row)
            validated = _request_payload(payload)
            payload = validated.model_dump()
            question_languages = {
                translation.language_code for translation in validated.translations
            }
            for language in LanguageCode:
                if language not in question_languages:
                    warnings.append(
                        f"Question translation is missing for {language.value}."
                    )
            for option in validated.options:
                option_languages = {
                    translation.language_code for translation in option.translations
                }
                for language in LanguageCode:
                    if language not in option_languages:
                        warnings.append(
                            f"Option {option.option_key} translation is missing for {language.value}."
                        )
            _validate_context(
                db,
                school_id,
                validated.class_id,
                validated.subject_id,
                validated.chapter_id,
            )
            duplicate = _duplicate_error(
                db, school_id, validated.chapter_id, validated.translations
            )
            if duplicate:
                issues.append(duplicate)
            for translation in validated.translations:
                fingerprint = (
                    validated.chapter_id,
                    translation.language_code.value,
                    translation.question_text.strip().casefold(),
                )
                if fingerprint in seen:
                    issues.append("Duplicate row: the same question text appears earlier in this file.")
                    break
                seen.add(fingerprint)
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                issues.extend(error["msg"] for error in exc.errors())
            else:
                issues.append(str(exc))
        except HTTPException as exc:
            issues.append(str(exc.detail))
        valid = not issues and payload is not None
        question_preview = None
        if payload is not None:
            question_preview = next(
                (
                    translation["question_text"]
                    for translation in payload["translations"]
                    if translation["language_code"] == LanguageCode.EN
                ),
                next(
                    (translation["question_text"] for translation in payload["translations"]),
                    None,
                ),
            )
        report_rows.append(
            {
                "row_number": offset,
                "valid": valid,
                "status": "valid" if valid else "invalid",
                "errors": issues,
                "warnings": warnings,
                "question_preview": question_preview[:160] if question_preview else None,
                "question_id": None,
            }
        )
        if valid and payload is not None:
            import_payloads[offset] = payload

    import_id, expires_at = import_preview_store.create(
        user.id,
        school_id,
        [
            {
                "row_number": report["row_number"],
                "payload": import_payloads.get(report["row_number"]),
                "valid": report["valid"],
                "status": report["status"],
                "errors": list(report["errors"]),
                "warnings": list(report["warnings"]),
                "question_preview": report["question_preview"],
                "question_id": None,
            }
            for report in report_rows
        ],
    )
    entry = import_preview_store.get(import_id, user.id, school_id)
    entry["expires_at"] = expires_at
    return _summary(import_id, entry)


@router.post("/imports/{import_id}/confirm", response_model=ImportSummary)
def confirm_import(
    import_id: UUID,
    request: ImportConfirmRequest,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    mode = (
        ImportConfirmationMode.ATOMIC
        if request.mode == ImportConfirmationMode.ALL_OR_NOTHING
        else request.mode
    )
    entry = import_preview_store.claim(
        import_id, user.id, school_id, mode.value
    )
    eligible = [row for row in entry["rows"] if row["valid"]]
    changed = False
    for row in eligible:
        payload = _request_payload(row["payload"])
        try:
            _validate_context(
                db, school_id, payload.class_id, payload.subject_id, payload.chapter_id
            )
            duplicate = _duplicate_error(
                db, school_id, payload.chapter_id, payload.translations
            )
            if duplicate:
                raise HTTPException(status_code=409, detail=duplicate)
        except (HTTPException, ValidationError, ValueError) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            row["valid"] = False
            row["status"] = "invalidated"
            row["errors"].append(str(detail))
            changed = True
    if mode == ImportConfirmationMode.ATOMIC and any(not row["valid"] for row in entry["rows"]):
        entry["rejected"] = True
        for row in entry["rows"]:
            if row["valid"]:
                row["status"] = "not_imported_atomic"
        return _summary(import_id, entry)

    if changed and request.mode == ImportConfirmationMode.ATOMIC:
        entry["rejected"] = True
        return _summary(import_id, entry)

    created_count = 0
    for row in entry["rows"]:
        if not row["valid"]:
            continue
        try:
            with db.begin_nested():
                payload = _request_payload(row["payload"])
                question = _create_question(db, payload, school_id, user.id)
                db.flush()
            row["question_id"] = question.id
            row["status"] = "created"
            created_count += 1
            if mode == ImportConfirmationMode.VALID_ROWS:
                db.commit()
        except HTTPException as exc:
            row["valid"] = False
            row["status"] = "invalidated"
            row["question_id"] = None
            row["errors"].append(str(exc.detail))
            if mode == ImportConfirmationMode.ATOMIC:
                db.rollback()
                for imported in entry["rows"]:
                    if imported["status"] == "created":
                        imported["status"] = "not_imported_atomic"
                        imported["question_id"] = None
                entry["committed_rows"] = 0
                entry["rejected"] = True
                return _summary(import_id, entry)
        except IntegrityError:
            db.rollback()
            row["valid"] = False
            row["status"] = "invalidated"
            row["question_id"] = None
            row["errors"].append("The row conflicts with existing data.")
            if mode == ImportConfirmationMode.ATOMIC:
                db.rollback()
                for imported in entry["rows"]:
                    if imported["status"] == "created":
                        imported["status"] = "not_imported_atomic"
                        imported["question_id"] = None
                entry["committed_rows"] = 0
                entry["rejected"] = True
                return _summary(import_id, entry)
    if mode == ImportConfirmationMode.ATOMIC and created_count:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            for imported in entry["rows"]:
                if imported["status"] == "created":
                    imported["status"] = "not_imported_atomic"
                    imported["question_id"] = None
            entry["rejected"] = True
            entry["committed_rows"] = 0
            return _summary(import_id, entry)
    entry["committed_rows"] = created_count
    return _summary(import_id, entry)


@router.get("/imports/{import_id}/report", response_model=ImportSummary)
@router.get("/import/report/{import_id}", response_model=ImportSummary, include_in_schema=False)
def import_report(
    import_id: UUID,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
) -> dict[str, Any]:
    entry = import_preview_store.get(import_id, user.id, school_id)
    return _summary(import_id, entry)


@router.get("/imports/{import_id}/report/download")
def download_import_report(
    import_id: UUID,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
) -> Response:
    entry = import_preview_store.get(import_id, user.id, school_id)
    return Response(
        content=import_report_csv(entry),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="question-import-{import_id}.csv"'},
    )


@router.post("/import/confirm", response_model=ImportSummary, include_in_schema=False)
def confirm_import_compat(
    request: ImportConfirmRequest,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if request.import_id is None:
        raise HTTPException(status_code=422, detail="import_id is required.")
    return confirm_import(request.import_id, request, user, school_id, db)


@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    question = _create_question(db, payload, school_id, user.id)
    _rollback_on_integrity_error(db)
    question = _get_question(db, school_id, question.id)
    return _question_response(db, question)


@router.post("/{question_id}/duplicate", response_model=QuestionResponse, status_code=201)
def duplicate_question(
    question_id: UUID,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    original = _get_question(db, school_id, question_id)
    class_id = db.get(Chapter, original.chapter_id).class_id
    chapter = _validate_context(
        db, school_id, class_id, original.subject_id, original.chapter_id, lock=True
    )
    duplicate = Question(
        school_id=school_id,
        subject_id=original.subject_id,
        chapter_id=chapter.id,
        question_type=original.question_type,
        difficulty=original.difficulty,
        status=QuestionStatus.DRAFT,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(duplicate)
    db.flush()
    _replace_translations(
        db,
        duplicate,
        [
            QuestionTranslationInput(
                language_code=translation.language_code,
                question_text=translation.question_text,
                explanation=translation.explanation,
            )
            for translation in original.translations
        ],
    )
    _replace_options(
        db,
        duplicate,
        [
            QuestionOptionInput(
                option_key=option.option_key,
                display_order=option.display_order,
                is_correct=option.is_correct,
                translations=[
                    {
                        "language_code": translation.language_code,
                        "option_text": translation.option_text,
                    }
                    for translation in option.translations
                ],
            )
            for option in original.options
        ],
    )
    _rollback_on_integrity_error(db)
    return _question_response(db, _get_question(db, school_id, duplicate.id))


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: UUID,
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _question_response(db, _get_question(db, school_id, question_id))


@router.patch("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: UUID,
    payload: QuestionPatch,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    question = _get_question(db, school_id, question_id)
    if db.execute(
        select(AttemptQuestion.id)
        .join(QuizAttempt, QuizAttempt.id == AttemptQuestion.attempt_id)
        .where(
            AttemptQuestion.question_id == question.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .limit(1)
    ).first():
        raise HTTPException(
            status_code=409,
            detail=(
                "This question has historical answers or belongs to an active "
                "quiz attempt and cannot be edited yet."
            ),
        )
    if question.status in {QuestionStatus.APPROVED, QuestionStatus.ARCHIVED}:
        raise HTTPException(
            status_code=409,
            detail="Move the question to DRAFT before editing it.",
        )
    data = payload.model_dump(exclude_unset=True)
    if any(value is None for value in data.values()):
        raise HTTPException(status_code=422, detail="Provided fields cannot be null.")
    class_id = data.pop("class_id", None)
    new_subject_id = data.get("subject_id", question.subject_id)
    new_chapter_id = data.get("chapter_id", question.chapter_id)
    target_chapter = db.get(Chapter, new_chapter_id)
    if target_chapter is None:
        raise HTTPException(status_code=422, detail="Chapter not found.")
    chapter = _validate_context(
        db,
        school_id,
        class_id or target_chapter.class_id,
        new_subject_id,
        new_chapter_id,
        lock=True,
    )
    translations = payload.translations
    options = payload.options
    data.pop("translations", None)
    data.pop("options", None)
    if translations is not None or (
        new_subject_id != question.subject_id or new_chapter_id != question.chapter_id
    ):
        _validate_duplicate_or_raise(
            db,
            school_id,
            chapter.id,
            translations if translations is not None else question.translations,
            exclude_id=question.id,
        )
    for field, value in data.items():
        setattr(question, field, value)
    question.subject_id = new_subject_id
    question.chapter_id = new_chapter_id
    question.updated_by = user.id
    if translations is not None:
        _replace_translations(db, question, translations)
    if options is not None:
        _update_options_preserving_ids(db, question, options)
    if question.status == QuestionStatus.REVIEW:
        try:
            _validate_review_ready(question.translations, question.options)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from None
    _rollback_on_integrity_error(db)
    return _question_response(db, _get_question(db, school_id, question.id))


@router.patch("/{question_id}/status", response_model=QuestionResponse)
def update_question_status(
    question_id: UUID,
    payload: QuestionStatusUpdate,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    question = _get_question(db, school_id, question_id)
    if question.status != payload.status:
        _status_validation(question, payload.status)
        question.status = payload.status
        question.updated_by = user.id
        _rollback_on_integrity_error(db)
    return _question_response(db, _get_question(db, school_id, question.id))


@router.post("/{question_id}/archive", response_model=QuestionResponse)
def archive_question(
    question_id: UUID,
    user: User = Depends(require_admin),
    school_id: UUID = Depends(_school_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    question = _get_question(db, school_id, question_id)
    if question.status != QuestionStatus.ARCHIVED:
        _status_validation(question, QuestionStatus.ARCHIVED)
        question.status = QuestionStatus.ARCHIVED
        question.updated_by = user.id
        _rollback_on_integrity_error(db)
    return _question_response(db, _get_question(db, school_id, question.id))

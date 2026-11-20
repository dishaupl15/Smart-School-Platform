from datetime import date, datetime, time, timedelta, timezone
from secrets import SystemRandom
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.dependencies.auth import require_student
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.academic import AcademicClass, Chapter, ClassSubject, Subject
from app.models.assessment import (
    AttemptQuestion,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    StudentAnswer,
)
from app.models.enrollment import StudentEnrollment
from app.models.enums import (
    AttemptStatus,
    LanguageCode,
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
from app.schemas.student_quiz import (
    QuizAnswerRequest,
    QuizAnalyticsResponse,
    QuizAttemptResponse,
    QuizHistoryResponse,
    QuizReadyResponse,
    QuizResultResponse,
    QuizStartRequest,
)

router = APIRouter()
_secure_random = SystemRandom()


def _active_class(
    db: Session,
    student: User,
    class_id: UUID | None = None,
) -> AcademicClass:
    if student.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active enrollment is required to take quizzes.",
        )
    statement = (
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
        .limit(1)
    )
    if class_id is not None:
        statement = statement.where(StudentEnrollment.class_id == class_id)
    enrollment = db.execute(statement).first()
    if enrollment is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if class_id is not None
                else status.HTTP_403_FORBIDDEN
            ),
            detail="An active enrollment is required to take quizzes.",
        )
    return enrollment[1]


def _available_quiz(
    db: Session,
    student: User,
    academic_class: AcademicClass,
    chapter_id: UUID,
) -> Quiz:
    quiz = db.execute(
        select(Quiz)
        .join(Chapter, Chapter.id == Quiz.chapter_id)
        .join(Subject, Subject.id == Quiz.subject_id)
        .join(
            ClassSubject,
            (ClassSubject.class_id == Quiz.class_id)
            & (ClassSubject.subject_id == Quiz.subject_id)
            & (ClassSubject.school_id == student.school_id),
        )
        .where(
            Quiz.chapter_id == chapter_id,
            Quiz.class_id == academic_class.id,
            Quiz.is_active.is_(True),
            Chapter.class_id == academic_class.id,
            Chapter.is_active.is_(True),
            Subject.school_id == student.school_id,
            Subject.is_active.is_(True),
        )
        .order_by(Quiz.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    return quiz


def _attempt_for_student(
    db: Session,
    attempt_id: UUID,
    student: User,
    *,
    lock: bool = False,
) -> QuizAttempt:
    statement = (
        select(QuizAttempt)
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
        .join(
            AcademicClass,
            and_(
                AcademicClass.id == QuizAttempt.class_id,
                AcademicClass.school_id == QuizAttempt.school_id,
                AcademicClass.is_active.is_(True),
            ),
        )
        .where(
            QuizAttempt.id == attempt_id,
            QuizAttempt.student_id == student.id,
            QuizAttempt.school_id == student.school_id,
        )
    )
    if lock:
        statement = statement.with_for_update()
    attempt = db.execute(statement).scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")
    return attempt


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _expires_at(attempt: QuizAttempt, settings: Settings) -> datetime:
    return _utc(attempt.started_at) + timedelta(minutes=settings.quiz_duration_minutes)


def _eligible_snapshots(
    db: Session,
    quiz: Quiz,
    language: LanguageCode,
    school_id: UUID,
    question_count: int,
) -> tuple[list[dict[str, Any]], LanguageCode]:
    questions = list(
        db.execute(
            select(Question)
            .join(QuizQuestion, QuizQuestion.question_id == Question.id)
            .where(
                QuizQuestion.quiz_id == quiz.id,
                QuizQuestion.class_id == quiz.class_id,
                QuizQuestion.subject_id == quiz.subject_id,
                QuizQuestion.chapter_id == quiz.chapter_id,
                Question.school_id == school_id,
                Question.subject_id == quiz.subject_id,
                Question.chapter_id == quiz.chapter_id,
                Question.status == QuestionStatus.APPROVED,
                Question.question_type == QuestionType.SINGLE_CHOICE,
            )
            .distinct()
            .options(
                selectinload(Question.translations),
                selectinload(Question.options).selectinload(QuestionOption.translations),
            )
        ).scalars()
    )
    fallback_languages = [language, LanguageCode.EN, LanguageCode.HI, LanguageCode.MR]
    for actual_language in dict.fromkeys(fallback_languages):
        snapshots: list[dict[str, Any]] = []
        for question in questions:
            translation_by_language = {
                translation.language_code: translation
                for translation in question.translations
            }
            question_translation = translation_by_language.get(actual_language)
            if question_translation is None:
                continue
            option_snapshots = []
            correct_option_id = None
            valid = len(question.options) == 4
            for option in question.options:
                option_translation = next(
                    (
                        translation
                        for translation in option.translations
                        if translation.language_code == actual_language
                    ),
                    None,
                )
                if option_translation is None:
                    valid = False
                    break
                option_snapshots.append(
                    {"id": str(option.id), "text": option_translation.option_text}
                )
                if option.is_correct:
                    if correct_option_id is not None:
                        valid = False
                        break
                    correct_option_id = str(option.id)
            if not valid or correct_option_id is None:
                continue
            _secure_random.shuffle(option_snapshots)
            snapshots.append(
                {
                    "question_id": question.id,
                    "question_translation_id": question_translation.id,
                    "language": actual_language,
                    "question_text": question_translation.question_text,
                    "snapshot": {
                        "options": option_snapshots,
                        "correct_option_id": correct_option_id,
                        "explanation": question_translation.explanation,
                    },
                }
            )
        if len(snapshots) >= question_count:
            return snapshots, actual_language
    return [], LanguageCode.EN


def _answer_map(db: Session, attempt_id: UUID) -> dict[UUID, StudentAnswer]:
    answers = db.execute(
        select(StudentAnswer)
        .join(AttemptQuestion, AttemptQuestion.id == StudentAnswer.attempt_question_id)
        .where(AttemptQuestion.attempt_id == attempt_id)
    ).scalars()
    return {answer.attempt_question_id: answer for answer in answers}


def _attempt_questions(db: Session, attempt_id: UUID) -> list[AttemptQuestion]:
    return list(
        db.execute(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt_id)
            .order_by(AttemptQuestion.display_order)
        ).scalars()
    )


def _complete_attempt(attempt: QuizAttempt, db: Session, now: datetime) -> None:
    if attempt.status == AttemptStatus.COMPLETED:
        return
    questions = _attempt_questions(db, attempt.id)
    answers = _answer_map(db, attempt.id)
    correct_count = 0
    unanswered_count = 0
    for question in questions:
        answer = answers.get(question.id)
        if answer is None:
            unanswered_count += 1
            continue
        answer.is_correct = (
            str(answer.selected_option_id)
            == question.question_snapshot["correct_option_id"]
        )
        if answer.is_correct:
            correct_count += 1
    total = len(questions)
    incorrect_count = total - correct_count - unanswered_count
    attempt.total_questions = total
    attempt.correct_answers = correct_count
    attempt.incorrect_answers = incorrect_count
    attempt.unanswered_questions = unanswered_count
    attempt.score = correct_count
    attempt.percentage = round((correct_count * 100 / total), 2) if total else 0
    attempt.completed_at = now
    attempt.status = AttemptStatus.COMPLETED


def _result_response(
    attempt: QuizAttempt,
    db: Session,
) -> dict[str, Any]:
    questions = _attempt_questions(db, attempt.id)
    answers = _answer_map(db, attempt.id)
    result_questions = []
    for question in questions:
        answer = answers.get(question.id)
        correct_option_id = question.question_snapshot["correct_option_id"]
        selected_option_id = str(answer.selected_option_id) if answer else None
        result_questions.append(
            {
                "attempt_question_id": question.id,
                "display_order": question.display_order,
                "question_text": question.question_text_snapshot,
                "options": [
                    {
                        "id": option["id"],
                        "text": option["text"],
                        "is_correct": option["id"] == correct_option_id,
                    }
                    for option in question.question_snapshot["options"]
                ],
                "selected_option_id": selected_option_id,
                "correct_option_id": correct_option_id,
                "explanation": question.question_snapshot.get("explanation"),
                "is_correct": selected_option_id == correct_option_id,
                "language_code": question.selected_language,
            }
        )
    return {
        "status": "COMPLETED",
        "attempt_id": attempt.id,
        "quiz_title": db.get(Quiz, attempt.quiz_id).title,
        "started_at": _utc(attempt.started_at),
        "completed_at": _utc(attempt.completed_at) if attempt.completed_at else None,
        "total_questions": attempt.total_questions,
        "correct_answers": attempt.correct_answers,
        "incorrect_answers": attempt.incorrect_answers,
        "unanswered_questions": attempt.unanswered_questions,
        "score": attempt.score,
        "percentage": float(attempt.percentage),
        "time_taken_seconds": max(
            0,
            int(
                (
                    _utc(attempt.completed_at or attempt.started_at)
                    - _utc(attempt.started_at)
                ).total_seconds()
            ),
        ),
        "language_code": questions[0].selected_language if questions else LanguageCode.EN,
        "questions": result_questions,
    }


def _attempt_response(
    attempt: QuizAttempt,
    db: Session,
    settings: Settings,
    now: datetime,
) -> dict[str, Any]:
    answers = _answer_map(db, attempt.id)
    questions = _attempt_questions(db, attempt.id)
    seconds_remaining = max(0, int((_expires_at(attempt, settings) - now).total_seconds()))
    return {
        "status": "IN_PROGRESS",
        "attempt_id": attempt.id,
        "quiz_title": db.get(Quiz, attempt.quiz_id).title,
        "started_at": _utc(attempt.started_at),
        "expires_at": _expires_at(attempt, settings),
        "remaining_seconds": seconds_remaining,
        "total_questions": len(questions),
        "language_code": questions[0].selected_language if questions else LanguageCode.EN,
        "questions": [
            {
                "attempt_question_id": question.id,
                "display_order": question.display_order,
                "question_text": question.question_text_snapshot,
                "options": question.question_snapshot["options"],
                "selected_option_id": (
                    answers[question.id].selected_option_id
                    if question.id in answers
                    else None
                ),
                "language_code": question.selected_language,
                "feedback": (
                    {
                        "is_correct": answers[question.id].is_correct,
                        "correct_option_id": question.question_snapshot[
                            "correct_option_id"
                        ],
                        "explanation": question.question_snapshot.get(
                            "explanation"
                        ),
                    }
                    if question.id in answers
                    and answers[question.id].is_correct is not None
                    else None
                ),
            }
            for question in questions
        ],
    }


def _current_attempt_state(
    attempt: QuizAttempt,
    db: Session,
    settings: Settings,
    now: datetime,
) -> dict[str, Any]:
    if attempt.status == AttemptStatus.IN_PROGRESS and now >= _expires_at(attempt, settings):
        _complete_attempt(attempt, db, now)
        db.commit()
    if attempt.status == AttemptStatus.COMPLETED:
        return _result_response(attempt, db)
    return _attempt_response(attempt, db, settings, now)


def _completed_attempt_filter(
    student: User,
    academic_class: AcademicClass,
):
    return (
        QuizAttempt.student_id == student.id,
        QuizAttempt.school_id == student.school_id,
        QuizAttempt.class_id == academic_class.id,
        QuizAttempt.status == AttemptStatus.COMPLETED,
        QuizAttempt.completed_at.is_not(None),
        Subject.school_id == student.school_id,
        Chapter.class_id == academic_class.id,
    )


def _completed_attempt_records(
    db: Session,
    student: User,
    academic_class: AcademicClass,
):
    return (
        select(QuizAttempt, Quiz, Subject, Chapter)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Subject, Subject.id == QuizAttempt.subject_id)
        .join(Chapter, Chapter.id == QuizAttempt.chapter_id)
        .where(*_completed_attempt_filter(student, academic_class))
    )


def _history_item(
    attempt: QuizAttempt,
    quiz: Quiz,
    subject: Subject,
    chapter: Chapter,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt.id,
        "quiz_title": quiz.title,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "chapter_id": chapter.id,
        "chapter_title": chapter.title,
        "score": attempt.score,
        "total_questions": attempt.total_questions,
        "percentage": float(attempt.percentage),
        "completed_at": _utc(attempt.completed_at),
    }


@router.get("/quiz/history", response_model=QuizHistoryResponse)
def get_quiz_history(
    subject_id: UUID | None = None,
    chapter_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be on or before date_to.",
        )
    academic_class = _active_class(db, student)
    query = _completed_attempt_records(db, student, academic_class)
    if subject_id is not None:
        query = query.where(QuizAttempt.subject_id == subject_id)
    if chapter_id is not None:
        query = query.where(QuizAttempt.chapter_id == chapter_id)
    if date_from is not None:
        query = query.where(
            QuizAttempt.completed_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        query = query.where(
            QuizAttempt.completed_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    total_items = db.execute(
        query.with_only_columns(func.count(QuizAttempt.id)).order_by(None)
    ).scalar_one()
    records = db.execute(
        query.order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            _history_item(attempt, quiz, subject, chapter)
            for attempt, quiz, subject, chapter in records
        ],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": (total_items + page_size - 1) // page_size,
    }


@router.get("/quiz/analytics", response_model=QuizAnalyticsResponse)
def get_quiz_analytics(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    academic_class = _active_class(db, student)
    base_query = _completed_attempt_records(db, student, academic_class)
    totals = db.execute(
        select(
            func.count(QuizAttempt.id),
            func.coalesce(func.sum(QuizAttempt.total_questions), 0),
            func.coalesce(func.sum(QuizAttempt.score), 0),
            func.avg(QuizAttempt.percentage),
            func.max(QuizAttempt.percentage),
        )
        .select_from(QuizAttempt)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Subject, Subject.id == QuizAttempt.subject_id)
        .join(Chapter, Chapter.id == QuizAttempt.chapter_id)
        .where(*_completed_attempt_filter(student, academic_class))
    ).one()
    subject_records = db.execute(
        select(
            Subject.id,
            Subject.name,
            func.count(QuizAttempt.id),
            func.avg(QuizAttempt.percentage),
        )
        .select_from(QuizAttempt)
        .join(Subject, Subject.id == QuizAttempt.subject_id)
        .join(Chapter, Chapter.id == QuizAttempt.chapter_id)
        .where(*_completed_attempt_filter(student, academic_class))
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    ).all()
    chapter_records = db.execute(
        select(
            Chapter.id,
            Chapter.title,
            Subject.id,
            Subject.name,
            func.count(QuizAttempt.id),
            func.avg(QuizAttempt.percentage),
        )
        .select_from(QuizAttempt)
        .join(Subject, Subject.id == QuizAttempt.subject_id)
        .join(Chapter, Chapter.id == QuizAttempt.chapter_id)
        .where(*_completed_attempt_filter(student, academic_class))
        .group_by(Chapter.id, Chapter.title, Subject.id, Subject.name)
        .order_by(Chapter.title)
    ).all()
    recent_records = db.execute(
        base_query.order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
        .limit(5)
    ).all()
    subject_performance = [
        {
            "subject_id": subject_id,
            "subject_name": subject_name,
            "completed_quizzes": completed_quizzes,
            "average_percentage": round(float(average_percentage), 2),
        }
        for subject_id, subject_name, completed_quizzes, average_percentage in subject_records
    ]
    chapter_performance = [
        {
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "completed_quizzes": completed_quizzes,
            "average_percentage": round(float(average_percentage), 2),
        }
        for chapter_id, chapter_title, subject_id, subject_name, completed_quizzes, average_percentage in chapter_records
    ]
    return {
        "total_completed_quizzes": totals[0],
        "total_questions": totals[1],
        "total_correct_answers": totals[2],
        "average_percentage": round(float(totals[3]), 2) if totals[3] is not None else 0,
        "highest_percentage": round(float(totals[4]), 2) if totals[4] is not None else 0,
        "recent_activity": [
            _history_item(attempt, quiz, subject, chapter)
            for attempt, quiz, subject, chapter in recent_records
        ],
        "subject_performance": subject_performance,
        "chapter_performance": chapter_performance,
        "strongest_subjects": [
            item
            for item in sorted(
                subject_performance,
                key=lambda item: item["average_percentage"],
                reverse=True,
            )
            if item["average_percentage"] >= 80
        ],
        "needs_improvement_subjects": [
            item
            for item in subject_performance
            if item["average_percentage"] < 60
        ],
        "strongest_chapters": [
            item
            for item in sorted(
                chapter_performance,
                key=lambda item: item["average_percentage"],
                reverse=True,
            )
            if item["average_percentage"] >= 80
        ],
        "needs_improvement_chapters": [
            item
            for item in chapter_performance
            if item["average_percentage"] < 60
        ],
    }


@router.get(
    "/chapters/{chapter_id}/quiz/current",
    response_model=QuizReadyResponse | QuizAttemptResponse | QuizResultResponse,
)
def get_current_quiz(
    chapter_id: UUID,
    class_id: UUID | None = Query(default=None),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    academic_class = _active_class(db, student, class_id)
    quiz = _available_quiz(db, student, academic_class, chapter_id)
    now = datetime.now(timezone.utc)
    attempt = db.execute(
        select(QuizAttempt)
        .where(
            QuizAttempt.student_id == student.id,
            QuizAttempt.school_id == student.school_id,
            QuizAttempt.class_id == academic_class.id,
            QuizAttempt.quiz_id == quiz.id,
        )
        .order_by(QuizAttempt.attempt_number.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if attempt is not None:
        return _current_attempt_state(attempt, db, settings, now)
    return {
        "status": "NOT_STARTED",
        "quiz_id": quiz.id,
        "quiz_title": quiz.title,
        "total_questions": settings.quiz_question_count,
        "duration_minutes": settings.quiz_duration_minutes,
    }


@router.post(
    "/chapters/{chapter_id}/quiz/start",
    response_model=QuizAttemptResponse | QuizResultResponse,
    status_code=status.HTTP_200_OK,
)
def start_or_resume_quiz(
    chapter_id: UUID,
    payload: QuizStartRequest,
    class_id: UUID | None = Query(default=None),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    academic_class = _active_class(db, student, class_id)
    quiz = _available_quiz(db, student, academic_class, chapter_id)
    quiz = db.execute(
        select(Quiz).where(Quiz.id == quiz.id).with_for_update()
    ).scalar_one()
    now = datetime.now(timezone.utc)
    existing = db.execute(
        select(QuizAttempt)
        .where(
            QuizAttempt.student_id == student.id,
            QuizAttempt.school_id == student.school_id,
            QuizAttempt.class_id == academic_class.id,
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return _current_attempt_state(existing, db, settings, now)

    candidates, _ = _eligible_snapshots(
        db,
        quiz,
        payload.language_code,
        student.school_id,
        settings.quiz_question_count,
    )
    if len(candidates) < settings.quiz_question_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This quiz needs {settings.quiz_question_count} approved, "
                "complete questions before it can start."
            ),
        )
    selected = _secure_random.sample(candidates, settings.quiz_question_count)
    attempt_number = db.execute(
        select(func.coalesce(func.max(QuizAttempt.attempt_number), 0)).where(
            QuizAttempt.student_id == student.id,
            QuizAttempt.quiz_id == quiz.id,
        )
    ).scalar_one() + 1
    now = datetime.now(timezone.utc)
    attempt = QuizAttempt(
        student_id=student.id,
        school_id=student.school_id,
        quiz_id=quiz.id,
        class_id=academic_class.id,
        subject_id=quiz.subject_id,
        chapter_id=quiz.chapter_id,
        attempt_number=attempt_number,
        started_at=now,
        status=AttemptStatus.IN_PROGRESS,
        total_questions=settings.quiz_question_count,
        correct_answers=0,
        incorrect_answers=0,
        unanswered_questions=settings.quiz_question_count,
        score=0,
        percentage=0,
    )
    db.add(attempt)
    db.flush()
    for order, candidate in enumerate(selected, start=1):
        db.add(
            AttemptQuestion(
                attempt_id=attempt.id,
                question_id=candidate["question_id"],
                class_id=quiz.class_id,
                subject_id=quiz.subject_id,
                chapter_id=quiz.chapter_id,
                question_translation_id=candidate["question_translation_id"],
                display_order=order,
                selected_language=candidate["language"],
                question_text_snapshot=candidate["question_text"],
                question_snapshot=candidate["snapshot"],
                option_order_snapshot=[
                    option["id"] for option in candidate["snapshot"]["options"]
                ],
            )
        )
    db.commit()
    return _attempt_response(attempt, db, settings, now)


@router.get(
    "/quiz/attempts/{attempt_id}",
    response_model=QuizAttemptResponse | QuizResultResponse,
)
def get_quiz_attempt(
    attempt_id: UUID,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    attempt = _attempt_for_student(db, attempt_id, student, lock=True)
    return _current_attempt_state(attempt, db, settings, datetime.now(timezone.utc))


@router.put(
    "/quiz/attempts/{attempt_id}/answers/{attempt_question_id}",
    response_model=QuizAttemptResponse | QuizResultResponse,
)
def save_quiz_answer(
    attempt_id: UUID,
    attempt_question_id: UUID,
    payload: QuizAnswerRequest,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    attempt = _attempt_for_student(db, attempt_id, student, lock=True)
    now = datetime.now(timezone.utc)
    if attempt.status == AttemptStatus.COMPLETED or now >= _expires_at(attempt, settings):
        if attempt.status == AttemptStatus.IN_PROGRESS:
            _complete_attempt(attempt, db, now)
            db.commit()
        return _result_response(attempt, db)
    question = db.execute(
        select(AttemptQuestion)
        .where(
            AttemptQuestion.id == attempt_question_id,
            AttemptQuestion.attempt_id == attempt.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Quiz question not found.")
    allowed_option_ids = {
        option["id"] for option in question.question_snapshot["options"]
    }
    if str(payload.selected_option_id) not in allowed_option_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected option does not belong to this question.",
        )
    answer = db.execute(
        select(StudentAnswer)
        .where(StudentAnswer.attempt_question_id == question.id)
        .with_for_update()
    ).scalar_one_or_none()
    if answer is not None:
        if answer.selected_option_id != payload.selected_option_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This question has already been answered and cannot be changed.",
            )
        return _attempt_response(attempt, db, settings, now)

    questions = _attempt_questions(db, attempt.id)
    answers = _answer_map(db, attempt.id)
    next_question = next(
        (candidate for candidate in questions if candidate.id not in answers),
        None,
    )
    if next_question is None or next_question.id != question.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answer the current quiz question before continuing.",
        )
    is_correct = (
        str(payload.selected_option_id)
        == question.question_snapshot["correct_option_id"]
    )
    db.add(
        StudentAnswer(
            attempt_question_id=question.id,
            question_id=question.question_id,
            selected_option_id=payload.selected_option_id,
            answered_at=now,
            is_correct=is_correct,
        )
    )
    db.commit()
    return _attempt_response(attempt, db, settings, now)


@router.post(
    "/quiz/attempts/{attempt_id}/submit",
    response_model=QuizResultResponse,
)
def submit_quiz(
    attempt_id: UUID,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    attempt = _attempt_for_student(db, attempt_id, student, lock=True)
    _complete_attempt(attempt, db, datetime.now(timezone.utc))
    db.commit()
    return _result_response(attempt, db)


@router.get(
    "/quiz/attempts/{attempt_id}/result",
    response_model=QuizResultResponse,
)
def get_quiz_result(
    attempt_id: UUID,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    attempt = _attempt_for_student(db, attempt_id, student, lock=True)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        if datetime.now(timezone.utc) < _expires_at(attempt, settings):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The quiz has not been submitted.",
            )
        _complete_attempt(attempt, db, datetime.now(timezone.utc))
        db.commit()
    return _result_response(attempt, db)

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock3 } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LoadingState } from "@/components/LoadingState";
import { useLanguage } from "@/hooks/useLanguage";
import { studentService } from "@/services/student-service";
import type {
  QuizAttempt,
  QuizCurrent,
  QuizReady,
  QuizResult,
} from "@/types/student-quiz";

function isQuizReady(session: QuizCurrent): session is QuizReady {
  return session.status === "NOT_STARTED";
}

function isQuizAttempt(session: QuizCurrent): session is QuizAttempt {
  return session.status === "IN_PROGRESS";
}

function isQuizResult(session: QuizCurrent): session is QuizResult {
  return session.status === "COMPLETED";
}

export function StudentQuizResultView({
  result,
  backLink,
  backLabel,
  onRetry,
  retryPending = false,
}: {
  result: QuizResult;
  backLink: string;
  backLabel: string;
  onRetry?: () => void;
  retryPending?: boolean;
}) {
  return (
    <div className="student-page">
      <Link className="student-back-link" to={backLink}>
        <ArrowLeft aria-hidden="true" size={15} /> {backLabel}
      </Link>
      <div className="student-page-heading">
        <div className="student-eyebrow">Quiz results</div>
        <h1>{result.quiz_title}</h1>
        <p>
          You scored {result.score} out of {result.total_questions} (
          {result.percentage}%).
        </p>
        <p>
          Completed {new Date(result.completed_at).toLocaleString()} · Language:{" "}
          {result.language_code.toUpperCase()}
        </p>
        <p>Time taken: {formatTime(result.time_taken_seconds)}</p>
      </div>
      <section className="student-quiz-result-summary">
        <div>
          <strong>{result.correct_answers}</strong>
          <span>Correct</span>
        </div>
        <div>
          <strong>{result.incorrect_answers}</strong>
          <span>Incorrect</span>
        </div>
        <div>
          <strong>{result.unanswered_questions}</strong>
          <span>Unanswered</span>
        </div>
      </section>
      <section className="student-content-panel">
        <h2>Answer review</h2>
        <ol className="student-quiz-review-list">
          {result.questions.map((question) => (
            <li key={question.attempt_question_id}>
              <div className="student-quiz-review-heading">
                <strong>
                  {question.display_order}. {question.question_text}
                </strong>
                <span className={question.is_correct ? "correct" : "incorrect"}>
                  {question.is_correct
                    ? "Correct"
                    : question.selected_option_id
                      ? "Not quite"
                      : "Unanswered"}
                </span>
              </div>
              <ul>
                {question.options.map((option) => (
                  <li
                    key={option.id}
                    className={[
                      option.is_correct ? "correct" : "",
                      option.id === question.selected_option_id &&
                      !option.is_correct
                        ? "incorrect"
                        : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    {option.text}
                    {option.is_correct ? " · Correct answer" : ""}
                    {option.id === question.selected_option_id
                      ? " · Your answer"
                      : ""}
                  </li>
                ))}
              </ul>
              {question.explanation ? <p>{question.explanation}</p> : null}
            </li>
          ))}
        </ol>
      </section>
      {onRetry ? (
        <button
          className="admin-button primary"
          disabled={retryPending}
          onClick={onRetry}
        >
          {retryPending ? "Preparing quiz…" : "Try another attempt"}
        </button>
      ) : null}
    </div>
  );
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export function StudentQuizPage() {
  const { chapterId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const { language } = useLanguage();
  const [sessionOverride, setSessionOverride] = useState<QuizCurrent | null>(
    null,
  );
  const [questionIndex, setQuestionIndex] = useState<number | null>(null);
  const [quizLanguage, setQuizLanguage] = useState(language);
  const [now, setNow] = useState(Date.now());
  const autoSubmittedAttempt = useRef<string | null>(null);
  const currentQuiz = useQuery({
    queryKey: ["student", "quiz", chapterId, classId],
    queryFn: () => studentService.currentQuiz(chapterId, classId),
    enabled: Boolean(chapterId),
  });
  const session = sessionOverride ?? currentQuiz.data;

  const startQuiz = useMutation({
    mutationFn: () =>
      studentService.startQuiz(chapterId, quizLanguage, classId),
    onSuccess: (nextSession) => {
      setSessionOverride(nextSession);
      setQuestionIndex(0);
      autoSubmittedAttempt.current = null;
    },
  });
  const saveAnswer = useMutation({
    mutationFn: ({
      attemptId,
      questionId,
      optionId,
    }: {
      attemptId: string;
      questionId: string;
      optionId: string;
    }) => studentService.saveQuizAnswer(attemptId, questionId, optionId),
    onSuccess: (nextSession) => setSessionOverride(nextSession),
  });
  const submitQuiz = useMutation({
    mutationFn: studentService.submitQuiz,
    onSuccess: (result) => {
      setSessionOverride(result);
    },
  });
  const submitAttempt = submitQuiz.mutate;
  const isSubmitting = submitQuiz.isPending;

  const activeAttempt = session && isQuizAttempt(session) ? session : null;
  const isActive = activeAttempt !== null;
  const expiresAt = activeAttempt ? Date.parse(activeAttempt.expires_at) : null;
  const remainingSeconds =
    expiresAt === null ? 0 : Math.max(0, Math.ceil((expiresAt - now) / 1000));

  useEffect(() => {
    if (!isActive) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isActive]);

  useEffect(() => {
    if (
      !session ||
      !isQuizAttempt(session) ||
      remainingSeconds > 0 ||
      isSubmitting ||
      autoSubmittedAttempt.current === session.attempt_id
    ) {
      return;
    }
    autoSubmittedAttempt.current = session.attempt_id;
    submitAttempt(session.attempt_id);
  }, [isSubmitting, remainingSeconds, session, submitAttempt]);

  if (currentQuiz.isLoading) {
    return <LoadingState label="Loading quiz…" />;
  }
  if (currentQuiz.isError || !session) {
    return (
      <div className="student-page">
        <div className="student-error" role="alert">
          <p>{currentQuiz.error?.message || "Could not load this quiz."}</p>
          <button
            className="admin-button secondary"
            onClick={() => void currentQuiz.refetch()}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const title = session.quiz_title;
  const goToChapter = (
    <Link
      className="student-back-link"
      to={`/student/chapters/${chapterId}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
    >
      <ArrowLeft aria-hidden="true" size={15} /> Chapter overview
    </Link>
  );

  if (isQuizReady(session)) {
    return (
      <div className="student-page">
        {goToChapter}
        <div className="student-page-heading">
          <div className="student-eyebrow">Chapter quiz</div>
          <h1>{title}</h1>
          <p>Read the instructions before you begin.</p>
        </div>
        <section className="student-content-panel student-quiz-instructions">
          <h2>Before you start</h2>
          <ul>
            <li>
              There are exactly {session.total_questions} questions and you have{" "}
              {session.duration_minutes} minutes.
            </li>
            <li>Each answer is checked immediately and cannot be changed.</li>
            <li>
              The quiz is submitted automatically when the timer runs out.
            </li>
          </ul>
          <label className="student-quiz-language">
            Quiz language
            <select
              value={quizLanguage}
              onChange={(event) =>
                setQuizLanguage(
                  event.target.value as "en" | "hi" | "mr",
                )
              }
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="mr">Marathi</option>
            </select>
          </label>
          {startQuiz.isError ? (
            <p className="student-error-message" role="alert">
              {startQuiz.error.message}
            </p>
          ) : null}
          <button
            className="admin-button primary"
            disabled={startQuiz.isPending}
            onClick={() => startQuiz.mutate()}
          >
            {startQuiz.isPending ? "Preparing quiz…" : "Begin quiz"}
          </button>
        </section>
      </div>
    );
  }

  if (isQuizResult(session)) {
    return (
      <StudentQuizResultView
        result={session}
        backLink={`/student/chapters/${chapterId}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
        backLabel="Chapter overview"
        onRetry={() => startQuiz.mutate()}
        retryPending={startQuiz.isPending}
      />
    );
  }

  const firstUnansweredIndex = session.questions.findIndex(
    (question) => question.feedback === null,
  );
  const currentQuestionIndex =
    questionIndex ??
    (firstUnansweredIndex < 0
      ? session.questions.length - 1
      : firstUnansweredIndex);
  const currentQuestion = session.questions[currentQuestionIndex];
  const answeredCount = session.questions.filter(
    (question) => question.feedback !== null,
  ).length;
  const feedback = currentQuestion.feedback;
  const submit = () => {
    autoSubmittedAttempt.current = session.attempt_id;
    submitQuiz.mutate(session.attempt_id);
  };

  return (
    <div className="student-page student-quiz-page">
      {goToChapter}
      <div className="student-quiz-header">
        <div>
          <div className="student-eyebrow">Chapter quiz</div>
          <h1>{title}</h1>
          <p>
            {answeredCount} of {session.total_questions} answered
          </p>
          <p>Language used: {session.language_code.toUpperCase()}</p>
        </div>
        <div
          className={`student-quiz-timer${remainingSeconds < 60 ? " urgent" : ""}`}
          role="timer"
          aria-label={`${Math.floor(remainingSeconds / 60)} minutes ${remainingSeconds % 60} seconds remaining`}
        >
          <Clock3 aria-hidden="true" size={18} />
          {formatTime(remainingSeconds)}
        </div>
      </div>
      <div
        className="student-quiz-progress-track"
        role="progressbar"
        aria-label="Quiz progress"
        aria-valuemin={0}
        aria-valuemax={session.total_questions}
        aria-valuenow={answeredCount}
      >
        <span
          style={{
            width: `${(answeredCount / session.total_questions) * 100}%`,
          }}
        />
      </div>
      <section className="student-content-panel student-quiz-question">
        <div className="student-quiz-question-count">
          Question {currentQuestionIndex + 1} of {session.total_questions}
        </div>
        <h2>{currentQuestion.question_text}</h2>
        <div className="student-quiz-options">
          {currentQuestion.options.map((option, index) => (
            <button
              type="button"
              key={option.id}
              className={[
                "student-quiz-option",
                option.id === currentQuestion.selected_option_id ? "selected" : "",
                feedback?.correct_option_id === option.id ? "correct" : "",
                option.id === currentQuestion.selected_option_id &&
                feedback &&
                !feedback.is_correct
                  ? "incorrect"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              disabled={saveAnswer.isPending || feedback !== null}
              aria-pressed={option.id === currentQuestion.selected_option_id}
              onClick={() =>
                saveAnswer.mutate({
                  attemptId: session.attempt_id,
                  questionId: currentQuestion.attempt_question_id,
                  optionId: option.id,
                })
              }
            >
              <span>{String.fromCharCode(65 + index)}</span>
              {option.text}
              {feedback?.correct_option_id === option.id ? (
                <CheckCircle2 aria-hidden="true" size={18} />
              ) : null}
            </button>
          ))}
        </div>
        {feedback ? (
          <div
            className={`student-quiz-feedback ${feedback.is_correct ? "correct" : "incorrect"}`}
            role="status"
          >
            <strong>
              {feedback.is_correct ? "Correct!" : "Incorrect"}
            </strong>
            {!feedback.is_correct ? (
              <span>
                Correct answer:{" "}
                {currentQuestion.options.find(
                  (option) => option.id === feedback.correct_option_id,
                )?.text ?? "See highlighted option"}
              </span>
            ) : null}
            {feedback.explanation ? <p>{feedback.explanation}</p> : null}
          </div>
        ) : null}
        {saveAnswer.isError ? (
          <p className="student-error-message" role="alert">
            {saveAnswer.error.message}
          </p>
        ) : null}
        {submitQuiz.isError ? (
          <p className="student-error-message" role="alert">
            {submitQuiz.error.message}
          </p>
        ) : null}
        <div className="student-quiz-navigation">
          <span>{feedback ? "Answered" : "Not answered"}</span>
          {currentQuestionIndex < session.questions.length - 1 ? (
            <button
              type="button"
              className="admin-button primary"
              disabled={!feedback || saveAnswer.isPending}
              onClick={() => setQuestionIndex(currentQuestionIndex + 1)}
            >
              Next Question <ArrowRight aria-hidden="true" size={15} />
            </button>
          ) : (
            <button
              type="button"
              className="admin-button primary"
              disabled={!feedback || submitQuiz.isPending}
              onClick={submit}
            >
              {submitQuiz.isPending ? "Finishing…" : "Finish Quiz"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

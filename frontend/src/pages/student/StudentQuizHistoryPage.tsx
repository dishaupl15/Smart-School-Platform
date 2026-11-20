import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingState } from "@/components/LoadingState";
import { studentService } from "@/services/student-service";
import { StudentQuizResultView } from "@/pages/student/StudentQuizPage";

function QueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="student-error" role="alert">
      <p>{message}</p>
      <button className="admin-button secondary" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function StudentQuizHistoryPage() {
  const [subjectId, setSubjectId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const subjects = useQuery({
    queryKey: ["student", "subjects"],
    queryFn: () => studentService.subjects(),
  });
  const chapters = useQuery({
    queryKey: ["student", "subjects", subjectId],
    queryFn: () => studentService.subject(subjectId),
    enabled: Boolean(subjectId),
  });
  const history = useQuery({
    queryKey: [
      "student",
      "quiz-history",
      subjectId,
      chapterId,
      dateFrom,
      dateTo,
      page,
    ],
    queryFn: () =>
      studentService.quizHistory({
        subject_id: subjectId || undefined,
        chapter_id: chapterId || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: 10,
      }),
  });

  const changeSubject = (value: string) => {
    setSubjectId(value);
    setChapterId("");
    setPage(1);
  };

  return (
    <div className="student-page">
      <div className="student-page-heading">
        <div className="student-eyebrow">Your progress</div>
        <h1>Quiz history</h1>
        <p>Review completed quizzes and revisit your answers.</p>
      </div>
      <section className="student-content-panel">
        <div className="quiz-history-filters">
          <label>
            Subject
            <select
              value={subjectId}
              onChange={(event) => changeSubject(event.target.value)}
              aria-label="Filter by subject"
            >
              <option value="">All subjects</option>
              {(subjects.data ?? []).map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chapter
            <select
              value={chapterId}
              disabled={!subjectId || chapters.isLoading}
              onChange={(event) => {
                setChapterId(event.target.value);
                setPage(1);
              }}
              aria-label="Filter by chapter"
            >
              <option value="">All chapters</option>
              {(chapters.data?.chapters ?? []).map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapter.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Completed from
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            Completed through
            <input
              type="date"
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        {subjects.isError ? (
          <QueryError
            message={subjects.error.message}
            onRetry={() => void subjects.refetch()}
          />
        ) : null}
      </section>

      {history.isLoading ? (
        <LoadingState label="Loading your quiz history…" />
      ) : history.isError ? (
        <QueryError
          message={history.error.message}
          onRetry={() => void history.refetch()}
        />
      ) : history.data?.items.length ? (
        <>
          <ul className="quiz-history-list">
            {history.data.items.map((item) => (
              <li key={item.attempt_id}>
                <CheckCircle2 aria-hidden="true" size={20} />
                <span>
                  <strong>{item.quiz_title}</strong>
                  <small>
                    {item.subject_name} · {item.chapter_title} ·{" "}
                    {new Date(item.completed_at).toLocaleString()}
                  </small>
                </span>
                <b>
                  {item.score}/{item.total_questions} · {item.percentage}%
                </b>
                <Link
                  className="admin-text-link"
                  to={`/student/quiz/history/${item.attempt_id}`}
                  aria-label={`Review ${item.quiz_title} results`}
                >
                  Review <ArrowRight aria-hidden="true" size={15} />
                </Link>
              </li>
            ))}
          </ul>
          <div className="quiz-history-pagination">
            <span>
              Page {history.data.page} of {history.data.total_pages} ·{" "}
              {history.data.total_items} completed quizzes
            </span>
            <div>
              <button
                type="button"
                className="admin-button secondary"
                disabled={page <= 1}
                onClick={() => setPage((current) => current - 1)}
              >
                <ArrowLeft aria-hidden="true" size={15} /> Previous
              </button>
              <button
                type="button"
                className="admin-button secondary"
                disabled={page >= history.data.total_pages}
                onClick={() => setPage((current) => current + 1)}
              >
                Next <ArrowRight aria-hidden="true" size={15} />
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="student-empty">
          <CheckCircle2 aria-hidden="true" size={24} />
          <strong>No completed quizzes found</strong>
          <span>
            Your finished quizzes will appear here. Try changing the filters.
          </span>
        </div>
      )}
    </div>
  );
}

export function StudentQuizResultPage() {
  const { attemptId = "" } = useParams();
  const result = useQuery({
    queryKey: ["student", "quiz-result", attemptId],
    queryFn: () => studentService.quizResult(attemptId),
    enabled: Boolean(attemptId),
  });

  if (result.isLoading)
    return <LoadingState label="Loading your quiz results…" />;
  if (result.isError || !result.data) {
    return (
      <div className="student-page">
        <QueryError
          message={result.error?.message || "Could not load these results."}
          onRetry={() => void result.refetch()}
        />
      </div>
    );
  }
  return (
    <StudentQuizResultView
      result={result.data}
      backLink="/student/quiz/history"
      backLabel="Quiz history"
    />
  );
}

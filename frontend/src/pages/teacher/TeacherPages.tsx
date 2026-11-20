import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  GraduationCap,
  Users,
} from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LoadingState } from "@/components/LoadingState";
import { teacherService } from "@/services/teacher-service";
import type {
  TeacherChapterPerformance,
  TeacherQuizResult,
  TeacherSubjectPerformance,
} from "@/types/teacher";

function PageHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="teacher-heading">
      <div className="teacher-eyebrow">Teacher workspace</div>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}

function QueryStatus({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error: boolean;
  retry: () => void;
}) {
  if (loading) return <LoadingState label="Loading your assigned classes…" />;
  if (!error) return null;
  return (
    <div className="teacher-empty" role="alert">
      <strong>We couldn’t load this information.</strong>
      <button className="admin-button secondary" onClick={retry}>
        Try again
      </button>
    </div>
  );
}

function StatCards({
  items,
}: {
  items: { label: string; value: string | number; icon: typeof Users }[];
}) {
  return (
    <section className="teacher-stats" aria-label="Teaching statistics">
      {items.map(({ label, value, icon: Icon }) => (
        <article className="teacher-stat" key={label}>
          <span className="teacher-stat-icon">
            <Icon size={19} aria-hidden="true" />
          </span>
          <span>{label}</span>
          <strong>{value}</strong>
        </article>
      ))}
    </section>
  );
}

function ResultsTable({ items }: { items: TeacherQuizResult[] }) {
  if (!items.length) {
    return (
      <div className="teacher-empty">
        <BookOpen size={22} aria-hidden="true" />
        <strong>No completed quiz results yet</strong>
        <span>
          Completed attempts from your assigned classes will appear here.
        </span>
      </div>
    );
  }
  return (
    <div className="teacher-table-wrap">
      <table className="teacher-table">
        <thead>
          <tr>
            <th>Student</th>
            <th>Class</th>
            <th>Quiz</th>
            <th>Score</th>
            <th>Completed</th>
            <th>
              <span className="sr-only">Student details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((result) => (
            <tr key={result.attempt_id}>
              <td data-label="Student">{result.student_name}</td>
              <td data-label="Class">
                {result.class_name} · {result.subject_name}
              </td>
              <td data-label="Quiz">{result.quiz_title}</td>
              <td data-label="Score">
                <strong>
                  {result.score}/{result.total_questions}
                </strong>{" "}
                <span className="teacher-score">
                  ({result.percentage.toFixed(1)}%)
                </span>
              </td>
              <td data-label="Completed">
                {new Date(result.completed_at).toLocaleDateString()}
              </td>
              <td>
                <Link
                  className="teacher-row-link"
                  aria-label={`View ${result.student_name} performance`}
                  to={`/teacher/students/${result.student_id}/performance?class_id=${result.class_id}`}
                >
                  <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PerformanceBars({
  title,
  items,
  label,
}: {
  title: string;
  items: (TeacherSubjectPerformance | TeacherChapterPerformance)[];
  label: (
    item: TeacherSubjectPerformance | TeacherChapterPerformance,
  ) => string;
}) {
  return (
    <section className="teacher-panel">
      <h2>{title}</h2>
      {items.length ? (
        <ul className="teacher-bars">
          {items.map((item) => (
            <li
              key={
                "chapter_id" in item
                  ? `${item.subject_id}-${item.chapter_id}`
                  : item.subject_id
              }
            >
              <div>
                <span>{label(item)}</span>
                <strong>{item.average_percentage.toFixed(1)}%</strong>
              </div>
              <span
                className="teacher-bar-track"
                role="progressbar"
                aria-label={`${label(item)} average`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={item.average_percentage}
              >
                <span
                  style={{
                    width: `${Math.min(100, Math.max(0, item.average_percentage))}%`,
                  }}
                />
              </span>
              <small>{item.completed_quiz_count} completed quizzes</small>
            </li>
          ))}
        </ul>
      ) : (
        <p className="teacher-muted">No completed quiz data yet.</p>
      )}
    </section>
  );
}

export function TeacherDashboardPage() {
  const query = useQuery({
    queryKey: ["teacher", "dashboard"],
    queryFn: teacherService.dashboard,
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  const dashboard = query.data;
  return (
    <div className="teacher-page">
      <PageHeading
        title="Dashboard"
        description="A focused view of the classes and learning outcomes you’re assigned to."
      />
      <StatCards
        items={[
          {
            label: "Assigned classes",
            value: dashboard.assigned_class_count,
            icon: GraduationCap,
          },
          {
            label: "Assigned subjects",
            value: dashboard.assigned_subject_count,
            icon: BookOpen,
          },
          { label: "Students", value: dashboard.student_count, icon: Users },
          {
            label: "Completed quizzes",
            value: dashboard.completed_quiz_count,
            icon: BarChart3,
          },
        ]}
      />
      <div className="teacher-summary">
        <span>Average score across assigned classes</span>
        <strong>{dashboard.average_percentage.toFixed(1)}%</strong>
      </div>
      <section className="teacher-panel">
        <div className="teacher-panel-heading">
          <div>
            <h2>Recent completed results</h2>
            <p>Only completed attempts in your assigned classes are shown.</p>
          </div>
          <Link className="teacher-text-link" to="/teacher/results">
            All results <ArrowRight size={15} />
          </Link>
        </div>
        <ResultsTable items={dashboard.recent_results} />
      </section>
    </div>
  );
}

export function TeacherClassesPage() {
  const query = useQuery({
    queryKey: ["teacher", "classes"],
    queryFn: teacherService.classes,
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  return (
    <div className="teacher-page">
      <PageHeading
        title="Assigned classes"
        description="Your active class and subject assignments."
      />
      {query.data.length ? (
        <div className="teacher-class-grid">
          {query.data.map((item) => (
            <article
              className="teacher-class-card"
              key={`${item.class_id}-${item.subject_id}`}
            >
              <span className="teacher-stat-icon">
                <GraduationCap size={19} />
              </span>
              <small>
                {item.academic_year} · Grade {item.grade_number}
                {item.section ? ` · Section ${item.section}` : ""}
              </small>
              <h2>{item.class_name}</h2>
              <p>{item.subject_name}</p>
              <div className="teacher-class-metrics">
                <span>
                  <Users size={15} /> {item.student_count} students
                </span>
                <span>{item.completed_quiz_count} completed quizzes</span>
                <strong>{item.average_percentage.toFixed(1)}% average</strong>
              </div>
              <Link to={`/teacher/classes/${item.class_id}/students`}>
                View students <ArrowRight size={15} />
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <div className="teacher-empty">
          <strong>No active class assignments</strong>
          <span>Ask your school administrator to assign your classes.</span>
        </div>
      )}
    </div>
  );
}

export function TeacherStudentsPage() {
  const { classId } = useParams();
  const query = useQuery({
    queryKey: ["teacher", "students", classId ?? "all"],
    queryFn: () => teacherService.students(classId),
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  const className = query.data[0]?.class_name;
  return (
    <div className="teacher-page">
      <PageHeading
        title={
          classId ? `${className ?? "Class"} students` : "Assigned students"
        }
        description="Students are listed only for your active assignments and their current enrollments."
      />
      {query.data.length ? (
        <section className="teacher-panel">
          <div className="teacher-table-wrap">
            <table className="teacher-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Class</th>
                  <th>Academic year</th>
                  <th>Completed quizzes</th>
                  <th>Average</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {query.data.map((student) => (
                  <tr key={`${student.student_id}-${student.class_id}`}>
                    <td data-label="Student">
                      <strong>{student.full_name}</strong>
                      <small>{student.email ?? "No email provided"}</small>
                    </td>
                    <td data-label="Class">{student.class_name}</td>
                    <td data-label="Academic year">{student.academic_year}</td>
                    <td data-label="Completed quizzes">
                      {student.completed_quiz_count}
                    </td>
                    <td data-label="Average">
                      {student.average_percentage.toFixed(1)}%
                    </td>
                    <td>
                      <Link
                        className="teacher-row-link"
                        to={`/teacher/students/${student.student_id}/performance?class_id=${student.class_id}`}
                        aria-label={`View ${student.full_name} performance`}
                      >
                        <ArrowRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div className="teacher-empty">
          <strong>No enrolled students</strong>
          <span>Students with active enrollments will appear here.</span>
        </div>
      )}
    </div>
  );
}

export function TeacherResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page") || 1));
  const query = useQuery({
    queryKey: ["teacher", "results", page],
    queryFn: () => teacherService.results(page),
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  return (
    <div className="teacher-page">
      <PageHeading
        title="Quiz results"
        description="Completed quiz attempts for your assigned classes."
      />
      <section className="teacher-panel">
        <p className="teacher-muted">
          {query.data.total_items} completed results
        </p>
        <ResultsTable items={query.data.items} />
        {query.data.total_pages > 1 && (
          <div className="teacher-pagination">
            <button
              disabled={page <= 1}
              onClick={() => setSearchParams({ page: String(page - 1) })}
            >
              Previous
            </button>
            <span>
              Page {page} of {query.data.total_pages}
            </span>
            <button
              disabled={page >= query.data.total_pages}
              onClick={() => setSearchParams({ page: String(page + 1) })}
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export function TeacherStudentPerformancePage() {
  const { studentId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const query = useQuery({
    queryKey: ["teacher", "performance", studentId, classId],
    queryFn: () => teacherService.studentPerformance(studentId, classId),
    enabled: Boolean(studentId),
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  const performance = query.data;
  return (
    <div className="teacher-page">
      <PageHeading
        title={performance.full_name}
        description={`${performance.class_name} · Academic year ${performance.academic_year}`}
      />
      <StatCards
        items={[
          {
            label: "Completed quizzes",
            value: performance.completed_quiz_count,
            icon: BookOpen,
          },
          {
            label: "Average score",
            value: `${performance.average_percentage.toFixed(1)}%`,
            icon: BarChart3,
          },
          {
            label: "Correct answers",
            value: performance.total_correct_answers,
            icon: GraduationCap,
          },
        ]}
      />
      <div className="teacher-analytics-grid">
        <PerformanceBars
          title="Subject performance"
          items={performance.subject_performance}
          label={(item) => item.subject_name}
        />
        <PerformanceBars
          title="Chapter performance"
          items={performance.chapter_performance}
          label={(item) =>
            "chapter_title" in item
              ? `${item.subject_name} · ${item.chapter_title}`
              : item.subject_name
          }
        />
      </div>
      <section className="teacher-panel">
        <h2>Completed quiz history</h2>
        <ResultsTable items={performance.recent_results} />
      </section>
      <Link className="teacher-text-link" to="/teacher/students">
        Back to students
      </Link>
    </div>
  );
}

export function TeacherAnalyticsPage() {
  const query = useQuery({
    queryKey: ["teacher", "analytics"],
    queryFn: teacherService.analytics,
  });
  if (query.isLoading || query.isError || !query.data) {
    return (
      <QueryStatus
        loading={query.isLoading}
        error={query.isError}
        retry={() => void query.refetch()}
      />
    );
  }
  const analytics = query.data;
  return (
    <div className="teacher-page">
      <PageHeading
        title="Class analytics"
        description="Performance trends across your active teaching assignments."
      />
      <StatCards
        items={[
          { label: "Students", value: analytics.student_count, icon: Users },
          {
            label: "Completed quizzes",
            value: analytics.completed_quiz_count,
            icon: BookOpen,
          },
          {
            label: "Average score",
            value: `${analytics.average_percentage.toFixed(1)}%`,
            icon: BarChart3,
          },
          {
            label: "Highest score",
            value: `${analytics.highest_percentage.toFixed(1)}%`,
            icon: GraduationCap,
          },
        ]}
      />
      <div className="teacher-analytics-grid">
        <PerformanceBars
          title="Subject performance"
          items={analytics.subject_performance}
          label={(item) => item.subject_name}
        />
        <PerformanceBars
          title="Chapter performance"
          items={analytics.chapter_performance}
          label={(item) =>
            "chapter_title" in item
              ? `${item.subject_name} · ${item.chapter_title}`
              : item.subject_name
          }
        />
      </div>
      <section className="teacher-panel">
        <h2>Recent completed results</h2>
        <ResultsTable items={analytics.recent_results} />
      </section>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  BookText,
  CheckCircle2,
  GraduationCap,
  Layers3,
  Sparkles,
  Target,
  Trophy,
  UserRound,
} from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LoadingState } from "@/components/LoadingState";
import { studentService } from "@/services/student-service";
import type { QuizAnalytics } from "@/types/student-quiz";
import type { StudentSubjectSummary } from "@/types/student";

function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="student-page-heading">
      <div className="student-eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}

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

function SubjectCard({
  subject,
  classId,
}: {
  subject: StudentSubjectSummary;
  classId?: string;
}) {
  return (
    <Link
      className="student-subject-card"
      to={`/student/subjects/${subject.id}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
    >
      <span className="student-subject-icon">
        <BookOpen aria-hidden="true" size={21} />
      </span>
      <span className="student-subject-copy">
        <small>{subject.code}</small>
        <strong>{subject.name}</strong>
        <span>
          {subject.description || "Explore the chapters in this subject."}
        </span>
      </span>
      <span className="student-subject-footer">
        <span>
          {subject.chapter_count}{" "}
          {subject.chapter_count === 1 ? "chapter" : "chapters"}
        </span>
        <ArrowRight aria-hidden="true" size={17} />
      </span>
    </Link>
  );
}

function SubjectGrid({
  subjects,
  classId,
}: {
  subjects: StudentSubjectSummary[];
  classId?: string;
}) {
  if (!subjects.length) {
    return (
      <div className="student-empty">
        <BookOpen aria-hidden="true" size={24} />
        <strong>No subjects are available yet</strong>
        <span>
          Your class subjects will appear here when they are assigned.
        </span>
      </div>
    );
  }
  return (
    <div className="student-subject-grid">
      {subjects.map((subject) => (
        <SubjectCard key={subject.id} subject={subject} classId={classId} />
      ))}
    </div>
  );
}

function EnrollmentLabel({
  className,
  grade,
  section,
  year,
}: {
  className: string;
  grade: number;
  section: string | null;
  year: string;
}) {
  return (
    <span>
      {className} · Grade {grade}
      {section ? `, Section ${section}` : ""} · {year}
    </span>
  );
}

function PerformanceBars({
  title,
  rows,
}: {
  title: string;
  rows: { id: string; label: string; average_percentage: number }[];
}) {
  return (
    <div className="student-performance-chart">
      <h3>{title}</h3>
      {rows.length ? (
        <ul>
          {rows.map((row) => (
            <li key={row.id}>
              <span>{row.label}</span>
              <div
                className="student-performance-track"
                role="progressbar"
                aria-label={`${row.label} average`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={row.average_percentage}
              >
                <span
                  style={{
                    width: `${Math.min(100, Math.max(0, row.average_percentage))}%`,
                  }}
                />
              </div>
              <b>{row.average_percentage}%</b>
            </li>
          ))}
        </ul>
      ) : (
        <p className="student-performance-empty">No completed quiz data yet.</p>
      )}
    </div>
  );
}

function PerformanceOverview({ analytics }: { analytics: QuizAnalytics }) {
  const subjectRows = analytics.subject_performance.map((subject) => ({
    id: subject.subject_id,
    label: subject.subject_name,
    average_percentage: subject.average_percentage,
  }));
  const chapterRows = analytics.chapter_performance.map((chapter) => ({
    id: chapter.chapter_id,
    label: `${chapter.subject_name} · ${chapter.chapter_title}`,
    average_percentage: chapter.average_percentage,
  }));
  const strongestAreas = [
    ...analytics.strongest_subjects.map((subject) => ({
      id: `subject-${subject.subject_id}`,
      label: subject.subject_name,
      average_percentage: subject.average_percentage,
    })),
    ...analytics.strongest_chapters.map((chapter) => ({
      id: `chapter-${chapter.chapter_id}`,
      label: `${chapter.subject_name} · ${chapter.chapter_title}`,
      average_percentage: chapter.average_percentage,
    })),
  ];
  const improvementAreas = [
    ...analytics.needs_improvement_subjects.map((subject) => ({
      id: `subject-${subject.subject_id}`,
      label: subject.subject_name,
      average_percentage: subject.average_percentage,
    })),
    ...analytics.needs_improvement_chapters.map((chapter) => ({
      id: `chapter-${chapter.chapter_id}`,
      label: `${chapter.subject_name} · ${chapter.chapter_title}`,
      average_percentage: chapter.average_percentage,
    })),
  ];

  return (
    <div className="student-performance">
      <div className="student-performance-metrics">
        <div>
          <span>
            <BarChart3 aria-hidden="true" size={16} /> Quizzes completed
          </span>
          <strong>{analytics.total_completed_quizzes}</strong>
        </div>
        <div>
          <span>
            <Target aria-hidden="true" size={16} /> Average score
          </span>
          <strong>{analytics.average_percentage}%</strong>
        </div>
        <div>
          <span>
            <Trophy aria-hidden="true" size={16} /> Highest score
          </span>
          <strong>{analytics.highest_percentage}%</strong>
        </div>
        <div>
          <span>Correct answers</span>
          <strong>
            {analytics.total_correct_answers}/{analytics.total_questions}
          </strong>
        </div>
      </div>
      {analytics.total_completed_quizzes ? (
        <>
          <div className="student-performance-charts">
            <PerformanceBars title="By subject" rows={subjectRows} />
            <PerformanceBars title="By chapter" rows={chapterRows} />
          </div>
          <div className="student-performance-highlights">
            <div>
              <h3>Strong areas · 80% and above</h3>
              {strongestAreas.length ? (
                strongestAreas.map((area) => (
                  <span key={area.id}>
                    {area.label} · {area.average_percentage}%
                  </span>
                ))
              ) : (
                <span>Keep practicing to build a strong area.</span>
              )}
            </div>
            <div>
              <h3>Needs practice · below 60%</h3>
              {improvementAreas.length ? (
                improvementAreas.map((area) => (
                  <span key={area.id}>
                    {area.label} · {area.average_percentage}%
                  </span>
                ))
              ) : (
                <span>No subjects need extra practice right now.</span>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="student-empty">
          <BarChart3 aria-hidden="true" size={24} />
          <strong>Your performance will appear here</strong>
          <span>Complete a quiz to start tracking your progress.</span>
        </div>
      )}
    </div>
  );
}

export function StudentDashboardPage() {
  const dashboard = useQuery({
    queryKey: ["student", "dashboard"],
    queryFn: studentService.dashboard,
  });
  const analytics = useQuery({
    queryKey: ["student", "quiz-analytics"],
    queryFn: studentService.quizAnalytics,
  });

  if (dashboard.isLoading)
    return <LoadingState label="Loading your dashboard…" />;
  if (dashboard.isError || !dashboard.data) {
    return (
      <QueryError
        message={dashboard.error?.message || "Could not load your dashboard."}
        onRetry={() => void dashboard.refetch()}
      />
    );
  }

  const { data } = dashboard;
  return (
    <div className="student-page">
      <section className="student-welcome">
        <div>
          <div className="student-eyebrow">Your learning space</div>
          <h1>Welcome back, {data.student_name.split(" ")[0]}</h1>
          <p>
            Pick up where you left off and explore what your class is learning.
          </p>
          <div className="student-class-line">
            <GraduationCap aria-hidden="true" size={17} />
            <EnrollmentLabel
              className={data.enrollment.class_name}
              grade={data.enrollment.grade_number}
              section={data.enrollment.section}
              year={data.enrollment.academic_year}
            />
          </div>
          <div className="student-school-line">{data.school_name}</div>
        </div>
        <span className="student-welcome-mark">
          <Sparkles aria-hidden="true" size={32} />
        </span>
      </section>

      <section className="student-metric-grid" aria-label="Learning overview">
        <div className="student-metric-card">
          <span className="student-metric-icon blue">
            <BookOpen aria-hidden="true" size={19} />
          </span>
          <span>My subjects</span>
          <strong>{data.subject_count}</strong>
        </div>
        <div className="student-metric-card">
          <span className="student-metric-icon violet">
            <BookText aria-hidden="true" size={19} />
          </span>
          <span>Available chapters</span>
          <strong>{data.chapter_count}</strong>
        </div>
      </section>

      <section className="student-section">
        <div className="student-section-heading">
          <div>
            <div className="student-eyebrow">Quiz performance</div>
            <h2>Your progress at a glance</h2>
          </div>
          <Link className="admin-text-link" to="/student/quiz/history">
            Quiz history <ArrowRight aria-hidden="true" size={15} />
          </Link>
        </div>
        {analytics.isLoading ? (
          <LoadingState label="Loading your performance…" />
        ) : analytics.isError || !analytics.data ? (
          <QueryError
            message={
              analytics.error?.message || "Could not load your performance."
            }
            onRetry={() => void analytics.refetch()}
          />
        ) : (
          <PerformanceOverview analytics={analytics.data} />
        )}
      </section>

      <section className="student-section">
        <div className="student-section-heading">
          <div>
            <div className="student-eyebrow">Your class</div>
            <h2>Explore your subjects</h2>
          </div>
          <Link className="admin-text-link" to="/student/subjects">
            All subjects <ArrowRight aria-hidden="true" size={15} />
          </Link>
        </div>
        <SubjectGrid
          subjects={data.subjects}
          classId={data.enrollment.class_id}
        />
      </section>

      <section className="student-section">
        <div className="student-section-heading">
          <div>
            <div className="student-eyebrow">Your progress</div>
            <h2>Recent activity</h2>
          </div>
          <span className="student-count-pill">
            {data.completed_quiz_count}{" "}
            {data.completed_quiz_count === 1
              ? "quiz completed"
              : "quizzes completed"}
          </span>
        </div>
        {data.recent_activity.length ? (
          <ul className="student-activity-list">
            {data.recent_activity.map((activity, index) => (
              <li key={`${activity.title}-${activity.completed_at}-${index}`}>
                <CheckCircle2 aria-hidden="true" size={19} />
                <span>
                  <strong>{activity.title}</strong>
                  <small>
                    {activity.subject_name} · {activity.chapter_title} ·{" "}
                    {new Date(activity.completed_at).toLocaleDateString()}
                  </small>
                </span>
                <b>
                  {activity.score}/{activity.total_questions} ·{" "}
                  {activity.percentage}%
                </b>
                <Link
                  className="admin-text-link"
                  to={`/student/quiz/history/${activity.attempt_id}`}
                >
                  Review <ArrowRight aria-hidden="true" size={15} />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="student-empty">
            <CheckCircle2 aria-hidden="true" size={24} />
            <strong>No completed quizzes yet</strong>
            <span>Your completed learning activities will appear here.</span>
          </div>
        )}
      </section>
    </div>
  );
}

export function StudentSubjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const enrollments = useQuery({
    queryKey: ["student", "enrollments"],
    queryFn: studentService.enrollments,
  });
  const selectedClassId =
    classId ??
    (enrollments.data?.length === 1
      ? enrollments.data[0].class_id
      : undefined);
  const subjects = useQuery({
    queryKey: ["student", "subjects", selectedClassId],
    queryFn: () => studentService.subjects(selectedClassId),
    enabled: Boolean(selectedClassId),
  });
  if (enrollments.isLoading) {
    return <LoadingState label="Loading your classes…" />;
  }
  if (enrollments.isError || !enrollments.data) {
    return (
      <QueryError
        message={enrollments.error?.message || "Could not load your classes."}
        onRetry={() => void enrollments.refetch()}
      />
    );
  }
  return (
    <div className="student-page">
      <PageHeading
        eyebrow="Your class"
        title="My subjects"
        description="Browse the subjects assigned to your current class."
      />
      {enrollments.data.length > 1 ? (
        <label className="student-class-selector">
          <span>Select your class and section</span>
          <select
            value={classId ?? ""}
            onChange={(event) => {
              const nextParams = new URLSearchParams(searchParams);
              if (event.target.value) {
                nextParams.set("class_id", event.target.value);
              } else {
                nextParams.delete("class_id");
              }
              setSearchParams(nextParams);
            }}
          >
            <option value="">Choose an active enrollment</option>
            {enrollments.data.map((enrollment) => (
              <option key={enrollment.class_id} value={enrollment.class_id}>
                {enrollment.class_name} · Grade {enrollment.grade_number}
                {enrollment.section ? `, Section ${enrollment.section}` : ""} ·{" "}
                {enrollment.academic_year}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {!selectedClassId ? (
        <div className="student-empty">
          <GraduationCap aria-hidden="true" size={24} />
          <strong>Select an active class</strong>
          <span>Choose an enrollment to view its subjects and chapters.</span>
        </div>
      ) : null}
      {selectedClassId && subjects.isLoading ? (
        <LoadingState label="Loading your subjects…" />
      ) : selectedClassId && subjects.isError ? (
        <QueryError
          message={subjects.error.message}
          onRetry={() => void subjects.refetch()}
        />
      ) : selectedClassId ? (
        <SubjectGrid subjects={subjects.data ?? []} classId={selectedClassId} />
      ) : null}
    </div>
  );
}

export function StudentSubjectDetailPage() {
  const { subjectId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const subject = useQuery({
    queryKey: ["student", "subjects", subjectId, classId],
    queryFn: () => studentService.subject(subjectId, classId),
    enabled: Boolean(subjectId),
  });

  if (subject.isLoading) return <LoadingState label="Loading subject…" />;
  if (subject.isError || !subject.data) {
    return (
      <QueryError
        message={subject.error?.message || "Could not load this subject."}
        onRetry={() => void subject.refetch()}
      />
    );
  }

  return (
    <div className="student-page">
      <Link
        className="student-back-link"
        to={`/student/subjects${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
      >
        <ArrowLeft aria-hidden="true" size={15} /> All subjects
      </Link>
      <PageHeading
        eyebrow={`Subject · ${subject.data.code}`}
        title={subject.data.name}
        description={
          subject.data.description || "Explore the chapters in this subject."
        }
      />
      <section className="student-content-panel">
        <div className="student-section-heading">
          <div>
            <div className="student-eyebrow">Course outline</div>
            <h2>Chapters</h2>
          </div>
          <span className="student-count-pill">
            {subject.data.chapters.length} total
          </span>
        </div>
        {subject.data.chapters.length === 0 ? (
          <div className="student-empty">
            <Layers3 aria-hidden="true" size={24} />
            <strong>No chapters have been added yet</strong>
            <span>Check back later for new material.</span>
          </div>
        ) : (
          <ol className="student-chapter-list">
            {subject.data.chapters.map((chapter) => (
              <li key={chapter.id}>
                <Link
                  className="student-chapter-link"
                  to={`/student/chapters/${chapter.id}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
                >
                  <span className="student-chapter-number">
                    {String(chapter.chapter_number).padStart(2, "0")}
                  </span>
                  <span className="student-chapter-copy">
                    <strong>{chapter.title}</strong>
                    <small>
                      {chapter.description || "Open chapter details"} ·{" "}
                      {chapter.has_available_quiz
                        ? "Quiz available"
                        : "No quiz available"}
                    </small>
                  </span>
                  <ArrowRight aria-hidden="true" size={17} />
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export function StudentChapterDetailPage() {
  const { chapterId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const chapter = useQuery({
    queryKey: ["student", "chapters", chapterId, classId],
    queryFn: () => studentService.chapter(chapterId, classId),
    enabled: Boolean(chapterId),
  });

  if (chapter.isLoading) return <LoadingState label="Loading chapter…" />;
  if (chapter.isError || !chapter.data) {
    return (
      <QueryError
        message={chapter.error?.message || "Could not load this chapter."}
        onRetry={() => void chapter.refetch()}
      />
    );
  }

  return (
    <div className="student-page">
      <Link
        className="student-back-link"
        to={`/student/subjects/${chapter.data.subject_id}${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
      >
        <ArrowLeft aria-hidden="true" size={15} /> {chapter.data.subject_name}
      </Link>
      <section className="student-chapter-hero">
        <span className="student-chapter-number large">
          {String(chapter.data.chapter_number).padStart(2, "0")}
        </span>
        <div>
          <div className="student-eyebrow">{chapter.data.subject_name}</div>
          <h1>{chapter.data.title}</h1>
          <p>
            {chapter.data.class_name} · Chapter {chapter.data.chapter_number}
          </p>
        </div>
      </section>
      <section className="student-content-panel student-chapter-content">
        <div className="student-eyebrow">Chapter overview</div>
        {chapter.data.description ? (
          <p>{chapter.data.description}</p>
        ) : (
          <p>More learning material for this chapter will be available here.</p>
        )}
      </section>
      <section className="student-quiz-status">
        <div>
          <div className="student-eyebrow">Chapter quiz</div>
          <strong>
            {chapter.data.has_available_quiz
              ? "A quiz is available for this chapter"
              : "No quiz is available for this chapter yet"}
          </strong>
          <span>
            {chapter.data.has_available_quiz
              ? "Answer 15 questions in a timed quiz with immediate feedback."
              : "Check back later for a chapter quiz."}
          </span>
        </div>
        {chapter.data.has_available_quiz ? (
          <Link
            className="admin-button primary"
            to={`/student/chapters/${chapter.data.id}/quiz${classId ? `?class_id=${encodeURIComponent(classId)}` : ""}`}
          >
            Start Quiz <ArrowRight aria-hidden="true" size={15} />
          </Link>
        ) : (
          <button className="admin-button primary" disabled>
            Start Quiz
          </button>
        )}
      </section>
    </div>
  );
}

export function StudentLearningPlaceholderPage() {
  return (
    <div className="student-page">
      <PageHeading
        eyebrow="Learning hub"
        title="More ways to learn"
        description="A space for additional learning resources, coming soon."
      />
      <section className="student-placeholder">
        <span className="student-placeholder-icon">
          <Sparkles aria-hidden="true" size={25} />
        </span>
        <h2>Your learning hub is taking shape</h2>
        <p>
          New resources will appear here when they are ready. For now, explore
          your class subjects and chapters.
        </p>
        <Link className="admin-button primary" to="/student/subjects">
          Browse subjects <ArrowRight aria-hidden="true" size={15} />
        </Link>
      </section>
    </div>
  );
}

export function StudentProfilePage() {
  const profile = useQuery({
    queryKey: ["student", "profile"],
    queryFn: studentService.profile,
  });
  if (profile.isLoading) return <LoadingState label="Loading your profile…" />;
  if (profile.isError || !profile.data) {
    return (
      <QueryError
        message={profile.error?.message || "Could not load your profile."}
        onRetry={() => void profile.refetch()}
      />
    );
  }

  const { data } = profile;
  return (
    <div className="student-page">
      <PageHeading
        eyebrow="Account"
        title="My profile"
        description="Your student account and current class information."
      />
      <section className="student-profile-card">
        <div className="student-profile-header">
          <span className="student-profile-avatar">
            <UserRound aria-hidden="true" size={27} />
          </span>
          <div>
            <h2>{data.full_name}</h2>
            <span>{data.school_name}</span>
          </div>
        </div>
        <dl className="student-profile-details">
          <div>
            <dt>Student ID</dt>
            <dd>{data.identifier || "Not provided"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{data.email || "Not provided"}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{data.phone || "Not provided"}</dd>
          </div>
          <div>
            <dt>Current class</dt>
            <dd>
              <EnrollmentLabel
                className={data.enrollment.class_name}
                grade={data.enrollment.grade_number}
                section={data.enrollment.section}
                year={data.enrollment.academic_year}
              />
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

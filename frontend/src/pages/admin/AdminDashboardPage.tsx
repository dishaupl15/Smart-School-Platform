import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  GraduationCap,
  Layers3,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { adminService } from "@/services/admin-service";
import type { Person } from "@/types/admin";

const cards = [
  {
    key: "active_students",
    label: "Active students",
    icon: Users,
    link: "/admin/students",
  },
  {
    key: "active_teachers",
    label: "Active teachers",
    icon: GraduationCap,
    link: "/admin/teachers",
  },
  {
    key: "classes",
    label: "Classes & sections",
    icon: Layers3,
    link: "/admin/classes",
  },
  {
    key: "subjects",
    label: "Subjects",
    icon: BookOpen,
    link: "/admin/subjects",
  },
  {
    key: "chapters",
    label: "Chapters",
    icon: BookOpen,
    link: "/admin/chapters",
  },
] as const;

function RecentPeople({ title, people }: { title: string; people: Person[] }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-heading">
        <h2>{title}</h2>
      </div>
      {people.length === 0 ? (
        <p className="admin-empty">No records yet.</p>
      ) : (
        <ul className="admin-recent-list">
          {people.map((person) => (
            <li key={person.id}>
              <span className="admin-avatar">
                {person.full_name.slice(0, 1).toUpperCase()}
              </span>
              <span>
                <strong>{person.full_name}</strong>
                <small>{person.identifier}</small>
              </span>
              <span
                className={`admin-status ${person.is_active ? "active" : ""}`}
              >
                {person.is_active ? "Active" : "Inactive"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function AdminDashboardPage() {
  const stats = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: adminService.dashboard,
  });

  if (stats.isLoading) {
    return (
      <div className="admin-loading" role="status">
        Loading school overview…
      </div>
    );
  }
  if (stats.isError || !stats.data) {
    return (
      <div className="admin-error" role="alert">
        Could not load the dashboard.{" "}
        {stats.error instanceof Error ? stats.error.message : "Try again."}
        <button
          className="admin-button secondary"
          onClick={() => void stats.refetch()}
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">School administration</div>
          <h1>Dashboard</h1>
          <p>Current records and enrollment activity for your school.</p>
        </div>
      </div>
      <section className="admin-stat-grid" aria-label="School statistics">
        {cards.map(({ key, label, icon: Icon, link }) => (
          <Link className="admin-stat-card" to={link} key={key}>
            <span className="admin-stat-icon">
              <Icon size={19} aria-hidden="true" />
            </span>
            <span className="admin-stat-label">{label}</span>
            <strong>{stats.data[key].toLocaleString()}</strong>
            <ArrowUpRight
              className="admin-stat-arrow"
              size={17}
              aria-hidden="true"
            />
          </Link>
        ))}
      </section>

      <div className="admin-dashboard-grid">
        <section className="admin-panel enrollment-overview">
          <div className="admin-panel-heading">
            <div>
              <h2>Enrollment overview</h2>
              <p>Student placements recorded for academic years.</p>
            </div>
            <Link className="admin-text-link" to="/admin/enrollments">
              Manage <ArrowUpRight size={15} />
            </Link>
          </div>
          <div className="enrollment-metrics">
            <div>
              <strong>{stats.data.active_enrollments.toLocaleString()}</strong>
              <span>Active enrollments</span>
            </div>
            <div>
              <strong>
                {stats.data.unenrolled_active_students.toLocaleString()}
              </strong>
              <span>Active students without an active enrollment</span>
            </div>
          </div>
          {stats.data.active_students === 0 && (
            <p className="admin-empty">
              Create student records to start managing enrollment.
            </p>
          )}
        </section>
        <div className="admin-quick-actions">
          <h2>Quick actions</h2>
          <Link to="/admin/students?create=1">
            <span className="quick-action-mark">+</span>
            <span>
              <strong>Add a student</strong>
              <small>Provision an account and class enrollment</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/admin/teachers?create=1">
            <span className="quick-action-mark">+</span>
            <span>
              <strong>Add a teacher</strong>
              <small>Create a school-managed teacher account</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/admin/classes">
            <span className="quick-action-mark">+</span>
            <span>
              <strong>Create a class</strong>
              <small>Set a grade, section, and academic year</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/admin/subjects">
            <span className="quick-action-mark">+</span>
            <span>
              <strong>Create a subject</strong>
              <small>Build the school subject catalogue</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/admin/question-bank">
            <span className="quick-action-mark">+</span>
            <span>
              <strong>Manage question bank</strong>
              <small>Create, review, and import multilingual questions</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
        </div>
      </div>

      <div className="admin-dashboard-grid recent-grid">
        <RecentPeople
          title="Recently added students"
          people={stats.data.recent_students}
        />
        <RecentPeople
          title="Recently added teachers"
          people={stats.data.recent_teachers}
        />
      </div>
    </div>
  );
}

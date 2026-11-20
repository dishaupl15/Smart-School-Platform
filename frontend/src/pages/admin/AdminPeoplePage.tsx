import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { adminService } from "@/services/admin-service";
import type { Page, Student, StudentDetail, Teacher } from "@/types/admin";

type PersonKind = "students" | "teachers";

const studentFormSchema = z.object({
  full_name: z.string().trim().min(1, "Enter a full name.").max(200),
  student_identifier: z
    .string()
    .trim()
    .min(1, "Enter a student identifier.")
    .max(100),
  email: z.union([
    z.literal(""),
    z.string().email("Enter a valid email address."),
  ]),
  phone: z.string().max(30),
  class_id: z.string().min(1, "Select a class."),
});

const teacherFormSchema = z.object({
  full_name: z.string().trim().min(1, "Enter a full name.").max(200),
  teacher_identifier: z
    .string()
    .trim()
    .min(1, "Enter a teacher identifier.")
    .max(100),
  email: z.string().trim().email("Enter a valid email address."),
  phone: z.string().max(30),
});

type StudentForm = z.infer<typeof studentFormSchema>;
type TeacherForm = z.infer<typeof teacherFormSchema>;

function PageControls({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="admin-pagination">
      <span>
        Page {page} of {Math.max(pages, 1)}
      </span>
      <div>
        <button
          className="admin-button secondary"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <button
          className="admin-button secondary"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

function ProvisionedCredential({ password }: { password: string }) {
  return (
    <div className="admin-credential" role="status">
      <strong>Account created. Copy this temporary password now.</strong>
      <code>{password}</code>
      <small>
        This value is shown only once and is not stored in plaintext.
      </small>
    </div>
  );
}

function StudentCreateForm({
  onCreated,
}: {
  onCreated: (password: string) => void;
}) {
  const classes = useQuery({
    queryKey: ["admin", "classes", "active", 100],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const form = useForm<StudentForm>({
    resolver: zodResolver(studentFormSchema),
    defaultValues: {
      full_name: "",
      student_identifier: "",
      email: "",
      phone: "",
      class_id: "",
    },
  });
  const create = useMutation({
    mutationFn: adminService.createStudent,
    onSuccess: (person) => {
      onCreated(person.temporary_password);
      form.reset();
    },
  });

  const submit = form.handleSubmit((values) => {
    create.mutate({
      full_name: values.full_name,
      student_identifier: values.student_identifier,
      ...(values.email ? { email: values.email } : {}),
      ...(values.phone ? { phone: values.phone } : {}),
      class_id: values.class_id,
    });
  });

  return (
    <form className="admin-form-grid" onSubmit={(event) => void submit(event)}>
      <label>
        Full name
        <input {...form.register("full_name")} autoComplete="name" />
        {form.formState.errors.full_name && (
          <small className="field-error">
            {form.formState.errors.full_name.message}
          </small>
        )}
      </label>
      <label>
        Student identifier
        <input {...form.register("student_identifier")} autoComplete="off" />
        {form.formState.errors.student_identifier && (
          <small className="field-error">
            {form.formState.errors.student_identifier.message}
          </small>
        )}
      </label>
      <label>
        Email <span className="label-optional">(optional)</span>
        <input type="email" {...form.register("email")} autoComplete="email" />
        {form.formState.errors.email && (
          <small className="field-error">
            {form.formState.errors.email.message}
          </small>
        )}
      </label>
      <label>
        Phone <span className="label-optional">(optional)</span>
        <input {...form.register("phone")} autoComplete="tel" />
      </label>
      <label>
        Initial class
        <select {...form.register("class_id")} defaultValue="">
          <option value="">Select a class</option>
          {classes.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.academic_year}
            </option>
          ))}
        </select>
        {form.formState.errors.class_id && (
          <small className="field-error">
            {form.formState.errors.class_id.message}
          </small>
        )}
      </label>
      {classes.isError && (
        <p className="admin-error" role="alert">
          Could not load active classes.
        </p>
      )}
      {create.isError && (
        <p className="admin-error" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="admin-form-actions">
        <button
          className="admin-button primary"
          disabled={create.isPending || classes.isLoading}
        >
          {create.isPending ? "Creating…" : "Create student"}
        </button>
      </div>
    </form>
  );
}

function TeacherCreateForm({
  onCreated,
}: {
  onCreated: (password: string) => void;
}) {
  const form = useForm<TeacherForm>({
    resolver: zodResolver(teacherFormSchema),
    defaultValues: {
      full_name: "",
      teacher_identifier: "",
      email: "",
      phone: "",
    },
  });
  const create = useMutation({
    mutationFn: adminService.createTeacher,
    onSuccess: (person) => {
      onCreated(person.temporary_password);
      form.reset();
    },
  });
  const submit = form.handleSubmit((values) => {
    create.mutate({
      full_name: values.full_name,
      teacher_identifier: values.teacher_identifier,
      email: values.email,
      ...(values.phone ? { phone: values.phone } : {}),
    });
  });

  return (
    <form className="admin-form-grid" onSubmit={(event) => void submit(event)}>
      <label>
        Full name
        <input {...form.register("full_name")} autoComplete="name" />
        {form.formState.errors.full_name && (
          <small className="field-error">
            {form.formState.errors.full_name.message}
          </small>
        )}
      </label>
      <label>
        Teacher identifier
        <input {...form.register("teacher_identifier")} autoComplete="off" />
        {form.formState.errors.teacher_identifier && (
          <small className="field-error">
            {form.formState.errors.teacher_identifier.message}
          </small>
        )}
      </label>
      <label>
        Email
        <input type="email" {...form.register("email")} autoComplete="email" />
        {form.formState.errors.email && (
          <small className="field-error">
            {form.formState.errors.email.message}
          </small>
        )}
      </label>
      <label>
        Phone <span className="label-optional">(optional)</span>
        <input {...form.register("phone")} autoComplete="tel" />
      </label>
      {create.isError && (
        <p className="admin-error" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="admin-form-actions">
        <button className="admin-button primary" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create teacher"}
        </button>
      </div>
    </form>
  );
}

export function AdminPeoplePage({ kind }: { kind: PersonKind }) {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [enrollmentFilter, setEnrollmentFilter] = useState("");
  const [creating, setCreating] = useState(searchParams.get("create") === "1");
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const isStudent = kind === "students";
  const title = isStudent ? "Students" : "Teachers";
  const classes = useQuery({
    queryKey: ["admin", "classes", "filters"],
    queryFn: () => adminService.classes({ page_size: 100 }),
  });
  const subjects = useQuery({
    queryKey: ["admin", "subjects", "filters"],
    queryFn: () => adminService.subjects({ page_size: 100 }),
    enabled: !isStudent,
  });
  const query = {
    search: search.trim() || undefined,
    class_id: classId || undefined,
    subject_id: !isStudent ? subjectId || undefined : undefined,
    is_active: activeFilter ? activeFilter === "active" : undefined,
    enrollment_status: isStudent ? enrollmentFilter || undefined : undefined,
    page,
    page_size: 20,
  };
  const people = useQuery<Page<Student> | Page<Teacher>>({
    queryKey: ["admin", kind, query],
    queryFn: async () =>
      isStudent ? adminService.students(query) : adminService.teachers(query),
  });
  const updateStatus = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      isStudent
        ? adminService.studentStatus(id, active)
        : adminService.teacherStatus(id, active),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["admin", kind] }),
  });

  const toggleCreate = () => {
    const next = !creating;
    setCreating(next);
    setTemporaryPassword("");
    if (next) setSearchParams({ create: "1" });
    else setSearchParams({});
  };

  const items = (people.data?.items ?? []) as (Student | Teacher)[];
  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">People management</div>
          <h1>{title}</h1>
          <p>Manage school accounts, status, and academic placement.</p>
        </div>
        <button className="admin-button primary" onClick={toggleCreate}>
          {creating ? "Close form" : `Add ${isStudent ? "student" : "teacher"}`}
        </button>
      </div>
      {temporaryPassword && (
        <ProvisionedCredential password={temporaryPassword} />
      )}
      {creating && (
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Create {isStudent ? "student" : "teacher"}</h2>
            <p>A one-time temporary password will be shown after creation.</p>
          </div>
          {isStudent ? (
            <StudentCreateForm
              onCreated={(password) => {
                setTemporaryPassword(password);
                setCreating(false);
                setSearchParams({});
                void queryClient.invalidateQueries({
                  queryKey: ["admin", "students"],
                });
              }}
            />
          ) : (
            <TeacherCreateForm
              onCreated={(password) => {
                setTemporaryPassword(password);
                setCreating(false);
                setSearchParams({});
                void queryClient.invalidateQueries({
                  queryKey: ["admin", "teachers"],
                });
              }}
            />
          )}
        </section>
      )}
      <section className="admin-panel">
        <div className="admin-toolbar">
          <label className="admin-search">
            Search
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Name or identifier"
            />
          </label>
          <label>
            Class
            <select
              value={classId}
              onChange={(event) => {
                setClassId(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All classes</option>
              {classes.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {!isStudent && (
            <label>
              Subject
              <select
                value={subjectId}
                onChange={(event) => {
                  setSubjectId(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All subjects</option>
                {subjects.data?.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Account
            <select
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
          {isStudent && (
            <label>
              Enrollment
              <select
                value={enrollmentFilter}
                onChange={(event) => {
                  setEnrollmentFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All enrollment</option>
                <option value="active">Enrolled</option>
                <option value="inactive">Not currently enrolled</option>
              </select>
            </label>
          )}
        </div>
        {people.isLoading ? (
          <div className="admin-loading" role="status">
            Loading {title.toLowerCase()}…
          </div>
        ) : people.isError ? (
          <div className="admin-error" role="alert">
            {people.error.message}
          </div>
        ) : items.length === 0 ? (
          <p className="admin-empty">
            No {title.toLowerCase()} match these filters.
          </p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>
                    {isStudent ? "Student identifier" : "Teacher identifier"}
                  </th>
                  <th>{isStudent ? "Current class" : "Classes & subjects"}</th>
                  <th>Status</th>
                  <th>Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((person) => {
                  const placement = isStudent
                    ? (() => {
                        const enrollment = (person as Student).enrollment;
                        return enrollment
                          ? `${enrollment.class_name} · ${enrollment.academic_year}`
                          : "—";
                      })()
                    : (person as Teacher).assignments
                        .filter((item) => item.is_active)
                        .map(
                          (item) => `${item.class_name} · ${item.subject_name}`,
                        )
                        .join(", ") || "—";
                  return (
                    <tr key={person.id}>
                      <td>
                        <Link
                          className="admin-text-link"
                          to={`/admin/${kind}/${person.id}`}
                        >
                          {person.full_name}
                        </Link>
                        <small className="table-subtext">
                          {person.email ?? "No email"}
                        </small>
                      </td>
                      <td>{person.identifier}</td>
                      <td>{placement}</td>
                      <td>
                        <span
                          className={`admin-status ${person.is_active ? "active" : ""}`}
                        >
                          {person.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        {new Date(person.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <button
                          className="admin-button subtle"
                          disabled={updateStatus.isPending}
                          onClick={() => {
                            const next = !person.is_active;
                            if (
                              window.confirm(
                                `${next ? "Activate" : "Deactivate"} ${person.full_name}?`,
                              )
                            )
                              updateStatus.mutate({
                                id: person.id,
                                active: next,
                              });
                          }}
                        >
                          {person.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {people.isError && updateStatus.isError && (
          <p className="admin-error" role="alert">
            {updateStatus.error.message}
          </p>
        )}
        {people.data && (
          <PageControls
            page={page}
            pages={people.data.pages}
            onChange={setPage}
          />
        )}
      </section>
      {updateStatus.isError && (
        <p className="admin-error" role="alert">
          {updateStatus.error.message}
        </p>
      )}
    </div>
  );
}

export function AdminPersonDetailPage({ kind }: { kind: PersonKind }) {
  const { id = "" } = useParams();
  return <PersonDetailContent kind={kind} id={id} />;
}

function PersonDetailContent({ kind, id }: { kind: PersonKind; id: string }) {
  const queryClient = useQueryClient();
  const person = useQuery<StudentDetail | Teacher>({
    queryKey: ["admin", kind, id],
    queryFn: async () =>
      kind === "students" ? adminService.student(id) : adminService.teacher(id),
    enabled: Boolean(id),
  });
  const update = useMutation({
    mutationFn: async (values: Record<string, unknown>) =>
      kind === "students"
        ? adminService.updateStudent(id, values)
        : adminService.updateTeacher(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", kind] });
      void queryClient.invalidateQueries({ queryKey: ["admin", kind, id] });
    },
  });
  const data = person.data;
  if (person.isLoading)
    return (
      <div className="admin-loading" role="status">
        Loading profile…
      </div>
    );
  if (person.isError || !data)
    return (
      <div className="admin-error" role="alert">
        {person.error?.message ?? "Profile not found."}
      </div>
    );
  const student = kind === "students" ? (data as StudentDetail) : null;
  const teacher = kind === "teachers" ? (data as Teacher) : null;

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">
            {kind === "students" ? "Student profile" : "Teacher profile"}
          </div>
          <h1>{data.full_name}</h1>
          <p>
            {data.identifier} ·{" "}
            {data.is_active ? "Active account" : "Inactive account"}
          </p>
        </div>
        <Link className="admin-button secondary" to={`/admin/${kind}`}>
          Back to {kind}
        </Link>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Profile information</h2>
        </div>
        <form
          className="admin-form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            update.mutate({
              full_name: String(form.get("full_name")),
              [kind === "students"
                ? "student_identifier"
                : "teacher_identifier"]: String(form.get("identifier")),
              email: String(form.get("email")) || null,
              phone: String(form.get("phone")) || null,
            });
          }}
        >
          <label>
            Full name
            <input
              name="full_name"
              defaultValue={data.full_name}
              required
              maxLength={200}
            />
          </label>
          <label>
            {kind === "students" ? "Student" : "Teacher"} identifier
            <input
              name="identifier"
              defaultValue={data.identifier}
              required
              maxLength={100}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              name="email"
              defaultValue={data.email ?? ""}
              required={kind === "teachers"}
            />
          </label>
          <label>
            Phone
            <input name="phone" defaultValue={data.phone ?? ""} />
          </label>
          {update.isError && (
            <p className="admin-error" role="alert">
              {update.error.message}
            </p>
          )}
          {update.isSuccess && (
            <p className="admin-success" role="status">
              Profile updated.
            </p>
          )}
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={update.isPending}
            >
              {update.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </section>
      {student && (
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Enrollment history</h2>
            <Link className="admin-text-link" to="/admin/enrollments">
              Manage enrollments
            </Link>
          </div>
          {student.enrollments.length === 0 ? (
            <p className="admin-empty">No enrollment history.</p>
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Class</th>
                    <th>Academic year</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {student.enrollments.map((entry) => (
                    <tr key={entry.id}>
                      <td>
                        {entry.class_name} · Grade {entry.grade_number}
                        {entry.section ? ` / ${entry.section}` : ""}
                      </td>
                      <td>{entry.academic_year}</td>
                      <td>{entry.is_active ? "Active" : "Historical"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {teacher && (
        <section className="admin-panel">
          <div className="admin-panel-heading">
            <h2>Class & subject assignments</h2>
            <Link className="admin-text-link" to="/admin/assignments">
              Manage assignments
            </Link>
          </div>
          {teacher.assignments.length === 0 ? (
            <p className="admin-empty">No teacher assignments.</p>
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Class</th>
                    <th>Subject</th>
                    <th>Academic year</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {teacher.assignments.map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.class_name}</td>
                      <td>{entry.subject_name}</td>
                      <td>{entry.academic_year}</td>
                      <td>{entry.is_active ? "Active" : "Inactive"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { adminService } from "@/services/admin-service";
import type { Enrollment, TeacherAssignment } from "@/types/admin";

function refreshAdmin(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ["admin"] });
}

function Notice({
  children,
  error = false,
}: {
  children: string;
  error?: boolean;
}) {
  return (
    <p
      className={error ? "admin-error" : "admin-success"}
      role={error ? "alert" : "status"}
    >
      {children}
    </p>
  );
}

export function AdminEnrollmentsPage() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [transferTargets, setTransferTargets] = useState<
    Record<string, string>
  >({});
  const students = useQuery({
    queryKey: ["admin", "students", "active"],
    queryFn: () => adminService.students({ is_active: true, page_size: 100 }),
  });
  const classes = useQuery({
    queryKey: ["admin", "classes", "active"],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const enrollments = useQuery({
    queryKey: ["admin", "enrollments"],
    queryFn: () => adminService.enrollments({ page_size: 100 }),
  });
  const create = useMutation({
    mutationFn: adminService.createEnrollment,
    onSuccess: () => {
      setMessage("Enrollment created.");
      refreshAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const transfer = useMutation({
    mutationFn: ({ id, target }: { id: string; target: string }) =>
      adminService.transferEnrollment(id, target),
    onSuccess: () => {
      setMessage(
        "Student transferred. Previous enrollment history was retained.",
      );
      refreshAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      student_id: String(form.get("student_id")),
      class_id: String(form.get("class_id")),
      academic_year: String(form.get("academic_year")),
    });
  };
  const activeClasses = classes.data?.items ?? [];

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Student placement</div>
          <h1>Enrollments</h1>
          <p>
            Enroll students, transfer between sections, and preserve each
            academic record.
          </p>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Enroll student</h2>
          <p>
            The selected class determines the academic year; enrollments cannot
            be overwritten.
          </p>
        </div>
        <form className="admin-form-grid compact" onSubmit={submit}>
          <label>
            Student
            <select name="student_id" required defaultValue="">
              <option value="">Select student</option>
              {students.data?.items.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.full_name} · {student.identifier}
                </option>
              ))}
            </select>
          </label>
          <label>
            Class
            <select
              name="class_id"
              required
              defaultValue=""
              onChange={(event) => {
                const form = event.currentTarget.form;
                const year = activeClasses.find(
                  (item) => item.id === event.target.value,
                )?.academic_year;
                const input = form?.elements.namedItem("academic_year");
                if (input instanceof HTMLInputElement && year)
                  input.value = year;
              }}
            >
              <option value="">Select class</option>
              {activeClasses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.academic_year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Academic year
            <input
              name="academic_year"
              required
              pattern="20[0-9]{2}[-/]([0-9]{2})"
              placeholder="Choose a class first"
            />
          </label>
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Enrolling…" : "Create enrollment"}
            </button>
          </div>
        </form>
        {message && (
          <Notice error={create.isError || transfer.isError}>{message}</Notice>
        )}
      </section>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Enrollment records</h2>
          <p>
            Use transfer to close the current placement and create a new one in
            the same year.
          </p>
        </div>
        {enrollments.isLoading ? (
          <div className="admin-loading" role="status">
            Loading enrollment records…
          </div>
        ) : enrollments.isError ? (
          <Notice error>{enrollments.error.message}</Notice>
        ) : enrollments.data?.items.length === 0 ? (
          <p className="admin-empty">No enrollment records yet.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Class</th>
                  <th>Academic year</th>
                  <th>Status</th>
                  <th>Transfer</th>
                </tr>
              </thead>
              <tbody>
                {enrollments.data?.items.map((item: Enrollment) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        className="admin-text-link"
                        to={`/admin/students/${item.student_id}`}
                      >
                        {item.student_name}
                      </Link>
                      <small className="table-subtext">
                        {item.student_identifier}
                      </small>
                    </td>
                    <td>
                      {item.class_name}
                      {item.section ? ` · ${item.section}` : ""}
                    </td>
                    <td>{item.academic_year}</td>
                    <td>{item.is_active ? "Current" : "Historical"}</td>
                    <td>
                      {item.is_active ? (
                        <div className="inline-assignment">
                          <select
                            aria-label={`Transfer ${item.student_name}`}
                            value={transferTargets[item.id] ?? ""}
                            onChange={(event) =>
                              setTransferTargets((current) => ({
                                ...current,
                                [item.id]: event.target.value,
                              }))
                            }
                          >
                            <option value="">Choose target class</option>
                            {activeClasses
                              .filter(
                                (academicClass) =>
                                  academicClass.academic_year ===
                                    item.academic_year &&
                                  academicClass.id !== item.class_id,
                              )
                              .map((academicClass) => (
                                <option
                                  key={academicClass.id}
                                  value={academicClass.id}
                                >
                                  {academicClass.name}
                                </option>
                              ))}
                          </select>
                          <button
                            className="admin-button subtle"
                            disabled={
                              !transferTargets[item.id] || transfer.isPending
                            }
                            onClick={() =>
                              window.confirm(
                                `Transfer ${item.student_name} to the selected class?`,
                              ) &&
                              transfer.mutate({
                                id: item.id,
                                target: transferTargets[item.id],
                              })
                            }
                          >
                            Transfer
                          </button>
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export function AdminAssignmentsPage() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [classId, setClassId] = useState("");
  const classes = useQuery({
    queryKey: ["admin", "classes", "active"],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const teachers = useQuery({
    queryKey: ["admin", "teachers", "active"],
    queryFn: () => adminService.teachers({ is_active: true, page_size: 100 }),
  });
  const assignments = useQuery({
    queryKey: ["admin", "assignments"],
    queryFn: () => adminService.assignments({ page_size: 100 }),
  });
  const subjects = useMemo(
    () =>
      classes.data?.items
        .find((item) => item.id === classId)
        ?.subjects.filter((item) => item.is_active) ?? [],
    [classes.data, classId],
  );
  const create = useMutation({
    mutationFn: adminService.createAssignment,
    onSuccess: () => {
      setMessage("Teacher assigned.");
      refreshAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const deactivate = useMutation({
    mutationFn: adminService.deactivateAssignment,
    onSuccess: () => {
      setMessage("Assignment deactivated.");
      refreshAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const reactivate = useMutation({
    mutationFn: (id: string) =>
      adminService.updateAssignment(id, { is_active: true }),
    onSuccess: () => {
      setMessage("Assignment reactivated.");
      refreshAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      teacher_id: String(form.get("teacher_id")),
      class_id: String(form.get("class_id")),
      subject_id: String(form.get("subject_id")),
      academic_year: String(form.get("academic_year")),
    });
  };
  const activeClasses = classes.data?.items ?? [];

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Teaching schedule</div>
          <h1>Teacher assignments</h1>
          <p>
            Assign active teachers to a subject in a class and academic year.
          </p>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Assign a teacher</h2>
          <p>Only subjects assigned to the chosen class are available.</p>
        </div>
        <form className="admin-form-grid compact" onSubmit={submit}>
          <label>
            Teacher
            <select name="teacher_id" required defaultValue="">
              <option value="">Select teacher</option>
              {teachers.data?.items.map((teacher) => (
                <option key={teacher.id} value={teacher.id}>
                  {teacher.full_name} · {teacher.identifier}
                </option>
              ))}
            </select>
          </label>
          <label>
            Class
            <select
              name="class_id"
              required
              value={classId}
              onChange={(event) => {
                setClassId(event.target.value);
                const year = activeClasses.find(
                  (item) => item.id === event.target.value,
                )?.academic_year;
                const field =
                  event.currentTarget.form?.elements.namedItem("academic_year");
                if (field instanceof HTMLInputElement && year)
                  field.value = year;
              }}
            >
              <option value="">Select class</option>
              {activeClasses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.academic_year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject
            <select name="subject_id" required defaultValue="">
              <option value="">Select subject</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Academic year
            <input
              name="academic_year"
              required
              pattern="20[0-9]{2}[-/]([0-9]{2})"
              placeholder="Choose a class first"
            />
          </label>
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Assigning…" : "Assign teacher"}
            </button>
          </div>
        </form>
        {message && (
          <Notice
            error={create.isError || deactivate.isError || reactivate.isError}
          >
            {message}
          </Notice>
        )}
      </section>
      <section className="admin-panel">
        {assignments.isLoading ? (
          <div className="admin-loading" role="status">
            Loading assignments…
          </div>
        ) : assignments.isError ? (
          <Notice error>{assignments.error.message}</Notice>
        ) : assignments.data?.items.length === 0 ? (
          <p className="admin-empty">No teacher assignments yet.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Teacher</th>
                  <th>Class</th>
                  <th>Subject</th>
                  <th>Academic year</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {assignments.data?.items.map(
                  (assignment: TeacherAssignment) => (
                    <tr key={assignment.id}>
                      <td>
                        <Link
                          className="admin-text-link"
                          to={`/admin/teachers/${assignment.teacher_id}`}
                        >
                          {assignment.teacher_name}
                        </Link>
                        <small className="table-subtext">
                          {assignment.teacher_identifier}
                        </small>
                      </td>
                      <td>{assignment.class_name}</td>
                      <td>{assignment.subject_name}</td>
                      <td>{assignment.academic_year}</td>
                      <td>{assignment.is_active ? "Active" : "Historical"}</td>
                      <td>
                        {assignment.is_active ? (
                          <button
                            className="admin-button subtle"
                            onClick={() =>
                              window.confirm("Deactivate this assignment?") &&
                              deactivate.mutate(assignment.id)
                            }
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            className="admin-button subtle"
                            onClick={() => reactivate.mutate(assignment.id)}
                          >
                            Reactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

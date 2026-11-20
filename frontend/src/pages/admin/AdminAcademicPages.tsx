import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { adminService } from "@/services/admin-service";
import type { AcademicClass, Chapter, Subject } from "@/types/admin";

function invalidateAdmin(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ["admin"] });
}

function ErrorState({ message }: { message: string }) {
  return (
    <p className="admin-error" role="alert">
      {message}
    </p>
  );
}

export function AdminClassesPage() {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState("");
  const [academicYear, setAcademicYear] = useState("");
  const classes = useQuery({
    queryKey: ["admin", "classes", academicYear],
    queryFn: () =>
      adminService.classes({
        academic_year: academicYear || undefined,
        page_size: 100,
      }),
  });
  const subjects = useQuery({
    queryKey: ["admin", "subjects", "active"],
    queryFn: () => adminService.subjects({ is_active: true, page_size: 100 }),
  });
  const create = useMutation({
    mutationFn: adminService.createClass,
    onSuccess: () => {
      setFormError("");
      invalidateAdmin(queryClient);
    },
    onError: (error) => setFormError(error.message),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminService.classStatus(id, active),
    onSuccess: () => invalidateAdmin(queryClient),
  });
  const updateClass = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: Record<string, unknown>;
    }) => adminService.updateClass(id, values),
    onSuccess: () => {
      setFormError("");
      invalidateAdmin(queryClient);
    },
    onError: (error) => setFormError(error.message),
  });
  const assignSubject = useMutation({
    mutationFn: ({
      classId,
      subjectId,
    }: {
      classId: string;
      subjectId: string;
    }) => adminService.assignSubject(classId, subjectId),
    onSuccess: () => invalidateAdmin(queryClient),
    onError: (error) => setFormError(error.message),
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      name: String(form.get("name")),
      grade_number: Number(form.get("grade_number")),
      academic_year: String(form.get("academic_year")),
      section: String(form.get("section")) || undefined,
    });
    event.currentTarget.reset();
  };

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Academic structure</div>
          <h1>Classes & sections</h1>
          <p>
            Maintain grade sections across academic years and associate
            subjects.
          </p>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Create a class</h2>
          <p>Grades 1–12; the grade/year/section combination must be unique.</p>
        </div>
        <form className="admin-form-grid compact" onSubmit={submit}>
          <label>
            Display name
            <input
              name="name"
              required
              maxLength={100}
              placeholder="Class 8 - A"
            />
          </label>
          <label>
            Grade
            <select name="grade_number" required defaultValue="">
              <option value="" disabled>
                Select grade
              </option>
              {Array.from({ length: 12 }, (_, index) => (
                <option key={index + 1} value={index + 1}>
                  Grade {index + 1}
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
              placeholder="2026-27"
            />
          </label>
          <label>
            Section
            <input name="section" maxLength={20} placeholder="A" />
          </label>
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Creating…" : "Create class"}
            </button>
          </div>
        </form>
        {formError && <ErrorState message={formError} />}
      </section>
      <section className="admin-panel">
        <div className="admin-toolbar">
          <label>
            Academic year filter
            <input
              value={academicYear}
              onChange={(event) => setAcademicYear(event.target.value)}
              placeholder="All academic years"
            />
          </label>
        </div>
        {classes.isLoading ? (
          <div className="admin-loading" role="status">
            Loading classes…
          </div>
        ) : classes.isError ? (
          <ErrorState message={classes.error.message} />
        ) : classes.data?.items.length === 0 ? (
          <p className="admin-empty">No classes have been configured.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Grade</th>
                  <th>Academic year</th>
                  <th>Students</th>
                  <th>Subjects</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {classes.data?.items.map((item) => (
                  <ClassRow
                    key={item.id}
                    item={item}
                    subjects={subjects.data?.items ?? []}
                    onAssign={(subjectId) =>
                      assignSubject.mutate({ classId: item.id, subjectId })
                    }
                    onToggle={(active) =>
                      toggle.mutate({ id: item.id, active })
                    }
                    onSave={(values) =>
                      updateClass.mutate({ id: item.id, values })
                    }
                    busy={
                      assignSubject.isPending ||
                      toggle.isPending ||
                      updateClass.isPending
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {assignSubject.isError && (
          <ErrorState message={assignSubject.error.message} />
        )}
        {toggle.isError && <ErrorState message={toggle.error.message} />}
      </section>
    </div>
  );
}

function ClassRow({
  item,
  subjects,
  onAssign,
  onToggle,
  onSave,
  busy,
}: {
  item: AcademicClass;
  subjects: Subject[];
  onAssign: (subjectId: string) => void;
  onToggle: (active: boolean) => void;
  onSave: (values: Record<string, unknown>) => void;
  busy: boolean;
}) {
  const assigned = new Set(item.subjects.map((subject) => subject.id));
  const [subjectId, setSubjectId] = useState("");
  const [editing, setEditing] = useState(false);
  return (
    <tr>
      <td>
        {editing ? (
          <input
            aria-label="Class display name"
            defaultValue={item.name}
            form={`class-edit-${item.id}`}
            name="name"
            required
            maxLength={100}
          />
        ) : (
          <>
            <strong>{item.name}</strong>
            <small className="table-subtext">
              {item.section ? `Section ${item.section}` : "No section label"}
            </small>
          </>
        )}
      </td>
      <td>
        {editing ? (
          <select
            aria-label="Class grade"
            defaultValue={item.grade_number}
            form={`class-edit-${item.id}`}
            name="grade_number"
          >
            {Array.from({ length: 12 }, (_, index) => (
              <option key={index + 1} value={index + 1}>
                {index + 1}
              </option>
            ))}
          </select>
        ) : (
          item.grade_number
        )}
      </td>
      <td>
        {editing ? (
          <input
            aria-label="Class academic year"
            defaultValue={item.academic_year}
            form={`class-edit-${item.id}`}
            name="academic_year"
            required
            pattern="20[0-9]{2}[-/]([0-9]{2})"
          />
        ) : (
          item.academic_year
        )}
      </td>
      <td>{item.student_count}</td>
      <td>
        <div className="subject-tags">
          {item.subjects.map((subject) => (
            <span key={subject.id}>{subject.name}</span>
          ))}
        </div>
        {item.is_active && (
          <div className="inline-assignment">
            <select
              aria-label={`Subject for ${item.name}`}
              value={subjectId}
              onChange={(event) => setSubjectId(event.target.value)}
            >
              <option value="">Add subject…</option>
              {subjects
                .filter((subject) => !assigned.has(subject.id))
                .map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
            </select>
            <button
              className="admin-button subtle"
              disabled={!subjectId || busy}
              onClick={() => {
                onAssign(subjectId);
                setSubjectId("");
              }}
            >
              Add
            </button>
          </div>
        )}
      </td>
      <td>
        <span className={`admin-status ${item.is_active ? "active" : ""}`}>
          {item.is_active ? "Active" : "Inactive"}
        </span>
      </td>
      <td>
        {editing ? (
          <form
            id={`class-edit-${item.id}`}
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              onSave({
                name: String(form.get("name")),
                grade_number: Number(form.get("grade_number")),
                academic_year: String(form.get("academic_year")),
                section: String(form.get("section")) || null,
              });
              setEditing(false);
            }}
          >
            <input
              aria-label="Class section"
              defaultValue={item.section ?? ""}
              name="section"
              maxLength={20}
            />
            <button
              className="admin-button subtle"
              type="submit"
              disabled={busy}
            >
              Save
            </button>
            <button
              className="admin-button subtle"
              type="button"
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </form>
        ) : (
          <>
            <button
              className="admin-button subtle"
              disabled={busy}
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            <button
              className="admin-button subtle"
              disabled={busy}
              onClick={() =>
                window.confirm(
                  `${item.is_active ? "Deactivate" : "Activate"} ${item.name}?`,
                ) && onToggle(!item.is_active)
              }
            >
              {item.is_active ? "Deactivate" : "Activate"}
            </button>
          </>
        )}
      </td>
    </tr>
  );
}

export function AdminSubjectsPage() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const subjects = useQuery({
    queryKey: ["admin", "subjects"],
    queryFn: () => adminService.subjects({ page_size: 100 }),
  });
  const classes = useQuery({
    queryKey: ["admin", "classes", "active"],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const create = useMutation({
    mutationFn: adminService.createSubject,
    onSuccess: () => {
      setMessage("");
      invalidateAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminService.subjectStatus(id, active),
    onSuccess: () => invalidateAdmin(queryClient),
  });
  const updateSubject = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: Record<string, unknown>;
    }) => adminService.updateSubject(id, values),
    onSuccess: () => invalidateAdmin(queryClient),
    onError: (error) => setMessage(error.message),
  });
  const assign = useMutation({
    mutationFn: () => adminService.assignSubject(classId, subjectId),
    onSuccess: () => {
      invalidateAdmin(queryClient);
      setMessage("Subject assigned to the class.");
      setSubjectId("");
    },
    onError: (error) => setMessage(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      name: String(form.get("name")),
      code: String(form.get("code")),
      description: String(form.get("description")) || undefined,
    });
    event.currentTarget.reset();
  };

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Academic catalogue</div>
          <h1>Subjects</h1>
          <p>Create subjects and connect them to active classes.</p>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Create subject</h2>
        </div>
        <form className="admin-form-grid compact" onSubmit={submit}>
          <label>
            Subject name
            <input name="name" required maxLength={150} />
          </label>
          <label>
            Subject code
            <input name="code" required maxLength={50} />
          </label>
          <label className="span-two">
            Description
            <textarea name="description" rows={2} maxLength={1000} />
          </label>
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Creating…" : "Create subject"}
            </button>
          </div>
        </form>
      </section>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Assign a subject to a class</h2>
          <p>A subject can be used by multiple classes within this school.</p>
        </div>
        <div className="admin-toolbar">
          <label>
            Class
            <select
              value={classId}
              onChange={(event) => setClassId(event.target.value)}
            >
              <option value="">Select class</option>
              {classes.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.academic_year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject
            <select
              value={subjectId}
              onChange={(event) => setSubjectId(event.target.value)}
            >
              <option value="">Select subject</option>
              {subjects.data?.items
                .filter((subject) => subject.is_active)
                .map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
            </select>
          </label>
          <button
            className="admin-button primary"
            disabled={!classId || !subjectId || assign.isPending}
            onClick={() => assign.mutate()}
          >
            {assign.isPending ? "Assigning…" : "Assign subject"}
          </button>
        </div>
        {message && (
          <p
            className={
              assign.isError || create.isError ? "admin-error" : "admin-success"
            }
            role={assign.isError || create.isError ? "alert" : "status"}
          >
            {message}
          </p>
        )}
      </section>
      <section className="admin-panel">
        {subjects.isLoading ? (
          <div className="admin-loading" role="status">
            Loading subjects…
          </div>
        ) : subjects.isError ? (
          <ErrorState message={subjects.error.message} />
        ) : subjects.data?.items.length === 0 ? (
          <p className="admin-empty">No subjects have been created.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Code</th>
                  <th>Assigned classes</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {subjects.data?.items.map((subject) => (
                  <SubjectRow
                    key={subject.id}
                    subject={subject}
                    onToggle={(active) =>
                      toggle.mutate({ id: subject.id, active })
                    }
                    onSave={(values) =>
                      updateSubject.mutate({ id: subject.id, values })
                    }
                    busy={toggle.isPending || updateSubject.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {toggle.isError && <ErrorState message={toggle.error.message} />}
        {updateSubject.isError && (
          <ErrorState message={updateSubject.error.message} />
        )}
      </section>
    </div>
  );
}

function SubjectRow({
  subject,
  onToggle,
  onSave,
  busy,
}: {
  subject: Subject;
  onToggle: (active: boolean) => void;
  onSave: (values: Record<string, unknown>) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <tr>
      <td>
        {editing ? (
          <input
            aria-label="Subject name"
            name="name"
            defaultValue={subject.name}
            form={`subject-edit-${subject.id}`}
            required
            maxLength={150}
          />
        ) : (
          <>
            <strong>{subject.name}</strong>
            {subject.description && (
              <small className="table-subtext">{subject.description}</small>
            )}
          </>
        )}
      </td>
      <td>
        {editing ? (
          <input
            aria-label="Subject code"
            name="code"
            defaultValue={subject.code}
            form={`subject-edit-${subject.id}`}
            required
            maxLength={50}
          />
        ) : (
          subject.code
        )}
      </td>
      <td>
        {subject.classes.length
          ? subject.classes.map((item) => item.name).join(", ")
          : "—"}
      </td>
      <td>
        <span className={`admin-status ${subject.is_active ? "active" : ""}`}>
          {subject.is_active ? "Active" : "Inactive"}
        </span>
      </td>
      <td>
        {editing ? (
          <form
            id={`subject-edit-${subject.id}`}
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              onSave({
                name: String(form.get("name")),
                code: String(form.get("code")),
              });
              setEditing(false);
            }}
          >
            <button className="admin-button subtle" disabled={busy}>
              Save
            </button>
            <button
              className="admin-button subtle"
              type="button"
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </form>
        ) : (
          <>
            <button
              className="admin-button subtle"
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            <button
              className="admin-button subtle"
              onClick={() =>
                window.confirm(
                  `${subject.is_active ? "Deactivate" : "Activate"} ${subject.name}?`,
                ) && onToggle(!subject.is_active)
              }
            >
              {subject.is_active ? "Deactivate" : "Activate"}
            </button>
          </>
        )}
      </td>
    </tr>
  );
}

export function AdminChaptersPage() {
  const queryClient = useQueryClient();
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [message, setMessage] = useState("");
  const classes = useQuery({
    queryKey: ["admin", "classes", "active"],
    queryFn: () => adminService.classes({ is_active: true, page_size: 100 }),
  });
  const subjects = useQuery({
    queryKey: ["admin", "subjects", "active"],
    queryFn: () => adminService.subjects({ is_active: true, page_size: 100 }),
  });
  const availableSubjects =
    subjects.data?.items.filter((subject) => {
      const selectedClass = classes.data?.items.find(
        (item) => item.id === classId,
      );
      return selectedClass?.subjects.some((item) => item.id === subject.id);
    }) ?? [];
  const chapters = useQuery({
    queryKey: ["admin", "chapters", classId, subjectId],
    queryFn: () =>
      adminService.chapters({
        class_id: classId || undefined,
        subject_id: subjectId || undefined,
        page_size: 100,
      }),
  });
  const create = useMutation({
    mutationFn: adminService.createChapter,
    onSuccess: () => {
      setMessage("");
      invalidateAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminService.chapterStatus(id, active),
    onSuccess: () => invalidateAdmin(queryClient),
    onError: (error) => setMessage(error.message),
  });
  const update = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: Record<string, unknown>;
    }) => adminService.updateChapter(id, values),
    onSuccess: () => {
      setMessage("");
      invalidateAdmin(queryClient);
    },
    onError: (error) => setMessage(error.message),
  });
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      class_id: String(form.get("class_id")),
      subject_id: String(form.get("subject_id")),
      chapter_number: Number(form.get("chapter_number")),
      title: String(form.get("title")),
      description: String(form.get("description")) || undefined,
    });
    event.currentTarget.reset();
  };

  return (
    <div className="admin-page">
      <div className="admin-page-heading">
        <div>
          <div className="admin-eyebrow">Learning structure</div>
          <h1>Chapters</h1>
          <p>
            Organize chapter content within a class and its assigned subject.
          </p>
        </div>
      </div>
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <h2>Create chapter</h2>
          <p>
            Only subject/class combinations already assigned together can be
            selected.
          </p>
        </div>
        <form className="admin-form-grid compact" onSubmit={submit}>
          <label>
            Class
            <select
              name="class_id"
              required
              value={classId}
              onChange={(event) => {
                setClassId(event.target.value);
                setSubjectId("");
              }}
            >
              <option value="">Select class</option>
              {classes.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.academic_year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject
            <select
              name="subject_id"
              required
              value={subjectId}
              onChange={(event) => setSubjectId(event.target.value)}
            >
              <option value="">Select subject</option>
              {availableSubjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chapter number
            <input name="chapter_number" type="number" min={1} required />
          </label>
          <label>
            Title
            <input name="title" required maxLength={200} />
          </label>
          <label className="span-two">
            Description
            <textarea name="description" rows={2} maxLength={2000} />
          </label>
          <div className="admin-form-actions">
            <button
              className="admin-button primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Saving…" : "Create chapter"}
            </button>
          </div>
        </form>
        {message && <ErrorState message={message} />}
      </section>
      <section className="admin-panel">
        {chapters.isLoading ? (
          <div className="admin-loading" role="status">
            Loading chapters…
          </div>
        ) : chapters.isError ? (
          <ErrorState message={chapters.error.message} />
        ) : chapters.data?.items.length === 0 ? (
          <p className="admin-empty">
            No chapters match this academic context.
          </p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Chapter</th>
                  <th>Class</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {chapters.data?.items.map((chapter: Chapter) => (
                  <ChapterRow
                    key={chapter.id}
                    chapter={chapter}
                    onToggle={(active) =>
                      toggle.mutate({ id: chapter.id, active })
                    }
                    onSave={(values) =>
                      update.mutate({ id: chapter.id, values })
                    }
                    busy={toggle.isPending || update.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {toggle.isError && <ErrorState message={toggle.error.message} />}
        {update.isError && <ErrorState message={update.error.message} />}
      </section>
    </div>
  );
}

function ChapterRow({
  chapter,
  onToggle,
  onSave,
  busy,
}: {
  chapter: Chapter;
  onToggle: (active: boolean) => void;
  onSave: (values: Record<string, unknown>) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <tr>
      <td>
        {editing ? (
          <input
            aria-label="Chapter number"
            name="chapter_number"
            type="number"
            min={1}
            defaultValue={chapter.chapter_number}
            form={`chapter-edit-${chapter.id}`}
            required
          />
        ) : (
          chapter.chapter_number
        )}
      </td>
      <td>
        {editing ? (
          <input
            aria-label="Chapter title"
            name="title"
            defaultValue={chapter.title}
            form={`chapter-edit-${chapter.id}`}
            required
            maxLength={200}
          />
        ) : (
          <>
            <strong>{chapter.title}</strong>
            {chapter.description && (
              <small className="table-subtext">{chapter.description}</small>
            )}
          </>
        )}
      </td>
      <td>{chapter.class_name}</td>
      <td>{chapter.subject_name}</td>
      <td>
        <span className={`admin-status ${chapter.is_active ? "active" : ""}`}>
          {chapter.is_active ? "Active" : "Inactive"}
        </span>
      </td>
      <td>
        {editing ? (
          <form
            id={`chapter-edit-${chapter.id}`}
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              onSave({
                chapter_number: Number(form.get("chapter_number")),
                title: String(form.get("title")),
              });
              setEditing(false);
            }}
          >
            <button className="admin-button subtle" disabled={busy}>
              Save
            </button>
            <button
              className="admin-button subtle"
              type="button"
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </form>
        ) : (
          <>
            <button
              className="admin-button subtle"
              onClick={() => setEditing(true)}
            >
              Edit / reorder
            </button>
            <button
              className="admin-button subtle"
              onClick={() =>
                window.confirm(
                  `${chapter.is_active ? "Deactivate" : "Activate"} ${chapter.title}?`,
                ) && onToggle(!chapter.is_active)
              }
            >
              {chapter.is_active ? "Deactivate" : "Activate"}
            </button>
          </>
        )}
      </td>
    </tr>
  );
}

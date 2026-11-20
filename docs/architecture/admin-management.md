# School admin management

The admin module provides a web dashboard and versioned API for managing people, academic structures, and the question bank within one school. It does not include quiz delivery, assessment, or analytics workflows.

## Access and school scope

- Every admin endpoint requires an authenticated active user with the `ADMIN` role.
- The backend derives the school scope from that administrator's `User.school_id`. Requests cannot supply or override a school ID.
- A school-less administrator receives HTTP 403 until an operator assigns the account to a school. Use the bootstrap CLI for a new school and administrator; assign existing accounts through an approved database operation.
- Records belonging to another school are treated as not found. Cross-school links are also rejected by database constraints where the schema supports them.
- Frontend role-protected routes and navigation improve usability but are not authorization boundaries; the API enforces access.

## Initial setup

Apply migrations before starting the API and creating the first school administrator:

```powershell
Set-Location backend
alembic upgrade head
python -m app.cli --name "School Administrator" --email admin@example.com --school-code NTH --school-name "North School"
```

The CLI securely prompts for and hashes the administrator password. `--school-code` is required. If the code exists, the administrator is attached to that school. If it does not exist, `--school-name` is required and the school is created in the same transaction. The bootstrap process requires the `ADMIN` role seeded by migrations.

Admin-created student and teacher accounts receive a generated temporary password. The API returns that password only in the successful creation response; the database stores only its Argon2id hash. The interface displays it once for the operator to copy. No email/SMS delivery or mandatory password-change flow is implemented, so the operator must hand it to the person through an approved secure channel. Do not copy it into tickets, logs, or shared documents.

## Supported workflows

- Dashboard counts for active people and academic records.
- Paginated student and teacher search/filter, profile detail/edit, status changes, and account provisioning.
- Class, subject, and chapter management, including class-subject linking.
- Student enrollment, enrollment history, and transfers that preserve the former class/year records.
- Teacher assignment to a class, subject, and academic year.
- Question-bank CRUD, multilingual translations, approval/archive workflow, search, statistics, and CSV/XLSX imports.
- Referenced academic records are deactivated rather than destructively deleted.

The API is mounted at `/api/v1/admin`. Its resource groups are `dashboard/stats`, `students`, `teachers`, `classes`, `subjects`, `chapters`, `enrollments`, `teacher-assignments`, and `questions`. Create/update operations validate school context and conflicts and return explicit errors; list endpoints support pagination and relevant search/filter parameters. See the FastAPI OpenAPI page at `/docs` for exact schemas. Question-bank routes and import behavior are detailed in [question-bank.md](question-bank.md).

## Data integrity and migrations

Migrations `20261118_0006` and `20261118_0007` support repeat enrollment transfers and normalized school-local identity constraints. The latter adds case-insensitive uniqueness for school usernames/emails and normalized identity rules for subjects and sectionless classes. Review existing production data for conflicting duplicates before applying this migration. Do not run downgrades against production without a separately reviewed recovery plan; downgrade of the transfer-history constraint can be blocked by repeated transfers.

The backend tests use isolated SQLite databases. Offline Alembic SQL generation verifies migration structure but does not replace testing upgrade/downgrade against a disposable PostgreSQL instance. Back up and preflight production data before applying migrations.

## Known limitations

- There is no admin UI for creating schools or transferring an administrator between schools. Bootstrap supports initial school creation; later tenant reassignment requires an audited operator procedure.
- Temporary credentials are returned once but there is no forced password reset or credential-delivery integration.
- The API provides CRUD-like create/read/update/deactivate operations for listed resources. Question-bank questions are archived rather than deleted; quiz delivery, results, and analytics remain outside this module.

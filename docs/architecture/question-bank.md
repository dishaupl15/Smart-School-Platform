# Question bank

The admin question bank manages school-owned, reusable single-choice MCQs. It uses the existing `questions`, `question_translations`, `question_options`, and `option_translations` tables. Every question belongs to an academic chapter; chapter constraints tie class, subject, school and question context together. Question text and option text are persisted separately for English (`en`), Hindi (`hi`), and Marathi (`mr`).

## Status workflow

- **DRAFT** — editable; translations may be incomplete.
- **REVIEW** — explicitly submitted by an administrator.
- **APPROVED** — validated and eligible for future quiz selection.
- **ARCHIVED** — retained for references/history but unavailable for new quiz selection.

Moving a draft to review requires English question and option text, exactly four options, and exactly one correct option. Approval additionally requires question and option translations in English, Hindi, and Marathi. The API validates the rules regardless of UI state. There is no teacher review role. Admin previews can show correct answers; future student APIs must use separate response schemas that never include `is_correct`, draft/review content, or internal answer keys.

Editing question-bank content does not rewrite attempt snapshots. Existing attempt-question records must continue rendering their stored text and option-order snapshots; future quiz services must not reconstruct historical attempts from current translations/options.

## Admin API

All endpoints require an authenticated active `ADMIN` and derive school scope from that admin's account:

- `GET /api/v1/admin/questions/stats` (compatibility alias: `/api/v1/admin/question-bank/stats`)
- `GET /api/v1/admin/questions` — server-side search, filters, sorting, and pagination.
- `POST /api/v1/admin/questions`, `GET /api/v1/admin/questions/{id}`, `PATCH /api/v1/admin/questions/{id}`
- `POST /api/v1/admin/questions/{id}/duplicate` — intentional draft clone.
- `PATCH /api/v1/admin/questions/{id}/status`, `POST /api/v1/admin/questions/{id}/archive`
- `POST /api/v1/admin/questions/imports/preview`, `POST /api/v1/admin/questions/import/preview`
- `POST /api/v1/admin/questions/import/confirm` with `{ "import_id": "...", "mode": "valid_rows|all_or_nothing" }`; the resource-style alias is `/imports/{id}/confirm` with mode `valid_rows|atomic`.
- `GET /api/v1/admin/questions/import/template` (or `/import-template?format=csv|xlsx`)
- `GET /api/v1/admin/questions/import/report/{import_id}`; report CSV download is `/imports/{id}/report/download`.

No client-supplied school ID is accepted. Foreign-school IDs do not expose records. Duplication creates a new draft and does not copy quiz, attempt, or answer relationships.

## CSV/XLSX import

Download a current template from the admin import page. The downloadable template contains these headers:

`class_id,subject_id,chapter_id,difficulty,question_en,question_hi,question_mr,explanation_en,explanation_hi,explanation_mr,option_a_en,option_a_hi,option_a_mr,option_b_en,option_b_hi,option_b_mr,option_c_en,option_c_hi,option_c_mr,option_d_en,option_d_hi,option_d_mr,correct_option`

The `class_id`, `subject_id`, and `chapter_id` values are UUIDs for active records available to the current school. `difficulty` is `EASY`, `MEDIUM`, or `HARD`; `correct_option` is `A`, `B`, `C`, or `D`. English question text and all four English options are required for an imported draft. Hindi and Marathi text can be completed before approval. Rows are imported as drafts.

Upload `.csv` or `.xlsx` (maximum 2 MiB and 500 rows). The backend validates headers, academic references, lengths, supported values, and duplicate questions. Duplicate checks compare case-insensitive trimmed text by chapter and language, including existing records and earlier rows in the same upload. The explicit `/{id}/duplicate` action is an intentional exception that clones a question into a new draft for editing. Preview is bound to the initiating admin and school and makes no database writes. Confirmation revalidates staged data before writing. Preview/import reports remain available for 30 minutes unless capacity eviction removes them sooner.

Choose one import policy:

- **Valid rows only:** insert valid, non-duplicate rows; report and reject every invalid/duplicate row.
- **All or nothing:** any invalid/duplicate row blocks the transaction. An all-or-nothing transaction is rolled back if a row fails during confirmation.

Missing Hindi and Marathi question or option translations are shown as preview warnings; English content remains required. CSV exports neutralize spreadsheet formulas in all user-influenced report fields, including errors and warnings. Invalid rows and their validation reasons are available in the import report. Do not upload student data or sensitive information.

## Local operation and tests

Apply migrations before starting the API:

```powershell
Set-Location backend
alembic upgrade head
uvicorn app.main:app --reload
```

Run backend tests with `python -m pytest` and frontend tests from `frontend` with `npm test`. The isolated database tests use SQLite; validate native PostgreSQL behavior and migrations against a disposable PostgreSQL instance before production. API request and response schemas are available through `/docs`.

## Capacity and security

Pagination and indexed school/status, chapter, translation and option relationships support the expected initial volume of roughly 200 questions per chapter without loading the complete bank. Search and filters run on the server. Upload parsing does not execute spreadsheet formulas or macros and caps worksheet size. Approval/status transitions and context validation are enforced on the backend, not trusted to the browser. The short-lived preview cache is process-local, bounded to 100 previews, uses random UUID IDs and owner/school binding, and purges expired entries. Use one API worker or sticky routing for preview/confirm/report; restart or worker changes expire pending imports. CSV report exports neutralize spreadsheet formulas in all user-controlled report cells.

The existing question-bank tables and ownership/context constraints already support these APIs, so no migration is needed. CSV parsing uses Python's standard library; XLSX and multipart support use `openpyxl` and `python-multipart`.

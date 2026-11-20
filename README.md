# Smart School Learning

A modular-monolith foundation for a multilingual school learning and assessment platform. The frontend and backend are separate applications connected through a versioned REST API. The project includes the school-domain schema and an initial authentication milestone; quiz delivery and assessment workflows are not implemented yet.

## Technology

- **Frontend:** React, TypeScript (strict), Vite, Tailwind CSS, shadcn/ui-compatible styling, React Router, TanStack Query, React Hook Form, Zod, i18next
- **Backend:** Python, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, PostgreSQL, Uvicorn
- **Quality:** ESLint, Prettier, Vitest, Testing Library, Pytest
- **Database:** Supabase-hosted PostgreSQL

## Project structure

```text
frontend/
  src/
    app/             App providers and error boundary
    components/      Shared UI and loading state
    features/        Feature-oriented modules as functionality is added
    i18n/locales/    English, Hindi, and Marathi translations
    layouts/         Responsive application shell
    pages/           Route-level pages
    routes/          React Router configuration
    schemas/         Shared form-validation schema location
    services/        Centralized API client
    types/           Shared frontend types
    utils/           Shared utilities
backend/
  app/
    api/v1/          Versioned routers and endpoints
    core/            Settings, security, errors, and logging
    db/              SQLAlchemy engine, session, and base
    models/          SQLAlchemy model modules
    repositories/    Database-access layer for future modules
    schemas/         Pydantic API schemas
    services/        Business logic for future modules
    utils/           Backend utilities
  migrations/        Alembic environment and schema revisions
  tests/             API and health endpoint tests
docs/architecture/   Architecture and extension guidance
```

## Prerequisites

- Node.js 20.19+ (or 22.12+) and npm
- Python 3.11+
- A Supabase project with PostgreSQL access

## Supabase database and local setup

1. Create a Supabase project.
2. In the Supabase dashboard, open **Connect** and copy the **Session Pooler** PostgreSQL connection string (port `5432`). Use URL-encoded credentials if the password contains special characters and include `sslmode=require` if it is not already present.
3. From the project root, create the backend environment file only if it does not already exist:

   ```powershell
   if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
   ```

   Edit `backend/.env` and set `DATABASE_URL` to the connection string. Never put backend credentials in `frontend/.env` or variables prefixed with `VITE_`. Supabase is only the PostgreSQL host; the application continues to use its existing FastAPI authentication and authorization.
4. Install Python dependencies and apply migrations manually, from the project root:

   ```powershell
   Set-Location backend
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   alembic upgrade head
   ```

   Migrations are not run automatically. This applies the existing migration history to the configured Supabase database; it does not seed school, student, or question records.
5. Start FastAPI from `backend` with the virtual environment activated:

   ```powershell
   uvicorn app.main:app --reload
   ```
6. In another terminal, install frontend dependencies and start React/Vite:

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```
7. Verify database connectivity at `http://localhost:8000/api/v1/health/database`. The API is at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

Docker Desktop and a local PostgreSQL container are not required. Configure `CORS_ORIGINS` as a comma-separated list of trusted frontend origins. Before deploying, configure a high-entropy `JWT_SECRET_KEY` (at least 32 characters), set `APP_ENV=production`, and enable `REFRESH_COOKIE_SECURE=true`. Review the cookie, CORS, and rate-limiting requirements in [the authentication guide](./docs/architecture/authentication.md).

## Tests and quality checks

Frontend, from `frontend`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run format:check
```

Backend, from `backend` with the virtual environment activated:

```powershell
python -m pytest
```

Tests for the database health endpoint mock database connectivity, so the backend test suite does not require a live PostgreSQL server.

## Current implementation status

- Responsive welcome/dashboard shell, navigation, and working English/Hindi/Marathi language switching
- Central frontend routing, query client, API client, loading/error handling, and strict TypeScript configuration
- FastAPI application factory, versioned router, CORS/settings/logging, SQLAlchemy session management, and health checks
- Alembic baseline migration and optional PostgreSQL Compose service
- Initial frontend and backend automated tests
- Typed SQLAlchemy domain schema for schools, users/roles, academics, enrollments, question bank, quizzes, attempts, answers, and historical snapshots
- Isolated SQLite database model tests and a full Alembic domain migration
- Argon2id password hashing, short-lived access tokens, rotating refresh sessions, role-based authorization, and an administrator bootstrap command
- School-scoped admin dashboard and management workflows for students, teachers, classes, subjects, chapters, enrollments, and teacher assignments
- Multilingual admin question bank with draft/review/approval/archive workflow, search, preview, duplication, and CSV/XLSX bulk import
- Quiz delivery, student assessment workflows, scoring, and analytics remain future work

## Recommended next milestone

Implement quiz delivery and attempt workflows using only approved questions, preserving school-scoped authorization and the schema's historical-attempt guarantees.

# Architecture overview

## Application shape

Smart School Learning is a modular monolith with two independently runnable applications: a React single-page frontend and a FastAPI backend. The backend is one deployable application with modules organized by responsibility; it is not split into microservices.

```text
Browser
  └── React + TypeScript frontend
        └── versioned JSON/REST requests
              └── FastAPI /api/v1
                    ├── API routers and request schemas
                    ├── services (business rules)
                    ├── repositories (database access)
                    └── SQLAlchemy sessions
                          └── PostgreSQL
```

## Frontend/backend separation

The frontend owns presentation, navigation, client-side validation, and translations. `src/services/api-client.ts` is the shared boundary for HTTP requests; it reads only the public `VITE_API_BASE_URL` variable. Backend secrets and database URLs stay in backend environment configuration and are never bundled into browser code.

Routes are declared centrally. Shared providers (TanStack Query and error handling) are configured once at application startup. Feature-specific pages, hooks, schemas, and API services can be added under `src/features` as the product grows.

## Backend request flow

Versioned routes live under `app/api/v1`. Route handlers validate input/output with Pydantic schemas and delegate business rules to services. Services use repositories for persistence where that separation benefits the feature. SQLAlchemy models and the database session lifecycle are centralized under `app/db` and `app/models`; Alembic migrations define the school, academic, enrollment, question-bank, assessment, authentication-session, and admin identity structures. Student quiz delivery snapshots selected approved questions and shuffled options on each attempt; the API exposes correctness only after submission.

Application settings are loaded from environment variables, with a `.env` file supported for local development. CORS origins, database connection/pool options, logging level, environment mode, and the quiz timer (`QUIZ_DURATION_MINUTES`, default 20) are configurable without source changes. The database health endpoint returns generic status only.

See [student quiz delivery](student-quizzes.md) for the student API, attempt lifecycle, expiry, and response privacy rules.

## Adding future modules

For a new domain such as quiz delivery or reporting:

1. Define SQLAlchemy models and constraints in `app/models`.
2. Generate and review an Alembic migration.
3. Add Pydantic request/response schemas in `app/schemas`.
4. Put domain operations in `app/services`; use repositories for nontrivial persistence access.
5. Add a focused router beneath `app/api/v1` and register it in the versioned router.
6. Add backend tests for the service and API contract.
7. Add a frontend feature module for its pages, hooks, schemas, types, and API calls.
8. Add localized strings to all supported locale files.

This keeps presentation, transport, business logic, and persistence from accumulating in route handlers or one global frontend module.

## Development and production

Development uses Vite's local server, Uvicorn reload mode, and optional Compose PostgreSQL. These are independent: a database need not be running to view the initial frontend or call the API health endpoint.

Production configuration is provided through environment variables and deployment-managed secrets. Set explicit trusted CORS origins, a private Supabase PostgreSQL URL, suitable pool sizing, and production logging/environment values. Serve the built frontend through the deployment's chosen static hosting/web server and expose the API over HTTPS. Docker Compose is not required for local or production PostgreSQL.

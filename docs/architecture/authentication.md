# Authentication and account security

The API authenticates with an Argon2id password hash, a short-lived signed access token, and a rotating opaque refresh token. The refresh token is stored only as an HMAC hash in `auth_sessions` and is sent to the browser in an `HttpOnly` cookie. The frontend keeps the access token in memory and sends it as a bearer token. Public registration is disabled.

## Initial administrator

Apply migrations before creating the first administrator:

```powershell
Set-Location backend
alembic upgrade head
python -m app.cli --name "School Administrator" --email admin@example.com --school-code NTH --school-name "North School"
```

The command prompts for the password twice. Passwords must be between 12 and 128 characters. Use `--username` instead of, or in addition to, `--email`. `--school-code` is required; if it does not exist, provide `--school-name` to create the school in the same transaction as the administrator. If the code already exists, that school is used and `--school-name` is ignored. The CLI refuses an existing identifier in the selected school and requires the `ADMIN` role seeded by the migrations.

An administrator without a school association cannot use school-management APIs. There is intentionally no client-supplied school selector; the backend derives the data scope from the authenticated administrator's `school_id`. For operational details, see the [admin management guide](./admin-management.md).

## Production settings

Configure these backend environment variables through the deployment secret manager:

- `APP_ENV=production`
- `JWT_SECRET_KEY`: at least 32 characters of high-entropy secret material; do not reuse across environments
- `REFRESH_COOKIE_SECURE=true`
- `CORS_ORIGINS`: explicit trusted frontend origins, never `*`
- `DATABASE_URL`: PostgreSQL connection URL, stored as a secret

Use HTTPS end-to-end. The refresh cookie defaults to `SameSite=Lax` and path `/api/v1/auth`. If the frontend and API are on different sites and require `SameSite=None`, enable Secure cookies and configure the exact cookie domain/path required by the deployment. Set `REFRESH_COOKIE_DOMAIN` only when needed. The frontend's `VITE_API_BASE_URL` must be a public API URL and must never contain credentials or secrets.

Access tokens expire after 10 minutes by default; refresh sessions expire after 30 days. Refresh tokens rotate on use, and detected reuse revokes the active sessions in that token family. Logout revokes the current refresh-token family. Password changes revoke the user's other sessions. Authentication and authorization decisions are enforced by the backend; client-side route guards are only a user-experience layer.

## Operational limitations

Login throttling currently uses in-memory limits per identifier and per client IP (with a higher IP threshold). It is effective only within one application process and resets on restart. A production deployment with multiple workers or replicas must place equivalent rate limiting at a shared gateway or replace the in-process limiter with a shared store before relying on it as an abuse-control boundary. Ensure the application uses the actual client IP only behind trusted proxy configuration.

Refresh sessions are persisted in the database; PostgreSQL is the supported production database. SQLite is used by isolated tests, where timezone-aware database columns may be returned as naive datetimes and are interpreted as UTC by the application.

## API overview

- `POST /api/v1/auth/login`: accepts username or email, password, and optional school code
- `POST /api/v1/auth/refresh`: rotates the HttpOnly refresh cookie and issues a new access token
- `POST /api/v1/auth/logout`: revokes the refresh-token family and clears the cookie
- `GET /api/v1/auth/me`: returns the current user's safe profile and assigned roles
- `POST /api/v1/auth/change-password`: verifies the current password and changes it

Login and refresh responses do not include password hashes, refresh-token hashes, or stored answer keys. Role checks and active-session checks are server-side.

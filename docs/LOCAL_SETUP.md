# Local setup and troubleshooting

## Requirements

- Docker Desktop with Docker Compose
- Node.js 20 or newer and pnpm
- Python 3.12 or newer for running backend tests outside Docker

## Start from a fresh clone

From the repository root, start all three local services (database, API, and Vite frontend):

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:5173`. The API is at `http://localhost:8000`; local API docs are at `/docs`. Sign-in details for the fictional administrator, editor, reviewer, and viewer are in the root README.

To run Vite on the host instead of in Docker, stop the frontend container with `docker compose stop frontend`, then run `pnpm install --frozen-lockfile` and `pnpm dev` from `frontend/`.

PostgreSQL data lives in the `relieftrail_data` Docker volume. SQL scripts run only when PostgreSQL initializes an empty volume. To rebuild this disposable local database after changing the schema:

```powershell
docker compose down -v
docker compose up --build
```

The `down -v` command permanently removes the local sample database volume. Do not run it if you need to keep local records.

## Environment variables

`.env.example` contains local-only values. Compose supplies safe localhost origins and fictional sample credentials. Production requires a unique `APP_SECRET_KEY` of at least 32 characters, real secret management, secure cookies, HTTPS, and an exact list of frontend origins. Never commit `.env` or production credentials.

## Run backend checks

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
$env:TEST_DATABASE_URL = "postgresql://relieftrail:test-only-password@localhost:5432/relieftrail_test"
python -m pytest backend/tests -q
```

Database integration tests expect a disposable PostgreSQL database initialized from `database/schema.sql` and `database/seed.sql`. Without `TEST_DATABASE_URL`, only those database integration cases are skipped.

## Troubleshooting

- **API says database unavailable:** wait for the `db` health check, then inspect `docker compose logs api db`.
- **Port 5432 or 8000 is already in use:** stop the conflicting local service or change the host-side port in Compose.
- **Browser sign-in fails:** open the frontend at one of the configured localhost origins; do not mix `localhost` and a custom hostname without updating `FRONTEND_ORIGINS`.
- **Schema changes do not appear:** the initialization scripts are one-time scripts for a new database volume; rebuild only if you are comfortable deleting the local demo data.
- **Frontend dependency install fails:** check Node/pnpm versions, then use `pnpm install --frozen-lockfile` from `frontend/`.
- **Tests cannot connect:** ensure the test DB exists, is disposable, is initialized from both SQL scripts, and that `TEST_DATABASE_URL` points to it.

## Deployment boundary

This Compose file is for local development. A real deployment requires a managed PostgreSQL service, HTTPS ingress, private database networking, secret management, backups and restore drills, monitoring, account lifecycle controls, threat review, and organization-specific privacy/retention policies. The current demo accounts must never be deployed.

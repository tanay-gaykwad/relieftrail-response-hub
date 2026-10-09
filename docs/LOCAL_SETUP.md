# Local setup

## Requirements

- Docker Desktop with Docker Compose
- Node.js 20 or newer
- pnpm

## Start the database and API

From the project root:

```powershell
Copy-Item .env.example .env   # Optional: customize the local demo credentials
docker compose up --build
```

PostgreSQL initializes from `database/schema.sql` and `database/seed.sql` the first time its volume is created. The API is at `http://localhost:8000`; OpenAPI docs are at `http://localhost:8000/docs`.

## Start the frontend

In a second terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:5173`. Default local sample login:

- Email: `admin@relieftrail.test`
- Password: `demo-change-me`

Other demo roles: `editor@relieftrail.test` / `editor-demo`, `reviewer@relieftrail.test` / `reviewer-demo`, and `viewer@relieftrail.test` / `viewer-demo`.

These credentials only access fictional seeded records in the local demo. Change them in `.env` if desired. Do not use them for any real service.

## Reset the fictional database

The database persists in a named Docker volume. To remove this local database and initialize a fresh sample dataset:

```powershell
docker compose down -v
docker compose up --build
```

This permanently removes that local volume's contents. Use it only for the disposable demo. SQL initialization scripts run only for a new volume; this project does not yet include production migration tooling.


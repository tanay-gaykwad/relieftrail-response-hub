# ReliefTrail ResponseHub

An end-to-end portfolio demo for a fictional nonprofit finance team. It brings response context, reported contributions and disbursements, spreadsheet imports, human review flags, and an activity history into one organization-scoped workspace.

This is a separate follow-on project to [ReliefTrail's earlier contract prototype](https://github.com/tanay-gaykwad/relieftrail-blockchain). The earlier repository explores smart-contract event ideas; this application explores the database and workflow around those events. The contract is not currently connected, and the app does not accept donations, move money, or prove aid delivery.

> **Demo safety:** All seeded people, organizations, response records, references, and amounts are fictional. Use only the sample credentials and do not enter real donor, beneficiary, bank, or payment information. This learning project is not production-certified and must not be used for operational humanitarian data.

## What you can do

- Sign in to a sample organization workspace.
- View response and funding summaries, review flags, and recent actions.
- Create and update response records. Editors can remove an empty draft; responses with funding or review history are protected.
- Import a CSV after full-file validation; accepted rows are committed together, duplicates are skipped, and the file is processed in memory only.
- Search and export the fictional funding records.
- Resolve a review flag and see who performed the action in the activity history.

The API checks a signed, short-lived bearer token on organization data routes. Users are attached to organizations through membership rows and have one of four roles: `org_admin`, `editor`, `reviewer`, or `viewer`. Reads are scoped to memberships. Response editing and CSV imports require an editor or organization administrator; only admins can approve/close a response; issue resolution also allows reviewers. A database trigger rejects changes to or deletion of audit rows.

These controls are a useful foundation to learn from, not proof that the system is safe for a real NGO. It does not yet include self-service account creation, invite and recovery flows, MFA, rate limiting, production secret management, deployment hardening, backups, or an independent security review.

## Run locally

Requirements: Docker Desktop with Compose, Node.js 20+, and pnpm.

1. (Optional) Copy `.env.example` to `.env` to change local demo settings. Never commit `.env`.
2. Start PostgreSQL and the API from this folder:

   ```powershell
   docker compose up --build
   ```

3. In another terminal, start the frontend:

   ```powershell
   cd frontend
   pnpm install --frozen-lockfile
   pnpm dev
   ```

4. Open `http://localhost:5173` and sign in using one of the fictional accounts below. API docs are at `http://localhost:8000/docs`.

| Role | Email | Password |
| --- | --- | --- |
| Organization admin | `admin@relieftrail.test` | `demo-change-me` |
| Editor | `editor@relieftrail.test` | `editor-demo` |
| Reviewer | `reviewer@relieftrail.test` | `reviewer-demo` |
| Viewer | `viewer@relieftrail.test` | `viewer-demo` |

PostgreSQL runs in a named Docker volume. SQL files under `database/` are applied on the first database start. If you change the initial schema and want to rebuild this disposable demo from scratch, run `docker compose down -v` (this removes the local database contents), then `docker compose up --build`.

## Database design

The schema is in [`database/schema.sql`](database/schema.sql), sample data in [`database/seed.sql`](database/seed.sql), and query examples in [`database/queries.sql`](database/queries.sql). The design separates organizations, users, organization memberships, responses, sources, import batches, funding records, reconciliation issues, and audit events. Foreign keys and checks protect references and allowed values. `response_funding_summary` derives totals from funding rows rather than storing duplicated totals. The ER diagram and normalization notes are in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md).

## Project files

```text
frontend/          React + TypeScript dashboard
backend/           FastAPI API, login, role checks, CSV workflow
database/          PostgreSQL schema, seed data, SQL examples
docs/              Product brief, data model, setup guide
output/pdf/        Project report for coursework submission
```

## Portfolio links and artifacts

- Companion project: [ReliefTrail contract prototype](https://github.com/tanay-gaykwad/relieftrail-blockchain)
- Project brief: [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md)
- Local setup: [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md)
- Course report: [`output/pdf/relieftrail-funding-workspace-report.pdf`](output/pdf/relieftrail-funding-workspace-report.pdf)
- Interface preview: [`screenshots/dashboard-interface-preview.png`](screenshots/dashboard-interface-preview.png) (illustrative; capture a live database-backed screen after local startup)

## Roadmap

1. Current learning demo: database-backed dashboard, sample login, organization membership and role checks, CSV import/export, review queue, and audit history.
2. Build proper user administration (invites, role changes, password reset, MFA) and authorization-focused verification.
3. Expand reconciliation rules and provide a reviewable correction workflow.
4. Explore AI only for suggesting spreadsheet mappings and drafting source-linked reports; a human must approve the result.
5. Connect contract events as a read-only source with explicit provenance.
6. Interview NGO finance and grants staff before making product or commercial claims; complete privacy, operational, and security reviews before any real pilot.


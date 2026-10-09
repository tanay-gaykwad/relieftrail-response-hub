# Project brief

## Product idea

**ReliefTrail Funding Workspace** is a learning project for an internal nonprofit funding-reconciliation workflow. A staff member sees response context and reported funding records together, imports a partner spreadsheet, reviews questionable entries, and keeps a traceable action history.

It is a standalone evolution of [the earlier ReliefTrail contract prototype](https://github.com/tanay-gaykwad/relieftrail-blockchain). The contract repository explores a source of event records; this app focuses on people, organizations, relational data, review workflow, and reporting. The two repositories are linked by the product story, not yet connected by software.

The product idea is informed by public humanitarian funding and data-exchange platforms, but this exact workflow has not been validated with organizations. This project is not a fundraiser, payment system, proof of aid delivery, or replacement for established reporting platforms.

## User workflow

1. Sign into the demo organization.
2. Review the dashboard and response/funding context allowed for the user's memberships.
3. Create or update a response if the account has an editor role; safely delete only an unused draft.
4. Import a sample CSV after complete validation; rows are saved in one transaction and duplicates are skipped.
5. Review a human-created flag and resolve it if the account has an appropriate role.
6. Check the append-only action history and export sample records.

## Objectives demonstrated

- Design a relational schema with normalized entities, keys, constraints, indexes, and organization membership.
- Use joins, aggregates, a view, and a trigger in PostgreSQL.
- Build a typed frontend and a Python API over the database.
- Handle authentication, organization-level access checks, roles, and transaction-backed audit writes.
- Validate and import external CSV data safely enough for a controlled fictional demo.
- Document the product boundary and the next learning steps.

## Trust and safety boundaries

- All portfolio records and the demonstration account are fictional.
- Avoid collecting beneficiary names, addresses, health information, bank details, or private evidence.
- Funding rows are reports of records, not evidence that aid was received or delivered.
- AI can later suggest spreadsheet mappings or draft source-linked summaries, but people must check them. It must not decide eligibility, approve aid, move money, or publish claims automatically.
- Do not deploy with demo secrets or use real organizational data. A real pilot requires interviews, privacy and security review, proper hosting and backups, and operational ownership.


# Product scope and demo walkthrough

## Intended users

ResponseHub models a small relief organization that needs to keep response activity, restricted funding, spending records, reporting deadlines, and review actions connected. It is an internal operations workflow, not a public donation portal or payment processor.

## Roles

| Role | View data | Edit responses and awards | Submit reports | Review reports | Resolve flags | Change team roles |
| --- | --- | --- | --- | --- | --- | --- |
| `org_admin` | Yes | Yes; may approve/close responses | Yes | Yes | Yes | Yes |
| `editor` | Yes | Yes; cannot approve/close | Yes | No | Yes | No |
| `reviewer` | Yes | No | No | Yes | Yes | No |
| `viewer` | Yes | No | No | No | No | No |

Roles are scoped to an organization. The API performs the checks; hiding a button in the frontend does not grant or revoke access.

## Workflow and success criteria

1. Sign in as the demo administrator (`admin@relieftrail.test` / `demo-change-me`).
2. Review the fictional responses and use **Awards & budgets** to inspect the funder, award ceiling, allocated response budget, spending and upcoming report count.
3. Create an award for an approved response. The system records the restriction, allocation, and reporting milestone together.
4. Record a disbursement against one budget line. The API and database reject overspending or out-of-period activity.
5. Open **Reporting calendar**, submit a summary, then sign in as a reviewer (`reviewer@relieftrail.test` / `reviewer-demo`) to accept or return it.
6. Sign in as a viewer (`viewer@relieftrail.test` / `viewer-demo`) and confirm write actions are rejected by the API.

Success means the records remain linked, the amount and role checks are enforced by the server/database, failed writes roll back, and the audit history identifies the action. It does not mean aid was delivered or that an expense was verified externally.

## What this demonstrates

- Relational modeling, normalization, constraints, composite foreign keys, views, indexes, and transactions.
- Authentication/session design, organization-level authorization, and role-specific workflows.
- Whole-file CSV validation, deduplication, and atomic import behavior.
- Financial guardrails for budget allocations and disbursement records.
- Clear documentation of trust boundaries and limitations.

## Learning and relevance

The design connects data integrity to real workflow decisions: who can approve a response, which award may fund it, what spending is allowed, and when a funder needs a report. The strongest lesson is that UI permissions are only a convenience; enforcement belongs in the API and database.

## Current boundary and roadmap

The sample dataset is fictional and the app is not production-cleared. Before any real pilot, the project needs organization interviews, onboarding/recovery/MFA, independent authorization review, a privacy and threat review, audited backups, deployment hardening, and operational ownership. Possible follow-on work includes multi-period reports, richer award closeout, source document retention policies, and read-only import of verified external transaction events.

# Product brief

## Product idea

**ReliefTrail ResponseHub** is a portfolio application that models an internal relief grants workflow. It connects response records with funders, restricted awards, budget lines, reported disbursements, donor reporting deadlines, human review, and organization-level access.

The application is a separate companion to the [ReliefTrail Blockchain prototype](https://github.com/tanay-gaykwad/relieftrail-blockchain). ResponseHub demonstrates relational records and operational roles; the Solidity repository demonstrates a narrow on-chain payout rule. They share a story but are not integrated. The blockchain contract does not send data into ResponseHub.

The workflow is inspired by common grants-management patterns, but it has not been validated with actual NGO finance teams. It is not a fundraiser, payment processor, beneficiary case-management system, or replacement for established platforms.

## User workflow

1. A member signs into an organization-scoped workspace.
2. Staff review response records and the funding activity attached to them.
3. An editor creates a response draft. An organization administrator approves or closes it.
4. An editor creates an award, captures its restriction and amount, allocates budget to an approved response, and creates a reporting milestone.
5. An editor records a disbursement against a budget line. API checks and database triggers prevent over-budget entries.
6. Editors submit report summaries; reviewers or administrators accept or return them.
7. Members review flags and action history. Editors may import a validated partner CSV; duplicates are skipped and the batch is written atomically.

## Objectives demonstrated

- Relational normalization, keys, constraints, indexes, composite foreign keys, views, and triggers.
- Transactions spanning award, allocation, reporting milestone, and audit actions.
- Typed frontend/API boundaries and server-enforced role authorization.
- Cookie-based revocable sessions, CSRF checks, login throttling, and tenant scoping.
- Whole-file CSV validation, deduplication, and import status history.
- Documentation and tests that distinguish database/on-chain facts from real-world evidence.

## Trust and safety boundaries

- All people, organizations, amounts, and records are fictional.
- Do not enter beneficiary names, addresses, health information, donor bank details, payment credentials, or private evidence.
- Funding rows show reported activity; they do not prove that a payment settled or aid was received.
- An audit event is a review aid, not a tamper-proof record against the database owner.
- AI may later suggest spreadsheet mappings or source-linked report drafts, but a person must review outputs. It must not decide eligibility, approve aid, move money, or publish claims automatically.
- Never deploy with demo accounts or secrets. Any real pilot requires user research, privacy and security reviews, proper hosting/backups, and an accountable operations owner.

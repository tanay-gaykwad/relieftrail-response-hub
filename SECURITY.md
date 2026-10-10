# Security notes

## Scope

ResponseHub is an educational portfolio application that uses fictional records. It is not approved for real NGO operations and should not store beneficiary, donor, banking, payment, or other sensitive information. The controls below demonstrate common server-side patterns; they are not a security certification.

## Controls implemented

- Passwords are hashed with Argon2id. Legacy PBKDF2 hashes are verified and upgraded at sign-in.
- Sessions use high-entropy random values in `HttpOnly`, `SameSite=Strict` cookies. Only a SHA-256 verifier is stored in PostgreSQL; sessions expire and can be revoked at logout.
- Write requests require a double-submit CSRF token. The API allows credentials only from configured frontend origins.
- Login failures are throttled by an HMAC of normalized email and client address; raw addresses are not stored in the throttle table.
- Every protected request checks that the account remains active and reloads organization memberships. API handlers enforce roles and tenant scope.
- Prepared SQL parameters are used for user-supplied values. CSV input is size/row limited, validated as a whole, then written in one transaction.
- PostgreSQL constraints, composite foreign keys, and triggers enforce organization boundaries, append-only audit events, award allocation limits, and spending ceilings.
- Production mode refuses a missing or placeholder secret, uses secure cookie attributes, enables HSTS, and disables interactive API documentation.

## Important limits

This repository has no MFA, account invitation or recovery workflow, password reset, managed identity provider, independent security audit, threat-model sign-off, backup/restore exercise, incident response process, or production monitoring. The demo accounts and passwords are public in the repository by design. Do not deploy with them. The local Compose configuration is intentionally for a local demonstration.

The demo password throttle is database-backed and suitable only for a small demonstration. A public service should use a reviewed rate-limiting strategy, alerting, operational controls, and abuse testing. Browser and database tests in CI do not replace penetration testing or a privacy/legal review.

## Before any real deployment

1. Remove public demo accounts and implement secure invitations, recovery, MFA, and account lifecycle controls.
2. Use a managed secrets store, HTTPS-only deployment, managed database, private networking, tested encrypted backups, and retention rules.
3. Complete a threat model and independent security review, including authorization tests across every endpoint and tenant.
4. Define audit retention, privacy notices, incident response, access review, and data deletion procedures with the organization.
5. Run dependency, static analysis, and dynamic security scans and address findings before handling sensitive information.

## Reporting a concern

Please do not include real personal data in public issues. Contact the repository owner through the GitHub profile with a concise description and reproduction steps. This is a portfolio project and does not promise a monitored security response service.

# Product and engineering review

This review describes the current portfolio demo and the improvements made in October 2026. It is based on the running screens and the source in this repository. It is not a penetration test, production-readiness certification, or endorsement for storing real aid-recipient or payment data.

## What the current product is

ResponseHub is an internal workspace for a relief organization's staff. It links response records to restricted awards, budget allocations, reported contributions and spending, reporting deadlines, reconciliation flags, and an activity history. Its purpose is to make the administrative record easier to review. It does not prove that a payment cleared or that aid reached a person.

The current screens cover the main staff workflow: review or edit response records, create awards, record spending, submit and review reports, import reported funding rows from CSV, resolve flags, and inspect activity. The screenshots in `screenshots/` should be captured from this running build before being described as verified product screenshots.

## Improvements completed in this pass

1. **Added account settings.** A user can reach “My profile” from the account controls and update their display name. Email remains read-only because there is no verified email-change workflow.
2. **Added password changes.** A user must provide the current password and a new passphrase of at least 15 characters. The API hashes it with Argon2id, revokes prior active sessions, and issues a fresh session to the current browser.
3. **Made demo account initialization non-destructive.** Restarting the API no longer resets a user's changed password, display name, disabled status, or organization role. Existing demo accounts are left as-is; only missing demo accounts and memberships are added.
4. **Clarified the donation boundary.** Contributions are records reported by staff or imported from CSV. There is no public donor page, payment gateway, receipt flow, or movement of money. This is intentional for a grants and response-funding workspace.

## Remaining work, ordered by importance

### Before any real organization uses it

- Add administrator-issued invitations, verified email ownership, password recovery, MFA, and account deactivation/revocation controls.
- Review every API route with authorization tests, including cross-organization access and concurrent role changes; then commission an independent security review.
- Add database migrations instead of relying on first-start SQL scripts. Define retention, restore-tested encrypted backups, monitoring, alerting, and incident response.
- Deploy with TLS, private database networking, managed secrets, non-demo account provisioning, and no publicly accessible demo credentials. Keep the database inaccessible from browsers.
- Have the intended organization review its privacy, donor-data, financial-control, and legal requirements before importing any real records.

### Product improvements for the portfolio version

- Add invitation and onboarding screens so an administrator can add teammates instead of only changing roles on preloaded accounts.
- Add a clear organization switcher; the current dashboard combines memberships while some creation forms use the first organization.
- Improve audit events with a stable actor user ID and before/after values where appropriate. The present log labels the actor by name and records a limited set of actions.
- Add a user-facing record detail page, pagination for large lists, and clearer import history with row-level validation feedback.
- Replace illustrative preview assets with screenshots captured from this exact running build and add a short narrated demo.

### If a public donation experience is desired

Treat it as a separate, explicitly scoped module. A real donation flow needs a payment provider's hosted checkout, signed webhook verification, idempotent transaction handling, donor receipts and consent, refund/chargeback workflows, and a privacy review. Payment card details should never be stored by this app. Until that work exists, do not present ResponseHub as accepting donations.

## Evidence and limits

The screenshots supplied by the project owner show the Responses, Awards & budgets, Reporting calendar, Funding records, Review queue, and Activity log screens. They confirm the intended internal-workspace design, but do not by themselves verify role behavior, database persistence, or security. The current project documentation identifies missing MFA, invitation/recovery, formal review, tested backups, and production operations. Those gaps remain open after this pass.


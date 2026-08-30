# Spec 017: Add Legal Policies And Terms Acceptance

## Overview

Add a public Terms of Service and Privacy Notice grounded in BeerRunJPN's actual operation, then require versioned agreement to the Terms when a new account is created. Existing operator-owned accounts continue without a retroactive agreement gate. The Privacy Notice is informational and must not be presented as blanket GDPR consent. This feature is a practical compliance baseline, not a guarantee of compliance or a substitute for advice from a qualified Dutch/EU lawyer.

## Goals

- Give visitors clear, always-available information about service rules and personal-data processing before signup.
- Record explicit, versioned Terms agreement for each new account without fabricating acceptance for existing users.
- Preserve login, authenticated features, and account deletion for existing accounts without an acceptance interstitial.
- Keep the legal text accurate for a free, currently invite-code-gated, self-hosted Netherlands service with no ads, analytics, payment processing, or backups.
- Minimize the operator's public personal information while still publishing the controller's real identity and a working contact email.

---

## Feature 1: Public Legal Documents

**Who & why:** Visitors and users need to understand who operates BeerRunJPN, how the service may be used, and how their data is handled before they submit account or trip data. The operator needs policy text that reflects the deployed app rather than a generic template with inaccurate claims.

### Functional Requirements

#### FR-1.1: Public Terms Of Service

`GET /terms` must return a directly addressable HTML Terms of Service page without requiring authentication or JavaScript. It must identify the current Terms version and effective date; describe the free service, eligibility, account responsibilities, user content and visibility, the source code's MIT License, acceptable use, human content moderation, reporting illegal or prohibited content, service changes, termination, availability, lack of backups, data-loss risk, liability subject to mandatory law, Netherlands governing law, and the operator contact.

The Terms must explain that account creation is optional, users retain ownership of their content while granting the limited permission needed to store, process, resize, and display it through the selected beer run, and users can delete entries or permanently delete their account from Account settings. The deletion wording must accurately disclose the owned-run prerequisite and clarify that deleting an account does not delete other users' accounts, entries, or photos. The Terms must not waive non-excludable EU consumer or data-protection rights.

**Verify:** An unauthenticated request to `/terms` returns 200 with every required section, the active version/effective date, and the configured controller identity and contact email safely escaped.

#### FR-1.2: Public Privacy Notice

`GET /privacy` must return a directly addressable HTML Privacy Notice without requiring authentication or JavaScript. It must describe the controller, categories and sources of data, purposes, Article 6 lawful bases, public/private run visibility, recipients, local Netherlands storage, device storage, retention, no-backup consequence, security, data-subject rights, how to submit a request, the absence of ads/analytics/automated decision-making, and policy changes.

The notice must distinguish locally stored BeerRunJPN data from browser requests to current external asset and map services, including Google Fonts, unpkg, and OpenStreetMap tile servers. It must not claim that no third party receives any request metadata while those integrations remain present. It must make clear that account creation and optional entry, location, and photo submissions are voluntary without describing every processing activity as consent. It must accurately describe self-service entry/account deletion, the owned-run prerequisite, and that deleting an account does not delete other users' accounts, entries, or photos.

**Verify:** An unauthenticated request to `/privacy` returns 200 with the required processing disclosures, no-backup disclosure, and configured controller identity/contact. Each public legal document shows the configured name and email only in its final contact section.

#### FR-1.3: Real Controller Identity With Minimal Public Contact Data

The application must require `LEGAL_CONTROLLER_NAME` and `LEGAL_CONTACT_EMAIL` through private environment configuration before startup. A natural-person controller must use their real full name; an organisation may use its registered legal name. A public postal address is not required by this implementation, but the policy and operator documentation must warn that other laws or a changed commercial/hosting model may require additional provider information.

Tracked examples must use rejected placeholders. Invalid, blank, padded, or placeholder configuration must stop application startup with a safe message that never echoes submitted private values.

**Verify:** Startup succeeds with a plausible controller name and email, fails safely for each missing/placeholder/malformed value, and tracked files contain no real operator identity or email.

#### FR-1.4: Persistent Legal Navigation

The main page must expose Terms and Privacy links while logged out and logged in. Signup UI must link to both documents in a way that does not clear entered form data.

**Verify:** Desktop and 390x844 browser checks can open both documents from the public page and signup form without losing signup input or requiring authentication.

### Architectural Requirements

#### AR-1.1: Lightweight Server Rendering

Legal pages must use the existing FastAPI/static-template architecture in `main.py`, `templates/`, and `static/css/` without adding Jinja, a frontend build step, or a policy-content dependency. Dynamic controller values must be HTML-escaped before insertion into tracked templates.

#### AR-1.2: One Code-Owned Policy Version Source

The current Terms version, Privacy Notice version, and effective date must be defined together in one code-owned legal module. The version reported by APIs, rendered by documents, required at signup, and stored in acceptance evidence must not drift.

---

## Feature 2: Explicit Signup Agreement

**Who & why:** A new account holder must see the governing documents and make an affirmative choice before account creation. The operator needs durable evidence of the exact Terms version agreed to without treating that agreement as consent to unrelated personal-data processing.

### Functional Requirements

#### FR-2.1: Unchecked Signup Agreement

The signup form must include an unchecked control worded as agreement to the Terms and acknowledgement of the Privacy Notice. The wording must not say that the user consents to all data processing. Client validation must prevent submission until it is checked, while server validation remains authoritative.

**Verify:** A fresh signup form starts unchecked, an unchecked submit shows a readable validation error without sending a request, and switching/closing the auth modal resets the control.

#### FR-2.2: Server-Enforced Current Version

`POST /api/signup` must require a strict boolean Terms agreement and the exact current Terms version. Missing, false, non-boolean, stale, or unknown values must return a sanitized validation failure and create neither a user nor an acceptance record.

**Verify:** Focused API tests cover every invalid shape/version and prove that only an explicit true agreement to the server's active version creates the account.

#### FR-2.3: Atomic Signup Evidence

Successful signup must create the user and the versioned Terms acceptance record in the same database transaction before returning a bearer token. If either write or token creation fails, neither record may remain.

**Verify:** Success stores one UTC acceptance timestamp for the active version, and injected failures leave no partial user or acceptance row.

#### FR-2.4: Public Version Metadata

An unauthenticated legal metadata endpoint must provide the active Terms version, Privacy Notice version, effective date, and public document URLs so the static frontend never hardcodes a version separately from the backend.

**Verify:** The public endpoint returns only non-sensitive policy metadata and the signup request uses its current Terms version.

### Architectural Requirements

#### AR-2.1: Append-Only Acceptance History

Acceptance evidence must use a separate `terms_acceptances` table keyed by user and Terms version, with a UTC timestamp and a foreign key to `users`. It must not add acceptance columns to `users`, which is rebuilt by migration 007. Model relationships must remove a user's acceptance history when the user is deleted.

#### AR-2.2: Reserved Migration Ordering

The merged migration runner must register `007_add_user_auth_subject` before `008_add_terms_acceptances`. Migration 008 must apply cleanly after 007 while remaining compatible with a database that recorded 008 before a later ID-preserving 007 rebuild during parallel feature development. Compatibility must be documented and tested.

---

## Feature 3: Existing-Account Compatibility

**Who & why:** The existing accounts belong to the operator and do not need retroactive acceptance logic. They must continue to log in, use authenticated features, and delete their accounts without fabricated agreement records or a new interstitial.

### Functional Requirements

#### FR-3.1: No Retroactive Acceptance Gate

Valid credentials for an existing account must continue to return a bearer token and all otherwise-authorized routes must continue to work when no Terms-acceptance row exists. The application must not show a mandatory acceptance interstitial, invent a historical acceptance record, or add a Terms-specific server authorization gate. `/api/me` must keep its existing `{username, id}` response contract.

**Verify:** An existing account with no acceptance row can log in, list its visible beer runs, open Account settings, and receive the unchanged `/api/me` response.

#### FR-3.2: Account Deletion Includes Acceptance Evidence

The existing self-service deletion flow must remain available through Account settings. Deleting a user must cascade any Terms-acceptance rows for that user while preserving another user's acceptance rows, entries, and photos.

**Verify:** Account-deletion tests prove the caller's acceptance rows are removed and another user's row remains.

### Architectural Requirements

#### AR-3.1: Signup-Only Acceptance Boundary

Terms validation and persistence belong in the signup transaction. `auth.get_current_user`, `permissions.py`, authenticated beer-run routes, invite routes, login, stored-session restoration, and account deletion must retain their existing authorization behavior.

#### AR-3.2: Module Boundaries And Cache Busting

Network calls belong in `static/js/modules/api.js`, auth form state in `static/js/modules/auth.js` and `signup.js`, and orchestration in `static/js/app.js`. Every changed deployed CSS/JavaScript URL and duplicate module import must receive a cache-buster update.

---

## Feature 4: Operator Compliance Notes

**Who & why:** Publishing policies and collecting agreement does not by itself make a service GDPR-compliant. The operator needs a concise runbook for configuration, data requests, incidents, and changes that invalidate the current assumptions.

### Functional Requirements

#### FR-4.1: Privacy Operations Runbook

A tracked operator document must explain how to configure the real controller identity/email, apply migration 008 safely, keep HTTPS and secrets in place, answer access/correction/erasure/portability/objection requests, assess and report personal-data breaches, maintain a basic record of processing, and review policy versions when practices change.

It must highlight the current absence of backups as a resilience/data-loss risk and require reassessment before removing invite codes, adding ads/analytics/payments/backups, changing hosting, adding processors, or targeting children.

**Verify:** The runbook includes every listed operational trigger and clearly separates current confirmed facts from future review items.

#### FR-4.2: Accurate Deployment Documentation

`.env.example` and `README.md` must document the required legal configuration, policy routes, migration step, acceptance behavior, and the fact that real controller details belong only in private deployment configuration. Documentation must not claim this feature alone guarantees legal compliance.

**Verify:** A clean tracked checkout contains only rejected placeholders and enough deployment instructions to start the app after setting legal identity values and applying migrations.

### Architectural Requirements

#### AR-4.1: No Live Runtime Mutation

Implementation and verification must use disposable databases. The feature may add migration 008 and document the production command, but must not apply it to `boozerun.db` or modify live uploads, users, entries, or caches.

---

## Data Requirements

- Add `terms_acceptances` with `user_id`, non-empty `terms_version`, and timezone-aware UTC `accepted_at` semantics.
- Enforce uniqueness for each `(user_id, terms_version)` pair and index current-user/current-version lookup.
- Existing users receive no rows during migration, and that absence does not restrict their accounts.
- A newly created user receives one row for the Terms version accepted during signup.
- Deleting a user must delete that user's acceptance rows without affecting other users.
- Do not store IP addresses, user agents, checkbox wording, or privacy-notice “consent” as acceptance evidence.

## Integration Points

- `legal.py` (new): policy versions, configuration validation, safe document rendering, and acceptance helpers.
- `main.py`: startup validation and public legal page/metadata routes.
- `models.py`, `schemas.py`, `migrations/runner.py`, `migrations/versions/008_add_terms_acceptances.py`: persistence and contracts.
- `auth_routes.py`: strict signup agreement and atomic acceptance persistence; existing authentication and deletion routes remain ungated.
- `templates/index.html`, new legal templates, `static/css/`, `static/js/app.js`, `static/js/modules/api.js`, `auth.js`, and `signup.js`: browser experience.
- `tests/test_auth.py`, `tests/test_account_deletion.py`, `tests/test_migrations.py`, and new legal-page/migration tests: automated verification.
- `.env.example`, `README.md`, and `docs/privacy-operations.md`: deployment and operator obligations.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|---------------------|
| Spec 001: Add Database Migrations | **Extends** — adds reserved migration 008 and compatibility requirements | AR-2.1, AR-2.2, AR-4.1 |
| Spec 004: Harden Auth Tokens | **Preserves** — bearer resolution and existing-session behavior remain unchanged | FR-3.1, AR-3.1 |
| Spec 005: Add Signup API | **Modifies** — requires atomic explicit Terms agreement during signup | FR-2.1 through FR-2.3 |
| Spec 010: Update Frontend Auth And Signup | **Modifies** — adds policy links and signup agreement without changing existing login/session behavior | FR-1.4, FR-2.1, FR-3.1 |
| Spec 013: Add Invite UI And Accept Flow | **Preserves** — existing accounts and invite continuation receive no retroactive Terms gate | FR-3.1, AR-3.1 |
| Spec 016: Delete Account And Personal Data | **Extends** — merged migration 007 precedes 008 and deletion must remove acceptance evidence | AR-2.1, AR-2.2, FR-3.2, Data Requirements |

## Constraints

- Remain a compact FastAPI, SQLite, vanilla-JavaScript app with no new frontend build system or policy-content framework.
- Use `2026-08-30` as the initial Terms version, Privacy Notice version, and effective date.
- Treat Terms agreement as contractual assent, not GDPR consent for all processing.
- Assume a free Netherlands-hosted service that currently uses signup codes, has no ads/analytics/payments/backups, and does not use automated decision-making.
- Restrict account creation/use to adults aged 18 or older because the service records alcohol consumption; revisit this with counsel if the intended audience changes.
- The tracked legal text is an operator-editable baseline and must receive professional review before broad public launch.
- Preserve public BeerRunJPN behavior and stable API shapes except for the explicitly changed signup contract and new legal endpoints/errors.

## Out of Scope

- Providing legal advice, certifying GDPR/DSA/ePrivacy compliance, or replacing qualified Dutch/EU counsel.
- Adding self-service data export or rectification; account deletion is already supplied by Spec 016 and is documented and integration-tested here.
- Retroactively collecting Terms agreement from existing accounts or blocking them behind a Terms-version gate.
- Adding a cookie banner while the app uses only essential device storage and no tracking/analytics; this must be revisited before adding non-essential storage or tracking.
- Vendoring Google Fonts, Leaflet, marker-cluster assets, or OpenStreetMap tiles; current external requests are disclosed instead.
- Adding backups, a processor, analytics, ads, payment handling, age verification, parental-consent flows, or multilingual legal documents.
- Publishing a postal address. The runbook must flag reassessment if commercial activity, DSA status, or other provider-information rules require it.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Features 1-4 define public documents, signup agreement, existing-account compatibility, deletion integration, and operator documentation with a Verify line for every FR.
- [x] **Testing strategy** — Every FR includes an acceptance condition; Integration Points and AR-4.1 require focused tests, the full suite, browser QA, and disposable data.
- [x] **Existing patterns** — AR-1.1 and AR-3.2 preserve FastAPI/static templates and established frontend module boundaries; Related Specs identifies modified flows.
- [x] **Dependencies** — AR-1.1 forbids new policy/template dependencies; external browser services are disclosed and vendoring is explicitly out of scope.
- [x] **Architecture & interfaces** — AR-2.1, AR-2.2, AR-3.1, AR-3.2, Data Requirements, and Integration Points define persistence, API, auth, migration, deletion, and UI boundaries.
- [x] **Error handling & failure modes** — FR-1.3, FR-2.2, and FR-2.3 cover invalid config, strict validation, stale versions, rollback, and safe public errors.
- [x] **Security review** — FR-1.3, FR-2.2, FR-3.1, Data Requirements, and Constraints address escaping, secret-safe validation, data minimization, and unchanged bearer boundaries.
- [x] **Performance impact** — Acceptance adds one indexed current-user/version lookup per identity-derived request; no polling, build step, or heavy dependency is introduced.
- [x] **Rollout & migration** — AR-2.2, AR-4.1, FR-4.1, and FR-4.2 define reserved ordering, compatibility, production instructions, and no live migration during implementation.
- [x] **Assumptions & risks** — Constraints and Out of Scope record the confirmed deployment facts, 18+ assumption, no-backup risk, merged Spec 016 behavior, signup-only acceptance boundary, external services, and professional-review boundary.

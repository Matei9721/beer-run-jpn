# Spec 018: Rebrand and Run-Scoped Wrapped

## Overview

Rename the reusable application brand from BeerRunJPN/BoozeRunJpn to BeerRun while preserving `BeerRunJPN` as the immutable identity of the existing canonical public run. Make Wrapped an explicit per-run capability so navigation and recap data are available only for runs with a generated, run-matched Wrapped artifact.

## Goals

- Present the multi-run service consistently as BeerRun.
- Preserve all behavior that depends on the canonical `BeerRunJPN` run name.
- Enable Wrapped only for the existing BeerRunJPN run after migration.
- Prevent another run from viewing or being included in BeerRunJPN's recap.

---

## Feature 1: Generic BeerRun Product Brand

**Who & why:** People can now create and join their own beer runs, so the service should no longer present one Japan trip as the identity of the whole application. The existing trip and its recap must retain their recognizable BeerRunJPN name.

### Functional Requirements

#### FR-1.1: Rebrand the application shell

User-visible application titles, mastheads, general help, invite/share copy, and legal-policy product references must use `BeerRun` (or `BEERRUN` in the existing uppercase visual treatment).

**Verify:** The main page, invitation/share copy, instructions, Terms, and Privacy Notice identify the service as BeerRun and no longer identify the service itself as BeerRunJPN.

#### FR-1.2: Preserve the canonical run identity

`BeerRunJPN` must remain the existing run's stored name, public fallback lookup, deletion protection, historical migration identifier, and authored Wrapped title/content. Compatibility storage keys and runtime file/environment names are not part of the visual rebrand.

**Verify:** Existing default-run, access, and deletion tests continue to resolve and protect the run named `BeerRunJPN`.

### Architectural Requirements

#### AR-1.1: Keep the lightweight frontend

Rebranding must use the existing templates and vanilla JavaScript modules without introducing a frontend build step or new dependency.

---

## Feature 2: Per-Run Wrapped Availability

**Who & why:** Participants should see a recap only when their selected run has one. A participant in another run must not be offered, or be able to retrieve, the BeerRunJPN recap.

### Functional Requirements

#### FR-2.1: Persist Wrapped availability

Each beer run must have a non-null boolean `has_wrapped` value that defaults to false. The migration must enable it only for the case-insensitive canonical `BeerRunJPN` row; existing and future other runs remain disabled unless deliberately enabled later.

**Verify:** A migrated database reports `has_wrapped = true` for BeerRunJPN, false for other existing runs, and false for newly created runs.

#### FR-2.2: Expose availability in beer-run responses

Every API response using the shared beer-run response shape must include `has_wrapped`, allowing the selected-run UI to make one consistent decision.

**Verify:** Create, detail, list, search, and update beer-run responses include the correct boolean.

#### FR-2.3: Show Wrapped navigation only for the selected eligible run

The Wrapped tab and completion notice must be hidden and removed from keyboard navigation unless the current selected run has `has_wrapped = true`. Eligible links must include the immutable run ID, and notice dismissal must be scoped by run ID.

**Verify:** Selecting BeerRunJPN shows run-scoped Wrapped links; selecting an unflagged run or clearing selection hides them; switching back restores them.

#### FR-2.4: Enforce run access and availability on recap data

Wrapped data retrieval must be scoped by beer-run ID, use the existing public/member read authorization boundary, and return a non-disclosing 404 for a missing, inaccessible, unflagged, missing-artifact, or mismatched-artifact run. UI hiding alone is not sufficient.

**Verify:** BeerRunJPN can retrieve only its matched recap, an unflagged public run receives 404, and an inaccessible private run does not reveal recap availability.

#### FR-2.5: Scope Wrapped generation to one run

The generator must require or resolve a single beer-run ID, filter entries to that run, record the run ID in artifact metadata, and write/read a run-specific artifact. Entries from other runs must never contribute.

**Verify:** A fixture containing entries in two runs generates totals and slides only from the requested run and the API rejects an artifact whose recorded run ID differs.

#### FR-2.6: Handle incomplete Wrapped URLs gracefully

The generic Wrapped shell must show its existing unavailable/error state when no valid run ID is supplied or when recap retrieval fails; it must not fall back to another run's data.

**Verify:** Opening `/wrapped` without a run ID does not load BeerRunJPN data and opening `/wrapped?run=<eligible-id>` loads the eligible recap.

### Architectural Requirements

#### AR-2.1: Follow existing model and response boundaries

The flag belongs on `models.BeerRun`, in `schemas.BeerRunResponse`, and in both response builders in `beer_run_routes.py`. Selected-run presentation belongs in `static/js/app.js` through the existing `setCurrentRun()` transition.

#### AR-2.2: Use a forward-only safe migration

Migration 009 must follow `migrations/runner.py` ordering, be idempotent, safely baseline a complete compatible pre-existing column, and reject partial or incompatible schema without recording success. It must never apply automatically to the protected live `boozerun.db` during development.

#### AR-2.3: Preserve authorization semantics

The run-scoped Wrapped API must reuse `permissions.authorize_public_read` so public runs remain anonymously readable and private runs require membership without leaking their existence.

#### AR-2.4: Update static cache versions

Any changed deployed JavaScript or CSS reference must receive the repository-required cache-busting version update.

---

## Data Requirements

- Add `beer_runs.has_wrapped` as a checked SQLite boolean, `NOT NULL`, default `0`.
- Backfill only `BeerRunJPN` case-insensitively to `1`.
- Store generated artifacts by immutable run ID and include that ID in artifact metadata.
- Preserve the tracked legacy artifact only as migration/source material if needed; no request may use it without an explicit run match.

## Integration Points

- `models.py`, `schemas.py`, and `beer_run_routes.py` for API data.
- `migrations/versions/009_add_beer_run_wrapped_flag.py` and `migrations/runner.py` for schema rollout.
- `static/js/app.js` and `templates/index.html` for selected-run presentation.
- `main.py`, `static/js/wrapped.js`, and `scripts/build_wrapped_data.py` for scoped recap delivery and generation.
- `templates/privacy.html`, `templates/terms.html`, and share/invite UI for product branding.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|---------------------|
| Spec 002: Add Beer Run Schema | **Extends** — adds Wrapped availability to beer runs | FR-2.1, AR-2.1 |
| Spec 003: Backfill Existing Trip | **Modifies** — preserves BeerRunJPN as the canonical migrated trip and enables its recap | FR-1.2, FR-2.1 |
| Spec 006: Add Beer Run CRUD API | **Extends** — adds availability to shared run responses | FR-2.2 |
| Spec 007: Centralize Beer Run Authorization | **References** — reuses public/member read authorization | FR-2.4, AR-2.3 |
| Spec 011: Add Beer Run Selector UI | **Extends** — conditions navigation on selected-run metadata | FR-2.3 |

## Constraints

- Do not mutate `boozerun.db`, uploads, user data, or local caches.
- Do not rename the canonical BeerRunJPN database row.
- Do not add a framework, build system, or third-party dependency.
- Preserve current mobile navigation and accessibility behavior.

## Out of Scope

- An owner UI or API for generating, enabling, disabling, or deleting Wrapped.
- Generic theming or authoring of distinct recap designs for future runs.
- Renaming repository folders, database files, environment variables, package import paths, or compatibility localStorage keys.
- Rewriting the existing BeerRunJPN-specific Wrapped narrative or artwork.

## Error Handling and Rollout

- Unavailable or inaccessible recap data returns 404 without disclosing private-run state.
- Invalid/missing run IDs and artifact mismatches render the existing Wrapped unavailable state.
- The migration is forward-only; rollback requires restoring the pre-migration database backup through the existing operational process.
- Deployment requires applying migration 009 before starting code that selects `has_wrapped`, then generating the canonical run-specific artifact.

## Assumptions and Risks

- `BeerRunJPN` remains the unique canonical public fallback for this release.
- Only BeerRunJPN has a completed recap at rollout.
- The legacy global artifact may contain mixed-run data if regenerated after multi-run support; implementation must regenerate or transform it through run-scoped generation before serving it.
- Future enablement of another run requires its own run-matched generated artifact; flipping the flag alone must still yield 404 if that artifact is absent.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Goals, FR-1.1 through FR-2.6, Constraints, and Out of Scope define the shipping boundary.
- [x] **Testing strategy** — Every FR has an explicit Verify condition covering backend, frontend, migration, and generation behavior.
- [x] **Existing patterns** — AR-2.1 through AR-2.4 identify the current model, response, selection, authorization, migration, and cache patterns.
- [x] **Dependencies** — AR-1.1 and Constraints require the current dependency-free frontend and no new libraries.
- [x] **Architecture & interfaces** — Data Requirements and Integration Points define schema, API, UI, and artifact boundaries.
- [x] **Error handling & failure modes** — FR-2.4, FR-2.6, and Error Handling and Rollout cover unavailable, inaccessible, invalid, and mismatched cases.
- [x] **Security review** — FR-2.4 and AR-2.3 require existing authorization and non-disclosing errors.
- [x] **Performance impact** — Generation filters a single run and request-time work is one indexed run lookup plus one artifact read; no unbounded new request work is introduced.
- [x] **Rollout & migration** — AR-2.2 and Error Handling and Rollout define safe migration, ordering, regeneration, and rollback expectations.
- [x] **Assumptions & risks** — Assumptions and Risks records canonical-run, artifact, and future-enablement constraints.

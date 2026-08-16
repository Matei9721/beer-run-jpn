# Research: Backfill Existing Trip

## Decision: Use The Existing Migration Runner For Backfill

**Rationale**: The project already validates startup readiness through the ordered in-repo migration runner, and Task 02 intentionally left historical `beer_run_id` assignment for Task 03. Adding `003_backfill_existing_trip` keeps fresh databases, upgraded databases, and local retry behavior on one path.

**Alternatives considered**:

- One-off script only: rejected because startup readiness would not know whether the backfill had been applied.
- Manual SQL instructions: rejected because it is harder to test and retry safely.
- New migration framework: rejected because Release 1 explicitly uses the lightweight local runner.

## Decision: Preserve Existing UI With An Implicit Default Run

**Rationale**: The current app is a single-trip experience. Until a later feature adds run selection, existing entry list, leaderboard, public views, and entry creation should behave as if the global dataset still exists, with `BeerRunJPN` as the implicit scope.

**Alternatives considered**:

- Add a run selector now: rejected as broader than Task 03 and likely to change the UI.
- Return all runs globally: rejected because it weakens the new run-scoped data model and could expose future private runs.
- Require clients to send a run id now: rejected because it would break current UI behavior.

## Decision: Keep API Response Shapes Stable

**Rationale**: Existing frontend consumers expect entry and leaderboard payloads without run-selection requirements. This task is a backend/data migration bridge, so compatibility matters more than exposing new beer-run fields.

**Alternatives considered**:

- Add `beer_run_id` or run name to all current responses: deferred unless implementation needs it, because it could require frontend consumer updates and is not needed to preserve current behavior.
- Introduce new versioned routes: rejected as unnecessary for a single default-run bridge.

## Decision: Handle Tamei Ownership Without Creating Accounts

**Rationale**: The real dataset is expected to contain `Tamei`, but test or partial databases may not. Creating a user during data migration would alter auth/user state unexpectedly. The backfill should clearly report missing owner state while still preserving historical entries where possible.

**Alternatives considered**:

- Silently create `Tamei`: rejected because it invents credentials and identity data.
- Promote the first user automatically: rejected because ownership would become data-order dependent.
- Ignore missing owner entirely: rejected because the spec requires operator feedback.

## Decision: Retry By Upsert-Like Checks, Not Data Reset

**Rationale**: Local retry safety requires reusing existing `BeerRunJPN`, preserving existing valid memberships, and filling missing assignments without deleting or recreating data.

**Alternatives considered**:

- Delete and recreate the default run: rejected because it risks losing relationships and violates runtime data protection.
- Blind insert on every run: rejected because it creates duplicates or constraint failures instead of retry safety.

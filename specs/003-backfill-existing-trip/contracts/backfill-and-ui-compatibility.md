# Contract: Backfill And UI Compatibility

## Migration Contract

### Apply Backfill

**Actor**: Local operator or app setup process running the existing migration command.

**Preconditions**:

- The database has the schema from `002_add_beer_run_schema`.
- Existing user and entry rows may or may not already have default run data from a partial attempt.

**Postconditions**:

- One beer-run named `BeerRunJPN` exists.
- `BeerRunJPN` is public/readable.
- Every existing user has one BeerRunJPN membership.
- Existing user `Tamei`, when present, has owner role for BeerRunJPN.
- Existing unassigned entries have BeerRunJPN as their run.
- Migration history records the backfill version only after successful completion.

**Retry behavior**:

- Re-running does not create duplicate BeerRunJPN rows.
- Re-running does not create duplicate memberships.
- Re-running does not change leaderboard totals.
- Re-running preserves entries already assigned to other runs.

**Failure behavior**:

- If ownership cannot be satisfied because `Tamei` is absent, the operator receives clear feedback.
- Runtime files are not deleted, reset, or replaced.

## App Compatibility Contract

### `POST /api/entries`

**Current behavior to preserve**:

- Requires the existing authenticated user.
- Accepts the current form fields.
- Saves uploaded images using the existing behavior.
- Returns the current success payload shape.

**New default-run behavior**:

- The saved entry belongs to BeerRunJPN automatically.
- The client does not need to send a run id or choose a run.

### `GET /api/entries`

**Current behavior to preserve**:

- Returns the existing entry payload shape.
- Supports the existing optional username filter.
- Orders entries newest first.

**New default-run behavior**:

- Results represent BeerRunJPN entries for the current single-trip UI.
- Existing frontend consumers do not need to pass a run id.

### `GET /api/leaderboard`

**Current behavior to preserve**:

- Returns the existing leaderboard payload shape.
- Sorts users by total alcohol.

**New default-run behavior**:

- Totals are computed from BeerRunJPN entries.
- After backfill, totals match the previous global totals for the same data.

### `POST /token` And `GET /api/me`

**Current behavior to preserve**:

- Existing credentials still authenticate.
- Token response shape is unchanged.
- Current user response shape is unchanged.

**New default-run behavior**:

- None. Authentication behavior is intentionally unchanged by this task.

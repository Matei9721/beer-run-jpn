# Data Model: Add Database Migrations

## Migration

Represents one ordered schema change in the local migration sequence.

**Fields**:

- `id`: Stable migration identifier, such as `001_initial_schema`.
- `description`: Human-readable summary of what the migration establishes or changes.
- `order`: Numeric ordering value used to apply migrations deterministically.
- `apply`: Operation that changes the target database when the migration has not yet been applied.
- `baseline_check`: Optional operation used by the initial migration to recognize an existing current-schema database without recreating data.

**Validation rules**:

- Migration identifiers must be unique.
- Migration order must be deterministic.
- A migration must be recorded only after it completes successfully or is safely baselined.

## Applied Migration Record

Represents a migration that has completed successfully for a specific database.

**Fields**:

- `version`: Migration identifier.
- `applied_at`: Timestamp recorded when the migration is applied or baselined.

**Relationships**:

- Each record corresponds to one `Migration`.
- Records live inside the same SQLite database they describe.

**Validation rules**:

- `version` must be unique.
- Missing records for required migrations mean the database is not ready unless the baseline check can safely adopt the existing schema.

## User

Existing account entity that must be preserved through migration.

**Baseline fields**:

- `id`
- `username`
- `hashed_password`

**Relationships**:

- A user can own many entries.

**Validation rules**:

- Existing user rows must not be deleted or overwritten by baseline adoption.
- Existing password hashes must remain usable after migration.

## Entry

Existing trip/drink log entity that must be preserved through migration.

**Baseline fields**:

- `id`
- `drink_type`
- `abv`
- `quantity`
- `brand`
- `latitude`
- `longitude`
- `image_path`
- `timestamp`
- `timezone`
- `timezone_code`
- `user_id`

**Relationships**:

- Each entry belongs to a user through `user_id`.

**Validation rules**:

- Existing entry rows must not be deleted or overwritten by baseline adoption.
- Existing image paths remain runtime data references and are not modified by migration.

## State Transitions

```text
empty database
  -> apply initial migration
  -> ready database

current-schema database without migration history
  -> baseline initial migration
  -> ready database

ready database
  -> no-op on repeated migration run
  -> ready database

outdated or incompatible database
  -> migration required or migration failure
  -> startup blocked until resolved
```

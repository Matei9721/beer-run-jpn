# Data Model: Add Beer-Run Schema

## BeerRun

Represents a named trip/run grouping for entries and memberships.

### Fields

- `id`: Stable internal identifier.
- `name`: Unique human-readable beer-run name. `BeerRunJPN` must be representable.
- `is_public`: Visibility flag. Defaults to private for new beer-runs.
- `created_at`: Creation timestamp for ordering and auditing.

### Relationships

- Has many `BeerRunMember` records.
- Has many `Entry` records.

### Validation Rules

- `name` is required and unique.
- `is_public` defaults to false/private when not specified.
- A valid beer-run must have at least one owner membership.
- Immediately after Task 03 backfill, `BeerRunJPN` is the only public run; additional public runs remain valid future data when explicitly marked public.

## BeerRunMember

Represents one user's membership in one beer-run.

### Fields

- `id`: Stable internal identifier.
- `beer_run_id`: The beer-run this membership belongs to.
- `user_id`: The user this membership belongs to.
- `role`: Membership role, limited to `owner` or `member`.
- `created_at`: Creation timestamp for ordering and auditing.

### Relationships

- Belongs to one `BeerRun`.
- Belongs to one `User`.

### Validation Rules

- The same user can have at most one membership in the same beer-run.
- `role` is required and must be `owner` or `member`.
- Each beer-run must have at least one owner membership in valid application/test data.

## User

Existing account entity.

### New Relationships

- Has many `BeerRunMember` records.
- Can belong to multiple beer-runs through memberships.

### Validation Rules

- Existing username and password behavior remains unchanged.
- Task 03 backfill will make every existing user a member of `BeerRunJPN` and assign Tamei as owner.

## Entry

Existing drink or trip log item.

### New Fields

- `beer_run_id`: The beer-run this entry belongs to.

### New Relationships

- Belongs to one `BeerRun`.

### Validation Rules

- Every entry must belong to exactly one valid beer-run once the schema and Task 03 backfill sequence is complete.
- Existing entries are preserved and assigned to `BeerRunJPN` by Task 03.

## Relationship Summary

```text
User 1..* BeerRunMember *..1 BeerRun
BeerRun 1..* Entry
User 1..* Entry
```

## State Notes

- New beer-runs start private.
- Membership roles are fixed for Release 1: owner and member.
- A beer-run may have more than one owner, but cannot have zero owners in valid data.
- Duplicate membership for the same user and run is invalid.

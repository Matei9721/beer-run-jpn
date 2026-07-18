# Data Model: Backfill Existing Trip

## BeerRunJPN

**Represents**: The default public beer-run for the existing historical Beer Run JPN trip.

**Key fields**:

- `name`: Must be `BeerRunJPN`.
- `is_public`: Must be true after backfill.
- `created_at`: Existing creation timestamp if the run already exists; otherwise the time the default run is created.

**Relationships**:

- Has many BeerRunJPN memberships.
- Has many historical and newly created default entries.

**Validation rules**:

- Exactly one beer-run named `BeerRunJPN` may exist.
- Backfill must reuse an existing `BeerRunJPN` row if present.
- Backfill must not create additional public runs.

## Existing User

**Represents**: A user account that existed before the beer-run backfill or exists when retrying the migration.

**Key fields**:

- `username`: Existing username; must not be changed by this feature.
- `hashed_password`: Existing credential data; must not be changed by this feature.

**Relationships**:

- Has one BeerRunJPN membership after backfill.
- Has zero or more entries that should appear in the default trip experience.

**Validation rules**:

- Every existing user gets at most one BeerRunJPN membership.
- The backfill does not create users.
- Existing login behavior must remain unchanged.

## Tamei User

**Represents**: The expected owner account for BeerRunJPN.

**Key fields**:

- `username`: Case-sensitive existing value expected to be `Tamei`.

**Relationships**:

- Must have a BeerRunJPN membership with owner role when present.

**Validation rules**:

- If present, Tamei must be owner after every backfill run.
- If absent, the backfill must report the missing-owner condition clearly and must not invent the account.

## BeerRunJPN Membership

**Represents**: A user's participation and role in BeerRunJPN.

**Key fields**:

- `beer_run_id`: References BeerRunJPN.
- `user_id`: References an existing user.
- `role`: Owner for Tamei when present; member for other users unless preserving an existing valid role on retry.

**Relationships**:

- Belongs to BeerRunJPN.
- Belongs to one existing user.

**Validation rules**:

- A user may have only one membership in BeerRunJPN.
- Retry must not duplicate memberships.
- Existing valid owner/member roles may be preserved unless Tamei needs to be corrected to owner.

## Entry

**Represents**: An existing or newly created drink/trip record shown in the current app experience.

**Key fields**:

- Existing drink, amount, location, timestamp, image, timezone, and user fields are preserved.
- `beer_run_id`: References BeerRunJPN for historical unassigned entries after backfill and for new entries created through the current UI.

**Relationships**:

- Belongs to an existing user.
- Belongs to BeerRunJPN for the current default trip experience.

**Validation rules**:

- Historical unassigned entries are assigned to BeerRunJPN.
- Already assigned entries for other runs are not moved by this backfill.
- Retry must not change valid BeerRunJPN assignments or alter entry totals.

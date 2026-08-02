# Implementation Summary: 006-add-beer-run-crud-api

**Status:** Completed
**Date:** 2026-07-26
**Branch:** `006-add-beer-run-crud-api` (based on `005-add-signup-api`)
**Worktree:** N/A — implemented directly on the branch

## Overview

Implemented the full beer-run CRUD API as specified in Spec 006: five endpoints
(create, list, detail, update, delete) with public/private visibility rules,
case-insensitive name uniqueness, owner-only mutations, cascade delete, and an
optional-authentication dependency for read endpoints.

## Files Created

| File | Purpose |
|------|---------|
| `beer_run_routes.py` | APIRouter with all 5 CRUD endpoints, name validation, visibility queries, IntegrityError helper |
| `migrations/versions/005_beer_run_name_nocase.py` | SQLite migration adding COLLATE NOCASE unique index on beer_runs.name |
| `tests/test_beer_run_crud.py` | 40 tests covering create, list, detail, update, delete, visibility, validation, error sanitization |

## Files Modified

| File | Changes |
|------|---------|
| `auth.py` | Added `optional_oauth2_scheme` and `get_optional_user()` dependency for read endpoints |
| `main.py` | Added `import beer_run_routes` and `app.include_router(beer_run_routes.router)` |
| `migrations/runner.py` | Registered migration 005 |
| `models.py` | Updated BeerRun.name to `String(collation="NOCASE")`, added NOCASE unique index in `__table_args__` |
| `schemas.py` | Added `BeerRunCreateRequest`, `BeerRunUpdateRequest`, `BeerRunResponse` |
| `tests/test_migrations.py` | Updated `MIGRATION_VERSIONS`, `restore_pre_case_insensitive_username_schema`, and assertions to include migration 005 |

## Test Results

```
189 passed, 0 failed, 1 warning in 28.16s
```

- **40 new CRUD tests** — all endpoints, visibility, auth, validation, cascading, error sanitization
- **104 existing auth tests** — all still pass
- **12 existing beer-run schema tests** — all still pass
- **7 existing main tests** — all still pass
- **24 existing migration tests** — updated for new migration, all pass
- **2 existing wrapped tests** — all still pass

## Spec Adherence

| Requirement | Status | Implementation |
|-------------|--------|---------------|
| FR-1.1 (name validation) | Done | `beer_run_routes.py:BEER_RUN_NAME_PATTERN` |
| FR-1.2 (case-insensitive duplicate) | Done | `beer_run_routes.py:_is_beer_run_name_unique_violation` + NOCASE pre-check |
| FR-1.3 (NOCASE migration) | Done | `migrations/versions/005_beer_run_name_nocase.py` |
| FR-1.4 (model metadata) | Done | `models.py:BeerRun` — `collation="NOCASE"`, `__table_args__` |
| FR-2.1 (JSON create request) | Done | `POST /api/beer-runs` in `beer_run_routes.py:create_beer_run` |
| FR-2.2 (atomic create + owner) | Done | Same route — beer_run insert + flush + membership insert |
| FR-2.3 (private default) | Done | `BeerRunCreateRequest.is_public: bool = False` |
| FR-2.4 (error responses) | Done | 422/409/500 with sanitized messages |
| FR-3.1 (list visible runs) | Done | `GET /api/beer-runs` in `beer_run_routes.py:list_beer_runs` |
| FR-3.2 (get run detail) | Done | `GET /api/beer-runs/{id}` in `beer_run_routes.py:get_beer_run` |
| FR-3.3 (member_count + role) | Done | `beer_run_routes.py:_beer_run_response` |
| FR-3.4 (BeerRunJPN visible) | Done | Via `_visible_runs_query` — public runs always visible |
| FR-4.1 (JSON update request) | Done | `PATCH /api/beer-runs/{id}` in `beer_run_routes.py:update_beer_run` |
| FR-4.2 (owner-only update) | Done | Ownership check before mutation, 403 for non-owners |
| FR-4.3 (name validation on update) | Done | Same BEER_RUN_NAME_PATTERN + NOCASE duplicate check |
| FR-4.4 (return updated run) | Done | Returns full BeerRunResponse |
| FR-5.1 (delete request) | Done | `DELETE /api/beer-runs/{id}` in `beer_run_routes.py:delete_beer_run` |
| FR-5.2 (owner-only delete) | Done | Ownership check, 403 for non-owners |
| FR-5.3 (cascade delete) | Done | entries → memberships → beer_run in one transaction |
| FR-5.4 (preserve unrelated data) | Done | Only target run + its entries/memberships deleted |
| AR-2.1 (schemas in schemas.py) | Done | Three new Pydantic models |
| AR-2.2 (dedicated router) | Done | `beer_run_routes.py` APIRouter, registered in `main.py` |
| AR-3.1 (single visibility query) | Done | `_visible_runs_query` shared by list and detail |
| AR-3.2 (optional auth) | Done | `auth.get_optional_user` returns `User \| None` |
| AR-5.1 (delete transaction) | Done | All deletes in one commit, rollback on failure |
| AR-5.2 (explicit delete) | Done | `.delete()` calls on entries then memberships then run |

## Smoke Test Manual Verification

To verify the implementation against a running server:

### Prerequisites
1. Ensure `SECRET_KEY` and `SIGNUP_CODE` are configured in `.env`
2. Run migrations: `uv --cache-dir .uv-cache run python scripts/migrate_db.py`
3. Start server: `uv --cache-dir .uv-cache run uvicorn main:app --host 127.0.0.1 --port 8000`

### Smoke Test Commands (curl / PowerShell)

```powershell
# 1. Log in
$token = (Invoke-RestMethod -Uri http://127.0.0.1:8000/token -Method Post -Body @{username='user';password='password'}).access_token
$headers = @{Authorization = "Bearer $token"}

# 2. Create a beer-run
$run = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/beer-runs -Method Post -Headers $headers -Body (@{name='Smoke Test Run'} | ConvertTo-Json) -ContentType 'application/json'
# Expected: 201, member_count=1, current_user_role='owner', is_public=false

# 3. List beer-runs (authenticated)
$runs = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/beer-runs -Headers $headers
# Expected: array containing 'Smoke Test Run' and 'BeerRunJPN'

# 4. List beer-runs (logged out)
$public = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/beer-runs
# Expected: array containing 'BeerRunJPN' but NOT 'Smoke Test Run'

# 5. Get detail
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/beer-runs/$($run.id)" -Headers $headers
# Expected: 200, full run details

# 6. Update name
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/beer-runs/$($run.id)" -Method Patch -Headers $headers -Body (@{name='Renamed Run'} | ConvertTo-Json) -ContentType 'application/json'
# Expected: 200, name='Renamed Run'

# 7. Make public
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/beer-runs/$($run.id)" -Method Patch -Headers $headers -Body (@{is_public=$true} | ConvertTo-Json) -ContentType 'application/json'
# Expected: 200, is_public=true. Now appears in logged-out list.

# 8. Delete
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/beer-runs/$($run.id)" -Method Delete -Headers $headers
# Expected: 200, {"status":"deleted","beer_run_id":<id>}
```

### Negative Smoke Tests
- Create without auth → 401
- Create with duplicate name → 409
- Create with 2-char name → 422
- Update as non-owner → 403
- Delete as non-owner → 403
- Fetch private run as logged-out → 404

## Deviations from Spec

None. All FRs and ARs are implemented as specified.

## Architecture Note

The `beer_run_routes.py` module follows the same APIRouter pattern as `auth_routes.py`, keeping the router focused and self-contained. `main.py` only registers the router (1 line of import, 1 line of `include_router`). No service layer or additional abstraction was introduced.

# ADR-001: Keep Account-Deletion Quarantine Outside Public Static Files

**Date:** 2026-08-30
**Status:** Accepted

## Context

Account deletion moves exclusively owned photos aside before committing the database transaction so a database failure can restore every live image reference. The original specification placed that quarantine beneath the configured upload root, but BoozeRunJpn serves `static/` publicly and the upload root is `static/uploads`. A failed post-commit purge could therefore leave deleted personal media addressable through `/static`.

## Decision

Store account-deletion quarantine operations in `.account-deletion-quarantine/` at the repository root, on the same filesystem as the uploads but outside the mounted static tree. Each operation has a random directory and a private manifest containing upload-root-relative original paths and quarantine filenames. Ignore the runtime quarantine root in Git.

Acquire a SQLite `BEGIN IMMEDIATE` lock before recomputing owned runs and photo candidates. Retry restoration after transient failures; if restoration remains impossible, retain the operation and manifest and return a sanitized recovery-pending failure instead of losing the recovery handle.

## Rationale

- Same-filesystem renames preserve the atomic staging property.
- Moving outside `static/` prevents retained quarantine data from being served publicly.
- A durable manifest allows an interrupted or persistently failed restoration to be diagnosed and recovered without logging personal paths.
- The early write lock closes the gap where concurrent run or entry creation could invalidate the cleanup plan.

## Consequences

- The quarantine root is runtime state and must remain untracked.
- A persistent restore failure can still require operator recovery, but it is explicit and recoverable rather than silently losing the moved-file list.
- The original Spec 016 wording that placed quarantine beneath the upload root is superseded by this safer boundary.

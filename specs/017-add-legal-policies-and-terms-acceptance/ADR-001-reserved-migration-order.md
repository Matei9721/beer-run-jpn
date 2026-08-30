# ADR-001: Preserve Migration 007 Before Legal Migration 008

- **Date:** 2026-08-30
- **Status:** Accepted
- **Context:** Updated `main` includes account deletion and `007_add_user_auth_subject`, which rebuilds `users`. Legal acceptance therefore follows as migration `008_add_terms_acceptances`. During parallel development, a disposable or pre-merge database may already have recorded 008 before later receiving the ID-preserving 007 rebuild.
- **Decision:** Register 007 before 008 as the canonical merged order and keep acceptance evidence in a separate child table with `REFERENCES users(id) ON DELETE CASCADE`. Migration/readiness behavior must also tolerate an already-recorded `006 -> 008 -> 007` development history without rewriting migration records.
- **Rationale:** Migration readiness is based on version presence rather than timestamp order. The child table survives migration 007's foreign-key-disabled `users` rebuild because numeric user IDs are preserved, while database and ORM cascades ensure account deletion removes acceptance evidence.
- **Consequences:** New databases and normal upgrades use `006 -> 007 -> 008`. Compatibility tests still cover both historical orders, run `PRAGMA foreign_key_check` after a simulated user-table rebuild, and prove user deletion cascades. No migration is applied to live data during implementation.

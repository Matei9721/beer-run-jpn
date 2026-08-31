# Spec 020 implementation summary

## Result

Implemented the data-backed Route Stamp run home in the isolated revamp
preview on branch `codex/frontend-revamp-run-home`.

The preview now resolves the selected run with the existing per-user storage
key and BeerRunJPN fallback, loads run metadata/leaderboard/entries as one
  scoped refresh, renders the approved identity → standings → Wrapped → recent
  pours hierarchy, and retains readable content when a later refresh
fails. Wrapped is shown only when `has_wrapped` is true. Logged-out visitors
receive public read data and an explicit view-only message.

The visual follow-up removes the decorative route graph, pulse row, and RUN
stamp; adds real run totals to the identity; promotes standings to the primary
surface; integrates Wrapped as a quieter paper ticket; raises the mobile Log
action into a coral circle; and keeps every standings row connected to a
run-scoped player pour sheet.

## Files

- `frontend_revamp/app/js/api.js` - normalized read-only API boundary.
- `frontend_revamp/app/js/run-selection.js` - selected-run state and storage helpers.
- `frontend_revamp/app/js/run-home.js` - run resolution, fallback, refresh generations, and access-loss recovery.
- `frontend_revamp/app/js/ui.js` - safe DOM rendering, empty/error/loading states, and sync feedback.
- `frontend_revamp/app/js/app.js` - home controller orchestration.
- `frontend_revamp/app/index.html` and `frontend_revamp/app/css/foundation.css` - responsive home mount and Route Stamp presentation.
- `frontend_revamp/app/js/navigation.js` - destination handling for dynamically rendered home actions.
- `tests/test_frontend_revamp.py` - asset isolation/version and run-home source contracts.

No production templates, production static assets, backend routes, database
files, migrations, uploads, or runtime data were changed.

## Verification

- Focused frontend tests: `8 passed, 1 warning`.
- Full suite: `509 passed, 1 warning`.
- `git diff --check`: passed.
- In-app Browser: public logged-out run rendered successfully at the default
  desktop viewport and at 390×844; the 390px view was inspected full-page for
  wrapping, fixed mobile navigation, standings, recent pours, and bottom
  spacing.
- In-app Browser refresh interaction: completed successfully with no console
  errors or warnings.
- In-app Browser mobile geometry: at 390px, document scroll width stayed below
  the viewport width; navigation targets measured 73×63px, the visible Refresh
  control measured 98×44px, and recent-pour disclosure targets measured 44×44px.
- Approved visual follow-up: the real data-backed preview was inspected at the
  narrow mobile viewport and at 1380×850 desktop. Wrapped is integrated into
  the run ticket only when available, with an ambient pull-tab action;
  standings show the backend-ordered top three with both volume and alcohol
  liters; Recent Pours follows standings in the wireframe's single-column flow
  on both mobile and desktop. The mobile document had no horizontal overflow.
  Tapping Tamei opened
  the correctly titled player-log dialog and Escape closed it normally.
- Desktop correction: the commented 988×835 viewport was rechecked with a
  single 717px dashboard column. A no-Wrapped fixture using the production
  classes rendered one 836px identity column with no empty region or Wrapped
  node. The redundant Recent Pours `Latest` badge was removed, and the pull-tab
  animation now uses a short nudge with a stable end state.
- Authentication-specific browser verification was not performed because no
  signed-in browser session or test credentials were available; the
  authenticated request and fallback contracts are covered by the isolated
  source tests and existing API tests.

The only test warning is the pre-existing Passlib/Argon2 deprecation warning.

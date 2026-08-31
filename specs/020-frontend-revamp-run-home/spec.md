# Spec 020: Frontend revamp run home

## Overview

Build the first data-backed Route Stamp screen inside the isolated revamp
preview. The screen gives a signed-in or logged-out visitor a coherent view of
the selected public or member-visible run, with live activity, compact
standings, recent pours, and explicit synchronization states.

The implementation extends the Task 01 vanilla shell under
`frontend_revamp/app/` and does not change the production home page or any
backend contract.

## Goals

- Resolve the selected run with the existing BeerRun fallback and browser
  storage behavior.
- Load run metadata, leaderboard, and entries as one run-scoped refresh unit.
- Present the approved mobile and desktop home hierarchy with resilient wrapping
  for user-generated names and drink data.
- Make loading, empty, unavailable, logged-out, and refresh-error states
  understandable without hiding existing data.

---

## Feature 1: Run context and scoped data loading

**Who & why:** Participants need to know which trip they are looking at before
they interpret any totals or activity. The screen must also remain safe when a
stored run was deleted, access was revoked, or a visitor is logged out.

### Functional Requirements

#### FR-1.1: Resolve the current run

The revamp home MUST resolve a run in this order: a valid authenticated
user-selected run stored under the existing
`beerRunJpn.selectedRun.user.{userId}` key, the first visible private run, the
first visible public run, and finally the public `BeerRunJPN` exact-name
fallback. A stored run that returns 404 MUST be removed from that user's
selection key before fallback continues. A logged-out visitor MUST never use a
private run and MUST use the public fallback when no other public context is
provided.

**Verify:** Exercise empty, authenticated, stored-valid, stored-404, and
logged-out contexts and confirm the selected run and storage cleanup match the
defined order.

#### FR-1.2: Use the existing read contracts

Run resolution and home refresh MUST use the existing response shapes from
`GET /api/me`, `GET /api/beer-runs`, `GET /api/beer-runs/{beer_run_id}`,
`GET /api/beer-runs/{beer_run_id}/leaderboard`, and
`GET /api/beer-runs/{beer_run_id}/entries`. The client MUST send the bearer
token only when one exists and MUST not broaden public visibility or expose
private run data to logged-out visitors.

**Verify:** Inspect requests in browser devtools or an injected fetch recorder
and confirm URLs, optional Authorization headers, and response handling.

#### FR-1.3: Refresh as one coherent run-scoped update

Each refresh MUST snapshot the selected run ID and a context generation, fetch
the run metadata, leaderboard, and entries for that snapshot, and render the
three results only after all required reads succeed. A run change MUST abort or
invalidate prior work before showing the replacement. A late response from a
previous run or refresh generation MUST not change the current run name,
standings, activity, Wrapped visibility, or sync status.

**Verify:** Hold one refresh request open, switch or replace the selected run,
then resolve the old request and confirm no old content is rendered.

#### FR-1.4: Capability-gate Wrapped

The home MUST render a `Wrapped is ready` entry point only when the selected
run response has `has_wrapped: true`. The card MUST be absent for false,
missing, or stale run capability data. Opening the entry point MUST preserve the
selected run ID for the later Wrapped integration without changing Wrapped's
existing visual implementation.

**Verify:** Render runs with `has_wrapped` true, false, and absent and confirm
only the true case exposes the Wrapped entry point.

### Architectural Requirements

#### AR-1.1: Keep module responsibilities focused

Network calls belong in `frontend_revamp/app/js/api.js`, selected-run state and
the existing per-user storage key belong in `run-selection.js`, DOM rendering
belongs in `ui.js`, and the home refresh/fallback controller belongs in a
focused revamp home module called by `app.js`. No framework, package manager,
or build step may be added.

#### AR-1.2: Preserve production boundaries

Only `frontend_revamp/app/`, the focused frontend-revamp tests, and the new
Task 02 specification or implementation summary may change. The production
`templates/`, `static/`, API modules, database, migrations, uploads, and
runtime data remain untouched.

---

## Feature 2: Standings-led home composition

**Who & why:** A group checking a trip from a phone needs immediate run context,
a prominent competition snapshot, and a short list of the most recent pours.
The layout should feel like a route record, not a generic metric dashboard.

### Functional Requirements

#### FR-2.1: Render the approved content order

The home MUST render selected-run identity and visibility with useful run totals
and an integrated conditional Wrapped entry point, followed by prominent
current standings and recent pours. It MUST NOT repeat those totals in a
separate pulse region. Desktop MUST preserve the wireframe's single-column
content flow rather than placing standings and recent pours in a two-column
dashboard.
The desktop sidebar and mobile bottom navigation MUST retain the
Task 01 order `Run`, `Standings`, `Log`, `Map`, `You`, with Profile represented
only by `You`. Sync status and the manual Refresh action MUST remain in the
shared shell locations.

**Verify:** Inspect the rendered DOM at 390x844 and a desktop viewport and
confirm the landmark order, navigation order, and action placement.

#### FR-2.2: Derive useful run totals

The selected-run identity MUST derive total liters, pour count, and member count
from the currently loaded run, leaderboard, and entries. These totals MUST be
readable text rather than decorative marks. An available run with no entries
MUST show zero-valued totals without inventing activity.

**Verify:** Render populated and zero-entry fixtures and confirm the identity
totals use fixture data without placeholder numbers or a duplicate pulse row.

#### FR-2.3: Render compact standings

The home MUST show the first three backend-ordered leaderboard rows and a
`See all` destination. Each row MUST show both `total_liters` and
`total_alcohol` in non-wrapping measure columns plus a fixed rank and flexible
participant column. Names MAY wrap to two lines, while both liter measures
remain right-aligned and fully visible. Selecting a visible player row
MUST open that player's run-scoped pour history from the entries already loaded
for the coherent home refresh. An empty leaderboard MUST have a clear
no-standings state.

**Verify:** Render long participant names and large totals at 390px and confirm
rank, name, both totals, disclosure, and the `See all` action do not overlap or clip;
open each player row and confirm the sheet contains only that player's pours.

#### FR-2.4: Render recent pours safely

The home MUST show the newest three entries from the selected run, with drink
type and brand as readable text, quantity and ABV as metadata, relative time,
and a fixed disclosure hit area. The text column owns wrapping for long drink,
brand, location, and translated labels. Entries without an image MUST retain
the same fixed visual slot and hierarchy as entries with an image. An empty
entry list MUST show a designed no-recent-pours state.

**Verify:** Render long drink, brand, location, and metadata values with and
without `image_path` and confirm the row geometry remains usable at mobile and
desktop widths.

#### FR-2.5: Preserve logged-out public use

When no valid access token is present, the home MUST keep public run identity,
leaderboard, and entries readable when the backend permits them. It MUST not
show authenticated-only actions as available, and it MUST explain the view-only
context with text rather than hiding the public data.

**Verify:** Load the preview without `access_token`, confirm public reads use no
Authorization header, and confirm private runs and write actions are absent.

### Architectural Requirements

#### AR-2.1: Use safe DOM construction

User-controlled run names, usernames, drink types, brands, locations, and
timestamps MUST be inserted through text-safe DOM APIs or equivalent escaping.
The renderer MUST not interpolate untrusted API fields into executable HTML.

#### AR-2.2: Use shared Route Stamp tokens

The new home styles MUST use the semantic light and dark tokens, typography,
spacing, ticket-surface, divider, shape, and motion rules established by
`frontend_revamp/design/design-system.md` and Task 01. New raw theme colors,
gradients, country-specific motifs, or a second icon family are not allowed.

#### AR-2.3: Preserve responsive interaction geometry

At 390x844 the home MUST use one-column content with 44px minimum interactive
targets, visible focus, no horizontal overflow, and enough bottom padding for
the fixed sync row and five-column navigation. At desktop widths it MUST use
the 192px sidebar and a maximum 900px main content measure. Long content MUST
grow naturally rather than hiding actions.

---

## Feature 3: System feedback and synchronization

**Who & why:** Travel networks are intermittent and data can be empty during a
new run. People need to understand whether BeerRun is loading, showing a real
empty run, or preserving the last successful snapshot after a refresh failure.

### Functional Requirements

#### FR-3.1: Loading state

Initial run-home loading MUST use skeletons or equivalent reserved geometry for
the identity, standings, and recent-pours regions. It MUST expose a
polite status message and MUST keep the shell navigation usable.

**Verify:** Delay the initial reads and confirm stable loading geometry,
accessible status text, and usable shell controls.

#### FR-3.2: Unavailable-run state

When no permitted run can be resolved, the home MUST replace the data regions
with a clear unavailable state that distinguishes missing access from a network
failure where the client can know the difference. The state MUST offer the
shared manual Refresh action and MUST not display stale content as if it
belonged to a different run.

**Verify:** Return an empty public fallback and a 404 run response and confirm
the selected-run identity, main content, and status communicate unavailability.

#### FR-3.3: Refresh success and error states

The manual Refresh action MUST remain visible beside the last-synced status.
While a real request is active it MUST be disabled or otherwise prevent
duplicate work, keep its label width stable, and announce progress. On success
it MUST announce a current sync time. If a refresh fails after a successful
snapshot, it MUST retain that snapshot and show an inline or status-region
error. Network or HTTP errors MUST not be rendered as empty arrays.

**Verify:** Trigger success, network failure, HTTP failure, and duplicate-click
cases and confirm status text, button state, and retained content.

#### FR-3.4: Reduced motion

Home state replacement, button press feedback, and refresh indication MUST use
the approved Route Stamp durations and MUST resolve to no transform or
rotation under `prefers-reduced-motion: reduce`. Status and focus feedback MUST
remain visible.

**Verify:** Emulate reduced motion and confirm the home retains all information
while disabling press and loading animation effects.

### Architectural Requirements

#### AR-3.1: Version changed revamp assets

Because the home changes the deployed revamp stylesheet, JavaScript modules,
and HTML entry point, the shared human-readable revamp asset version MUST be
incremented consistently in HTML, direct module imports, CSS font/icon URLs,
and `frontend_revamp/app/README.md`.

#### AR-3.2: Keep the existing preview route isolated

The implementation MUST continue to be served only through `/revamp-preview`
and `/revamp-assets`, with no link or injection into `/`. Existing Task 01
route and asset isolation tests MUST remain green.

---

## Data Requirements

- Run identity uses `BeerRunResponse` fields `id`, `name`, `is_public`,
  `has_wrapped`, `member_count`, and `current_user_role`.
- Standings use `LeaderboardUser` fields `username`, `total_liters`, and
  `total_alcohol`, preserving backend order.
- Recent pours use `Entry` fields `id`, `username`, `drink_type`, `abv`,
  `quantity`, `brand`, `latitude`, `longitude`, `image_path`, `timestamp`,
  `timezone`, and `timezone_code`.
- No schema, database, migration, or API response change is introduced.

## Integration Points

- `frontend_revamp/app/index.html`: shared shell and home mount.
- `frontend_revamp/app/css/foundation.css`: Route Stamp home layout,
  responsive geometry, states, and motion.
- `frontend_revamp/app/js/api.js`: normalized run, leaderboard, entries, and
  current-user reads.
- `frontend_revamp/app/js/run-selection.js`: selected run state and existing
  per-user key helpers.
- `frontend_revamp/app/js/ui.js`: safe home DOM rendering and sync feedback.
- `frontend_revamp/app/js/run-home.js`: run resolution, refresh generations,
  fallback, and home controller.
- `frontend_revamp/app/js/app.js`: orchestration only.
- `tests/test_frontend_revamp.py`: source-level contract and asset-version
  coverage, while browser checks cover rendered behavior.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 019: Frontend revamp foundation and isolated preview | **Depends on** - extends the shared shell, tokens, modules, and preview route | AR-1.1, FR-2.1, AR-2.2, AR-3.2 |
| Spec 018: Rebrand and run-scoped Wrapped | **References** - preserves BeerRun naming and capability-gated Wrapped behavior | FR-1.4, FR-2.5 |
| Spec 009: Scope entries and leaderboard API | **References** - consumes the stable run-scoped read response shapes | FR-1.2, FR-2.3, FR-2.4 |

## Constraints

- Follow `repository_rules.md`, the approved Route Stamp design artifacts, and
  the Task 02 brief.
- Keep mobile-first information hierarchy and one-handed target sizing.
- Keep current production templates, static assets, Wrapped implementation,
  database, uploads, and caches unchanged.
- Do not add a frontend framework, package manager, build tool, CDN runtime
  dependency, or new backend capability.

## Out of Scope

- The full run picker/library and switching UI, which belongs to Task 06.
- The full dedicated standings screen and its deeper ranking controls, which
  belong to Task 03; the compact run-home player log sheet is included here.
- Map, drink detail, logging, authentication screens, account settings, and
  Wrapped visual integration.
- Production cutover, API/schema changes, database migrations, and live data
  mutation.

## Risks and assumptions

- The isolated preview may call existing public read APIs after Task 02; it does
  not create entries or mutate backend state.
- The backend's `has_wrapped` flag remains the home visibility capability. The
  existing run-scoped Wrapped endpoint continues to enforce artifact validity
  when the later integration opens it.
- The preview can be tested with a disposable or existing local server; tests
  must not point at protected runtime database or upload paths.
- The run switcher remains a shared trigger until Task 06 supplies the full
  library interaction.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Features 1-3 define run resolution,
  home composition, states, responsive behavior, and explicit out of scope.
- [x] **Testing strategy** - Every functional requirement has a Verify line;
  source-level tests and required rendered browser checks are named in
  FR-2.1, FR-3.1, and AR-3.2.
- [x] **Existing patterns** - Task 01 modules, Route Stamp design artifacts,
  production selected-run behavior, and backend route shapes are referenced.
- [x] **Dependencies** - No new dependency is proposed; AR-2.2 and the
  constraints preserve the local asset and vanilla architecture.
- [x] **Architecture & interfaces** - AR-1.1, the Data Requirements, and
  Integration Points define module boundaries and consumed interfaces.
- [x] **Error handling & failure modes** - FR-1.3, FR-3.2, and FR-3.3 cover
  stale requests, access loss, network failures, HTTP failures, and empty
  content.
- [x] **Security review** - FR-1.1, FR-1.2, FR-2.5, and AR-2.1 cover public
  visibility, bearer-token scope, and untrusted content rendering.
- [x] **Performance impact** - FR-1.3 batches run-scoped reads, while AR-2.3
  and AR-3.1 preserve stable layout and cacheable static assets.
- [x] **Rollout & migration** - AR-1.2 and AR-3.2 preserve isolated preview
  rollout and a no-op production rollback boundary; no migration is needed.
- [x] **Assumptions & risks** - the final section records the preview API
  boundary, Wrapped capability interpretation, test data boundary, and Task 06
  switcher dependency.

# Spec 019: Frontend revamp foundation and isolated preview

## Overview

Establish the approved Route Stamp frontend foundation as a separately served preview without changing the production BeerRun interface. The preview provides the shared responsive shell, semantic design tokens, theme resolution, component primitives, and focused vanilla JavaScript module boundaries that Tasks 02-13 can extend.

## Goals

- Render the approved Task 00 shell at `/revamp-preview` on mobile and desktop.
- Preserve `/`, the current templates, the current static assets, and all API and browser-storage contracts.
- Give later revamp tasks a lightweight, accessible, theme-aware foundation with no build step.

---

## Feature 1: Isolated preview delivery

**Who & why:** Maintainers need to build and review the new frontend incrementally while the current BeerRun remains the reliable production experience. The preview therefore needs an explicit, reversible serving boundary that cannot accidentally replace the home page.

### Functional Requirements

#### FR-1.1: Explicit preview route

`GET /revamp-preview` MUST return `frontend_revamp/app/index.html` as an HTML document. The existing `GET /` route MUST continue to return `templates/index.html`, and the preview MUST NOT be linked from or injected into the production template.

**Verify:** Request both paths and confirm they return distinct documents whose identifying shell text comes from the expected source.

#### FR-1.2: Isolated asset namespace

Files below `frontend_revamp/app/` MUST be served below `/revamp-assets` without changing the existing `/static` mount. Missing revamp assets MUST return 404 and MUST NOT fall through to production assets.

**Verify:** Request the preview stylesheet and one module through `/revamp-assets`, then request a missing asset and confirm the expected content types and 404.

#### FR-1.3: Static preview behavior

Opening the preview MUST NOT require authentication, call a BeerRun API, write bearer-token or selected-run state, or mutate backend/runtime data. Representative shell content is explicitly labelled as preview content.

**Verify:** Load the preview with an empty browser profile and confirm it renders without API requests or local-storage writes.

### Architectural Requirements

#### AR-1.1: Absolute project-root resolution

The route and static mount MUST resolve files from `PROJECT_ROOT` in `main.py`, so serving does not depend on the process working directory.

#### AR-1.2: Rollback boundary

Removing the `/revamp-preview` route, `/revamp-assets` mount, and `frontend_revamp/app/` MUST fully remove Task 01 behavior. No production template, production CSS, production JavaScript, database, migration, or API contract may be changed.

---

## Feature 2: Route Stamp shell and component foundation

**Who & why:** Participants need a consistent BeerRun frame that works one-handed on phones and remains efficient on desktop. Later screens need shared primitives that already encode the approved visual language rather than restyling each screen independently.

### Functional Requirements

#### FR-2.1: Semantic application shell

The preview MUST use semantic header, navigation, main, section, form, and status-region elements. It MUST show the BeerRun product identity, a representative selected-run control, a preview heading, a small representative component panel, sync status, and Refresh without presenting Task 02 run-home data as implemented.

**Verify:** Inspect the document landmarks and confirm the preview exposes a single main landmark, labelled navigation, labelled selected-run control, form labels, and a polite sync-status region.

#### FR-2.2: Equivalent responsive navigation

Both viewport layouts MUST expose exactly Run, Standings, Log, Map, and You in that order with the approved Phosphor regular icons and visible text labels. At widths below 768px the shell MUST use a fixed five-column bottom navigation with sync controls directly above it; at 768px and above it MUST use the 192px desktop sidebar with sync controls in its footer. Log MUST be emphasized without becoming an additional destination.

**Verify:** At 390x844 and 1440x900, confirm the same five destinations and order, the correct mobile/desktop navigation pattern, and no duplicated You/Profile destination.

#### FR-2.3: Responsive fit and safe areas

At 390x844 and representative desktop widths, the document MUST have no horizontal page overflow or clipped focus indicators. Mobile sticky controls MUST respect safe-area insets, and main content MUST remain visible above the sync row and bottom navigation.

**Verify:** At both target viewports, compare `document.documentElement.scrollWidth` with `innerWidth`, tab through controls, and confirm the bottom content is not obscured.

#### FR-2.4: Shared control states

The foundation MUST visibly define primary, secondary, quiet, and disabled buttons; a labelled text control; selected navigation; and keyboard focus. Interactive targets MUST be at least 44x44 pixels, default fields and buttons MUST be 48px high, and disabled content MUST remain readable.

**Verify:** Inspect computed geometry and keyboard focus for every representative control in both themes.

### Architectural Requirements

#### AR-2.1: Approved semantic tokens

CSS MUST encode the complete approved light/dark semantic color roles, type scale, spacing scale, radii, layer scale, motion durations, and easing from `frontend_revamp/design/design-system.md` and `motion.md`. Component rules MUST use semantic tokens rather than raw theme colors.

#### AR-2.2: Approved visual constraints

The shell MUST use cool-paper/deep-green materiality, restrained coral action emphasis, thin rules, sparse surfaces, and clipped ticket corners only on the representative run identity surface. It MUST NOT introduce neon, gradients, glassmorphism, country-specific motifs, generic card grids, or new global destinations.

#### AR-2.3: Local fonts and icons

Barlow Condensed and Atkinson Hyperlegible Next WOFF2 assets and their license notices MUST be locally vendored with `font-display: swap`. Only the required Phosphor regular SVG navigation/utility icons MUST be vendored, rendered with `currentColor`, and retain upstream geometry and licensing.

---

## Feature 3: Theme and focused module boundaries

**Who & why:** People need the preview to respect their operating-system theme immediately, while later implementation tasks need isolated state and integration seams that do not collapse into a global script.

### Functional Requirements

#### FR-3.1: System-default theme resolution

Before the document becomes visible, a root theme resolver MUST read a frontend-only preference accepting `system`, `light`, or `dark`, default to `system`, and set `data-theme` to the resolved `light` or `dark` value. Invalid saved values MUST behave as `system`.

**Verify:** With no saved preference, confirm the root matches the browser color scheme before first paint; then confirm valid and invalid preference values resolve as specified.

#### FR-3.2: Live system preference changes

While the preference is `system`, a `prefers-color-scheme` change MUST update the root theme immediately without shifting layout, moving focus, or changing scroll position. Explicit `light` or `dark` preferences MUST ignore system changes.

**Verify:** Emulate light and dark system schemes with each preference value and confirm theme, focus, scroll position, and geometry remain stable.

#### FR-3.3: Preview-only theme demonstration

The preview MAY expose System, Light, and Dark controls to exercise the foundation, but they MUST be labelled as preview controls, use native radio semantics, and use a revamp-specific storage key. They MUST NOT imply that the Task 10 Account preference is implemented or synchronize with the account API.

**Verify:** Change each preview option using keyboard and pointer input, reload, and confirm only the revamp-specific preference persists.

### Architectural Requirements

#### AR-3.1: Focused JavaScript modules

`frontend_revamp/app/js/` MUST establish separate modules for API access, authentication state, run selection, UI rendering, navigation, mapping, form state, theme state, and top-level orchestration. Task 01 modules that do not yet integrate production data MUST expose narrow inert boundaries rather than making placeholder requests or duplicating future behavior.

#### AR-3.2: No global application state

Application orchestration MUST use ES module imports and explicit functions or state objects. No application state or handler may be attached to `window`, and no framework, package manager, transpiler, or build step may be added.

#### AR-3.3: Motion and reduced motion

Ordinary control transitions MUST use only approved opacity, transform, color, border, or surface changes. Under `prefers-reduced-motion: reduce`, Route Stamp durations MUST resolve to zero and press transforms, pulses, rotations, and scale changes MUST be disabled without removing status or focus feedback.

---

## Feature 4: Asset versioning and verification

**Who & why:** Operators need predictable browser updates when the revamp eventually becomes production code, and reviewers need evidence that this isolated foundation does not regress the current app.

### Functional Requirements

#### FR-4.1: Explicit preview asset versions

The preview HTML and JavaScript imports MUST use a shared human-readable version query string. `frontend_revamp/app/README.md` MUST document that any changed deployed CSS, JavaScript, font, or icon dependency increments the shared version in HTML entry points and direct module imports before release.

**Verify:** Inspect all preview entry-point asset references and direct module imports, and confirm the documented version value is consistent.

#### FR-4.2: Regression and browser verification

Focused route/asset tests and the complete pytest suite MUST pass. The preview MUST be inspected in light, dark, and system modes at 390x844 and a representative desktop viewport, including navigation equivalence, focus visibility, overflow, console errors, and system-theme changes.

**Verify:** Record the passing automated-test result and browser checks in the implementation summary.

### Architectural Requirements

#### AR-4.1: Source-only implementation

All implementation files MUST remain readable source files below `frontend_revamp/app/`, except the narrow route/static integration and focused tests. No generated bundles, lockfiles, package manifests, database artifacts, uploaded media, or cache files may be created or committed.

---

## Integration Points

- `main.py`: add only the `/revamp-preview` document route and `/revamp-assets` static mount using `PROJECT_ROOT`.
- `frontend_revamp/app/`: contain the isolated semantic HTML, CSS, locally vendored assets, JavaScript modules, and asset-versioning documentation.
- `tests/`: verify route isolation, asset delivery, and production-root preservation with the existing FastAPI `TestClient` fixture.
- Browser storage: use `beer_run_revamp_theme_preference`; do not read or write `access_token` or the production selected-run key.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 010: Update frontend auth and signup | **References** — preserves bearer-token browser storage and existing production frontend boundaries | FR-1.3, AR-1.2, AR-3.1 |
| Spec 011: Add beer-run selector UI | **References** — preserves selected-run storage behavior while establishing a future run-selection seam | FR-1.3, AR-3.1 |
| Spec 018: Rebrand and run-scoped Wrapped | **References** — preserves BeerRun product naming, production asset behavior, and unchanged Wrapped presentation | FR-1.1, AR-1.2, AR-2.2 |

## Constraints

- Follow `repository_rules.md` and the current API contracts.
- Use `frontend_revamp/wireframes/index.html` for shell structure and navigation order.
- Use the approved Route Stamp direction, design system, motion reference, content-resilience rules, and mockups as the visual source of truth.
- Preserve FastAPI, SQLite, vanilla CSS, vanilla JavaScript modules, and Leaflet as the only approved map library.
- Keep Task 01 representative content static and explicitly identified as preview-only.

## Out of Scope

- Production cutover or any change to `/`, `templates/`, `static/css/`, `static/js/`, or Wrapped assets.
- Live API calls, authentication UI, run selection behavior, maps, entry forms, home data, standings, activity, or full run-library behavior.
- An Account screen or production theme preference.
- Backend/API/database/migration changes.
- New visual-direction decisions, a frontend framework, build tooling, or dependency installation.

## Risks and assumptions

- The preview route is intentionally public because it contains no private data and makes no API calls.
- Font and icon assets must come from their approved upstream distributions with license notices; no runtime CDN dependency is acceptable.
- Later tasks may expand the inert module boundaries, but must not merge their responsibilities into the top-level orchestrator.
- The 768px desktop breakpoint is the Task 00 baseline and must be checked at intermediate widths during browser QA.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Features 1-4 define the isolated route, shell, themes, module boundaries, asset policy, and exact verification targets.
- [x] **Testing strategy** — FR-1.1 through FR-1.3 and FR-4.2 define focused TestClient checks plus required desktop/mobile browser verification.
- [x] **Existing patterns** — Integration Points and Related Specs reference `main.py`, current static serving, browser-storage boundaries, and prior frontend specs.
- [x] **Dependencies** — AR-2.3 permits only locally vendored approved font/icon assets; AR-3.2 and AR-4.1 forbid new runtime/build dependencies.
- [x] **Architecture & interfaces** — AR-1.1, AR-3.1, AR-3.2, and Integration Points define the serving and module boundaries.
- [x] **Error handling & failure modes** — FR-1.2 covers missing assets; FR-3.1 covers missing/invalid preferences; rollback is defined by AR-1.2.
- [x] **Security review** — FR-1.3 and the Constraints prohibit private data, API calls, auth changes, and runtime-data mutation in the public preview.
- [x] **Performance impact** — AR-2.3, AR-3.2, and AR-4.1 keep assets local, static, unbundled, and free of new runtime frameworks or requests.
- [x] **Rollout & migration** — AR-1.2 defines removal/rollback; FR-4.1 documents asset versioning; no data migration is introduced.
- [x] **Assumptions & risks** — the Risks and assumptions section records preview exposure, asset provenance, module evolution, and breakpoint validation.

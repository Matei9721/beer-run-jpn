# Frontend revamp application

This directory is the isolated Route Stamp implementation. FastAPI serves the document at `/revamp-preview` and these files below `/revamp-assets`. Nothing here replaces the production `/` route or `/static` assets before Task 14.

## Boundaries

- `index.html`: semantic shell and preview-only representative content.
- `css/foundation.css`: approved semantic tokens, components, motion, and responsive shell.
- `js/app.js`: orchestration only.
- `js/api.js`: network boundary; Task 01 does not make API requests.
- `js/auth.js`: token lifecycle plus focused login/signup rendering and validation.
- `js/invite.js`: public invite preview, auth resumption, idempotent acceptance, and joined-run selection.
- `js/run-selection.js`: selected-run interaction state.
- `js/run-home.js`: run resolution, scoped refresh generations, and home state orchestration.
- `js/run-library.js`: desktop popover/mobile sheet switching, full-library discovery, and focused create/manage flows.
- `js/standings.js`: full standings and run-scoped participant history surfaces.
- `js/ui.js`: rendering and status feedback.
- `js/navigation.js`: shared destination state.
- `js/map.js`: Leaflet markers, runner filtering, selected-entry state, and contextual drink detail.
- `js/log.js`: authenticated create/edit form, GPS and photo state, stale-save protection, and success receipt.
- `js/form-state.js`: form interaction state.
- `js/theme.js`: frontend-only System, Light, and Dark resolution.
- `assets/`: locally vendored font/icon files and their license notices.

## Asset cache busting

Task 08 assets use `revamp-029-08` for the stylesheet, application entry point, and application module imports. Unchanged dependencies retain their earlier versions. When any deployed revamp dependency changes, increment its relevant version everywhere it is referenced before release.

When Task 14 promotes revamp files to production paths, copy this convention into every affected production template and direct module import. Rollback before Task 14 is the removal of the `/revamp-preview` route, `/revamp-assets` mount, and this application directory; the existing `/` and `/static` paths remain untouched.

## Vendored sources

- Atkinson Hyperlegible Next Latin variable WOFF2: Fontsource distribution, SIL Open Font License 1.1.
- Barlow Condensed Latin 600/700 WOFF2: Fontsource 5.3.0 distribution, SIL Open Font License 1.1.
- House, Trophy, Plus, MapTrifold, User, CaretDown, ArrowClockwise, and BeerStein regular SVGs: Phosphor Icons core, MIT License.

The corresponding notices are in `assets/licenses/`. Fonts and icons are local. The map retains the app's existing Leaflet 1.9.4 and Leaflet.markercluster 1.4.1 CDN dependencies, while all revamp application modules remain isolated under `/revamp-assets/`.

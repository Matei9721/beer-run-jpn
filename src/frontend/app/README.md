# Production frontend application

This directory is the production Route Stamp interface. FastAPI serves
`index.html` at `/` and mounts this directory at `/assets`.

## Boundaries

- `index.html`: semantic landing page and application shell.
- `css/foundation.css`: approved semantic tokens, components, motion, and responsive shell.
- `css/landing.css`: compact four-section landing layout, responsive photo-map composition, page-level theme lock, and device-aware motion.
- `js/app.js`: orchestration only.
- `js/landing.js`: landing visibility, non-interactive OpenStreetMap backdrop, reveal motion, and responsive motion profile.
- `js/api.js`: authenticated and public API request boundary for application controllers.
- `js/account.js`: account summary, sign-out, appearance preference, ownership blockers, and account deletion.
- `js/auth.js`: token lifecycle plus focused login/signup rendering and validation.
- `js/confirmation.js`: shared accessible destructive confirmation lifecycle.
- `js/invite.js`: public invite preview, auth resumption, idempotent acceptance, and joined-run selection.
- `js/legal.js`: in-app legal routing, source-document loading, and accessible section navigation.
- `js/run-selection.js`: selected-run interaction state.
- `js/run-home.js`: run resolution, scoped refresh generations, and home state orchestration.
- `js/run-library.js`: desktop popover/mobile sheet switching, full-library discovery, and focused create/manage flows.
- `js/standings.js`: full standings and run-scoped participant history surfaces.
- `js/system-states.js`: presentation-only onboarding, connection notices, and shared retry controls.
- `js/ui.js`: rendering and status feedback.
- `js/navigation.js`: shared destination state.
- `js/map.js`: Leaflet markers, runner filtering, selected-entry state, and contextual drink detail.
- `js/log.js`: authenticated create/edit form, GPS and photo state, stale-save protection, and success receipt.
- `js/form-state.js`: form interaction state.
- `js/theme.js`: frontend-only System, Light, and Dark resolution.
- `assets/`: locally vendored font/icon files and license notices.

## Asset cache busting

Production frontend references use the coherent
`beerrun-101-portable-landing-photos` version. Increment it everywhere a directly
referenced deployed dependency changes.

## Vendored sources

- Atkinson Hyperlegible Next Latin variable WOFF2: Fontsource distribution, SIL Open Font License 1.1.
- Barlow Condensed Latin 600/700 WOFF2: Fontsource 5.3.0 distribution, SIL Open Font License 1.1.
- House, Trophy, Plus, MapTrifold, User, CaretDown, ArrowClockwise, and BeerStein regular SVGs: Phosphor Icons core, MIT License.

The corresponding notices are in `assets/licenses/`. Fonts and icons are local.
The map retains the app's existing Leaflet 1.9.4 and Leaflet.markercluster 1.4.1
CDN dependencies, while application modules are served below `/assets/`.

The landing map composition uses three user-approved BeerRun photographs copied
byte-for-byte into `assets/images/`. The original runtime uploads remain
untouched, while every source deployment receives the tracked landing assets.
Unavailable assets are hidden so a failed request never shows a broken image
placeholder.

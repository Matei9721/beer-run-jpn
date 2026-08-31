# Frontend revamp application

This directory is the isolated Route Stamp implementation. FastAPI serves the document at `/revamp-preview` and these files below `/revamp-assets`. Nothing here replaces the production `/` route or `/static` assets before Task 14.

## Boundaries

- `index.html`: semantic shell and preview-only representative content.
- `css/foundation.css`: approved semantic tokens, components, motion, and responsive shell.
- `js/app.js`: orchestration only.
- `js/api.js`: network boundary; Task 01 does not make API requests.
- `js/auth.js`: read-only authentication-state boundary.
- `js/run-selection.js`: selected-run interaction state.
- `js/run-home.js`: run resolution, scoped refresh generations, and home state orchestration.
- `js/ui.js`: rendering and status feedback.
- `js/navigation.js`: shared destination state.
- `js/map.js`: future Leaflet instance boundary; Task 01 does not load Leaflet.
- `js/form-state.js`: form interaction state.
- `js/theme.js`: frontend-only System, Light, and Dark resolution.
- `assets/`: locally vendored font/icon files and their license notices.

## Asset cache busting

Task 02 uses the shared version `revamp-020-7` on HTML stylesheet/module references, direct JavaScript module imports, fonts, and icons. When any deployed revamp CSS, JavaScript, font, or icon dependency changes, increment this shared version everywhere it is referenced before release. Keep query versions human-readable and change them in the same commit as the asset.

When Task 14 promotes revamp files to production paths, copy this convention into every affected production template and direct module import. Rollback before Task 14 is the removal of the `/revamp-preview` route, `/revamp-assets` mount, and this application directory; the existing `/` and `/static` paths remain untouched.

## Vendored sources

- Atkinson Hyperlegible Next Latin variable WOFF2: Fontsource distribution, SIL Open Font License 1.1.
- Barlow Condensed Latin 600/700 WOFF2: Fontsource 5.3.0 distribution, SIL Open Font License 1.1.
- House, Trophy, Plus, MapTrifold, User, CaretDown, and ArrowClockwise regular SVGs: Phosphor Icons core, MIT License.

The corresponding notices are in `assets/licenses/`. No font, icon, or JavaScript runtime CDN request is made by the preview.

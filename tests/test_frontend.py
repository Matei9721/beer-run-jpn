import json
import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "src" / "frontend" / "app"
ASSET_VERSION = "beerrun-105-tour-end"
LANDING_ASSET_VERSION = "beerrun-117-photo-pins"
LANDING_STYLE_VERSION = "beerrun-121-live-system-theme"
APP_MODULE_VERSION = "beerrun-126-wait-indicators"
THEME_MODULE_VERSION = "beerrun-121-live-system-theme"
FOUNDATION_ASSET_VERSION = "beerrun-126-wait-indicators"
MAP_ASSET_VERSION = "beerrun-114-desktop-map"
MAP_MODULE_VERSION = "beerrun-115-cluster-replay"
TOUR_ASSET_VERSION = "beerrun-113-mobile-tour"


def run_node_module(script):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_production_root_serves_the_route_stamp_application(client):
    production = client.get("/")

    assert production.status_code == 200
    assert production.headers["content-type"].startswith("text/html")
    assert production.content == (FRONTEND_ROOT / "index.html").read_bytes()
    assert "data-app-shell" in production.text
    assert "data-run-home" in production.text
    assert "/assets/" in production.text


def test_production_assets_use_the_assets_namespace(client):
    stylesheet = client.get(f"/assets/css/foundation.css?v={FOUNDATION_ASSET_VERSION}")
    landing_stylesheet = client.get(f"/assets/css/landing.css?v={LANDING_STYLE_VERSION}")
    module = client.get(f"/assets/js/app.js?v={ASSET_VERSION}")
    landing_photos = [
        client.get(f"/assets/assets/images/{filename}?v={LANDING_ASSET_VERSION}")
        for filename in (
            "landing-drink-at-bar.webp",
            "landing-canned-sour.webp",
            "landing-drink-at-restaurant.webp",
            "landing-map-unpinned.webp",
        )
    ]
    missing = client.get("/assets/css/does-not-exist.css")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert landing_stylesheet.status_code == 200
    assert landing_stylesheet.headers["content-type"].startswith("text/css")
    assert module.status_code == 200
    assert "javascript" in module.headers["content-type"]
    assert all(photo.status_code == 200 for photo in landing_photos)
    assert all(photo.headers["content-type"] == "image/webp" for photo in landing_photos)
    assert missing.status_code == 404
    assert client.get("/revamp-preview").status_code == 404
    assert client.get("/revamp-assets/css/foundation.css").status_code == 404


def test_production_document_references_only_versioned_entry_assets(client):
    html = client.get("/").text
    asset_urls = re.findall(r'(?:href|src)="(/assets/(?:css|js)/[^"]+)"', html)

    assert asset_urls == [
        f"/assets/css/foundation.css?v={FOUNDATION_ASSET_VERSION}",
        f"/assets/css/map.css?v={MAP_ASSET_VERSION}",
        f"/assets/css/landing.css?v={LANDING_STYLE_VERSION}",
        f"/assets/js/app.js?v={APP_MODULE_VERSION}",
    ]
    assert "/static/css/" not in html
    assert "/static/js/" not in html


def test_frontend_module_boundaries_exist_and_imports_resolve():
    javascript_root = FRONTEND_ROOT / "js"
    expected_modules = {
        "account.js",
        "api.js",
        "app.js",
        "auth.js",
        "avatar.js",
        "confirmation.js",
        "form-state.js",
        "invite.js",
        "landing.js",
        "legal.js",
        "log.js",
        "map.js",
        "navigation.js",
        "run-library.js",
        "run-selection.js",
        "run-home.js",
        "run-discovery.js",
        "tour.js",
        "standings.js",
        "system-states.js",
        "theme.js",
        "ui.js",
    }
    assert {path.name for path in javascript_root.glob("*.js")} == expected_modules

    app_source = (javascript_root / "app.js").read_text(encoding="utf-8")
    imports = re.findall(r'from "(\./[^"?]+\.js)\?v=([^"?]+)"', app_source)
    assert {Path(path).name for path, _ in imports} == expected_modules - {"app.js", "avatar.js", "confirmation.js", "run-discovery.js", "tour.js"}
    updated_versions = {"map.js": MAP_MODULE_VERSION, "theme.js": THEME_MODULE_VERSION, **dict.fromkeys(
        ("run-home.js", "run-library.js", "system-states.js"), TOUR_ASSET_VERSION
    ), **dict.fromkeys(
        ("account.js", "standings.js", "ui.js", "run-library.js"), "beerrun-123-dicebear-gaze-muted"
    ), "navigation.js": "beerrun-124-you-avatar", **dict.fromkeys(
        ("account.js", "auth.js", "invite.js", "legal.js", "log.js", "map.js", "run-home.js", "run-library.js", "standings.js", "system-states.js", "ui.js"),
        "beerrun-126-wait-indicators"
    )}
    assert all(version == updated_versions.get(Path(path).name, ASSET_VERSION) for path, version in imports)
    assert all((javascript_root / path.removeprefix("./")).is_file() for path, _ in imports)


def test_landing_page_routes_into_production_application_flows():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "landing.css").read_text(encoding="utf-8")
    landing = (FRONTEND_ROOT / "js" / "landing.js").read_text(encoding="utf-8")
    app = (FRONTEND_ROOT / "js" / "app.js").read_text(encoding="utf-8")

    assert 'data-landing-page' in html
    assert html.count('class="landing-section') == 4
    landing_markup = html.split('data-landing-page', 1)[1].split('data-app-shell', 1)[0]
    assert 'role="main"' in landing_markup
    assert '<main' not in landing_markup
    assert html.count('data-landing-route="login"') == 1
    assert html.count('data-landing-route="signup"') == 1
    assert html.count('data-landing-route="tour"') == 1
    assert f'/assets/assets/images/landing-map-unpinned.webp?v={LANDING_ASSET_VERSION}' in html
    assert all(f'/assets/assets/images/{name}?v={LANDING_ASSET_VERSION}' in html for name in (
        "landing-drink-at-bar.webp",
        "landing-canned-sour.webp",
        "landing-drink-at-restaurant.webp",
    ))
    assert "/static/uploads/" not in landing_markup
    assert 'Open any logged drink on the map and see every friend\'s pin.' in html
    assert html.count('Take a tour') == 1
    assert '<span>Track the drinks.</span><span>Remember the trip.</span>' in html
    assert 'https://github.com/Matei9721/beer-run-jpn' in html
    assert 'page.dataset.motionProfile = desktopMotion.matches ? "desktop" : "touch"' in landing
    assert '@media (max-width: 767px)' in css
    mobile_css = css.split('@media (max-width: 767px)', 1)[1]
    assert '.landing-photo-map' in mobile_css
    assert 'min-height: calc(100dvh - 64px);' in mobile_css
    assert 'height: clamp(300px, 78vw, 340px);' in mobile_css
    assert 'overflow-x: auto' not in mobile_css
    assert '-webkit-mask-image: linear-gradient' in css
    assert 'filter: blur(1.5px)' in css
    assert 'inset: 0;' in css
    assert 'width: 100%;' in css
    assert 'height: 100%;' in css
    assert 'object-fit: cover;' in css
    assert '-webkit-mask-composite: source-in;' in css
    assert 'mask-composite: intersect;' in css
    assert '.landing-photo-map::after' not in css
    assert '--landing-photo-bleed' not in css
    assert 'width: calc(100% + var(--landing-photo-bleed) + 76px);' not in css
    assert 'margin-left: -76px;' not in css
    assert 'height: 108%;' not in css
    assert 'height: 110%;' not in mobile_css
    assert 'transparent 36%' in mobile_css
    assert 'rgb(0 0 0 / 0.12)' in mobile_css
    assert '--photo-rotation: -4.5deg;' in css
    photo_card_css = css.split('.landing-photo-card {', 1)[1].split('}', 1)[0]
    assert 'box-shadow: none;' in photo_card_css
    assert 'left: 40%;' in css
    assert 'right: 19%;' not in css
    hover_css = css.split('.landing-page.is-ready .landing-photo-card:hover {', 1)[1].split('}', 1)[0]
    assert 'box-shadow' not in hover_css
    assert '.landing-photo-rail figure::before' not in css
    assert '.landing-page.is-ready .landing-photo-card' in css
    assert 'opacity: 0;' not in photo_card_css
    assert 'translate: 0 32px;' not in css
    assert '@media (min-width: 768px) and (hover: hover) and (pointer: fine)' in css
    assert 'class="landing-map-signal"' not in html
    assert '@keyframes landingMapDrift' not in css
    assert '@keyframes landingPhotoBreathe' not in css
    assert '@keyframes landingPhotoFloat' not in css
    assert '@keyframes landingSignalPulse' not in css
    assert '@media (prefers-reduced-motion: reduce)' in css
    assert 'IntersectionObserver' in landing
    assert 'data-landing-map' not in html
    assert 'tile.openstreetmap.org' not in landing
    assert 'window.addEventListener("scroll"' not in landing
    assert 'landing.isActive()' in app
    assert 'location.hash || "#landing"' in app
    assert 'data-landing-session-action="login"' in html
    assert 'data-landing-session-action="signup"' in html
    assert 'setAuthenticated' in landing
    assert 'image.addEventListener("error", hideUnavailablePhoto' in landing
    assert "figure.hidden = true" in landing
    assert 'services.auth.getAccessToken()) destination = "run"' in app
    assert 'closeTo: "#landing"' in app


def test_startup_placeholder_stays_until_session_and_run_are_ready():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-motion-profile="touch" hidden' in html
    assert 'role="status" data-startup-status' in html
    assert 'beer-run-loading.svg' in html.split('<body>', 1)[1]
    result = run_node_module(r'''
      import fs from "node:fs";
      import assert from "node:assert/strict";
      const app = fs.readFileSync("src/frontend/app/js/app.js", "utf8");
      const startup = app.slice(app.lastIndexOf("void (async () => {")).replace(/^void /, "");
      const cases = [];
      for (const [hash, status, invite] of [
        ["", "none", false], ["#landing", "valid", false],
        ["#map", "valid", false], ["#login", "none", false],
        ["#signup", "none", false], ["#map", "stale", false],
        ["#landing", "stale", false], ["", "none", true],
        ["#run", "valid", false],
      ]) {
        const events = [];
        const location = { hash, pathname: "/", search: invite ? "?invite=example" : "" };
        const history = { replaceState: (_state, _unused, url) => {
          location.hash = new URL(url, "https://example.test").hash;
        } };
        let resolveSession, resolveRun;
        const sessionPending = new Promise(resolve => { resolveSession = resolve; });
        const runPending = new Promise(resolve => { resolveRun = resolve; });
        const inactive = { isActive: () => false };
        const landing = { ...inactive, hide: () => events.push("hide-landing") };
        const authController = {
          ...inactive,
          validateStoredSession: () => { events.push("validate"); return sessionPending; },
          show: mode => events.push(mode),
        };
        const runHome = { initialize: () => { events.push("initialize"); return runPending; } };
        const inviteController = { ...inactive, hasInviteRoute: () => invite };
        const runLibrary = inactive, legalController = inactive;
        const onboarding = { consider: () => events.push("onboarding") };
        let loading = true;
        const document = { querySelector: selector => selector === "[data-startup-loading]"
          ? { remove: () => { loading = false; } } : null };
        const showLandingView = () => events.push("landing");
        const syncLandingSession = () => events.push("sync-session");
        const restoreDestination = () => events.push(`restore:${location.hash || "#landing"}`);
        const finished = eval(startup);
        const isLanding = !invite && (!hash || hash === "#landing");
        assert.deepEqual(events, isLanding ? ["landing", "validate"] : ["validate"]);
        assert.equal(loading, !isLanding);
        resolveSession({ status });
        await Promise.resolve();
        assert.equal(events.at(-1), "initialize");
        assert.equal(events.some(event => event.startsWith("restore:")), false);
        assert.equal(loading, !isLanding);
        resolveRun();
        await finished;
        assert.equal(loading, false);
        if (status === "stale") {
          assert.equal(location.hash, "#login");
          assert.equal(events.at(-1), "login");
        } else {
          assert.ok(events.includes(`restore:${invite ? "#invite" : hash || "#landing"}`));
        }
        cases.push({ hash, status, invite, earlyLanding: isLanding });
      }
      console.log(JSON.stringify(cases));
    ''')
    assert len(result) == 9
    assert sum(case["earlyLanding"] for case in result) == 3


def test_startup_failure_offers_retry_without_showing_the_landing_page():
    result = run_node_module(r'''
      import fs from "node:fs";
      import assert from "node:assert/strict";
      const app = fs.readFileSync("src/frontend/app/js/app.js", "utf8");
      const startup = app.slice(app.lastIndexOf("void (async () => {")).replace(/^void /, "");
      const cases = [];
      for (const phase of ["session", "run"]) {
        const location = { hash: "#run" };
        const inviteController = { hasInviteRoute: () => false };
        const authController = { validateStoredSession: async () => {
          if (phase === "session") throw new Error("Session unavailable");
          return { status: "valid" };
        } };
        const runHome = { initialize: async () => { throw new Error("Run unavailable"); } };
        const status = { textContent: "Loading BeerRun…" };
        const retry = { hidden: true };
        const document = { querySelector: selector => {
          if (selector === "[data-startup-status]") return status;
          if (selector === "[data-startup-retry]") return retry;
          throw new Error("Placeholder must remain until startup succeeds");
        } };
        const syncLandingSession = () => {};
        const showLandingView = () => assert.fail("Landing must not appear");
        const console = { error: () => {} };
        await eval(startup);
        assert.match(status.textContent, /couldn’t load/);
        assert.equal(retry.hidden, false);
        cases.push(phase);
      }
      console.log(JSON.stringify(cases));
    ''')
    assert result == ["session", "run"]


def test_wrapped_loading_indicator_settles_on_success_empty_and_error():
    result = run_node_module(r'''
      import fs from "node:fs";
      import assert from "node:assert/strict";
      const source = fs.readFileSync("src/frontend/static/js/wrapped.js", "utf8");
      const load = source.slice(source.indexOf("async function loadWrapped()"), source.indexOf("startBtn.addEventListener('click'"));
      const cases = [];
      for (const outcome of ["ready", "empty", "error"]) {
        let completeFetch;
        const fetch = () => new Promise(resolve => { completeFetch = resolve; });
        const window = { location: { href: "https://example.test/wrapped?run=1" } };
        const localStorage = { getItem: () => null };
        const attributes = {};
        const startBtn = { disabled: false, textContent: "START REEL", setAttribute: (key, value) => { attributes[key] = value; } };
        let wrapped, slides, message;
        const stage = { innerHTML: "", appendChild: () => {}, querySelectorAll: () => [], querySelector: () => ({ classList: { add: () => {} } }) };
        const renderSlide = () => ({});
        const renderEmptyState = value => { message = value; };
        const renderProgress = () => {}, updateControls = () => {}, queueGalleryMotionUpdate = () => {}, fitSlideText = () => {};
        const pending = eval(`${load}\nloadWrapped()`);
        assert.equal(attributes["aria-busy"], "true");
        assert.equal(startBtn.disabled, true);
        assert.equal(startBtn.textContent, "LOADING");
        completeFetch({ ok: outcome !== "error", status: 503, json: async () => ({ slides: outcome === "ready" ? [{ id: "intro" }] : [] }) });
        await pending;
        assert.equal(attributes["aria-busy"], "false");
        assert.equal(startBtn.disabled, outcome !== "ready");
        assert.equal(startBtn.textContent, outcome === "ready" ? "START REEL" : "UNAVAILABLE");
        if (outcome !== "ready") assert.ok(message);
        cases.push(outcome);
      }
      console.log(JSON.stringify(cases));
    ''')
    assert result == ["ready", "empty", "error"]


def test_application_pages_share_the_landing_wordmark_and_link_back_to_it():
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    auth = (FRONTEND_ROOT / "js" / "auth.js").read_text(encoding="utf-8")
    legal = (FRONTEND_ROOT / "js" / "legal.js").read_text(encoding="utf-8")
    onboarding = (FRONTEND_ROOT / "js" / "tour.js").read_text(encoding="utf-8")

    assert html.count('class="brand-wordmark landing-wordmark"') == 1
    assert 'product-identity brand-wordmark' in html
    assert 'data-show-landing' in html
    assert '.brand-wordmark__asset' in css
    assert html.count(f'beer-run-wordmark.svg?v={ASSET_VERSION}') == 2
    assert html.count(f'beer-run-wordmark-dark.svg?v={ASSET_VERSION}') == 2
    assert '<use href="/assets/assets/brand/' not in html
    assert 'createBrandWordmark' in auth
    assert 'createBrandWordmark' in legal
    assert 'createBrandWordmark' in onboarding
    assert 'auth-brand brand-wordmark' in auth
    assert 'product-identity brand-wordmark legal-view__brand' in legal
    assert 'onboarding-brand brand-wordmark' in onboarding
    assert 'identity.dataset.showLanding = ""' in auth
    assert 'identity.dataset.showLanding = ""' in legal


def test_production_brand_assets_are_finalized_and_the_mark_is_the_favicon(client):
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    final_brand_root = FRONTEND_ROOT / "assets" / "brand" / "final"

    assert 'rel="icon"' in html
    assert f'/assets/assets/brand/final/beer-run-mark.svg?v={ASSET_VERSION}' in html
    assert {path.name for path in final_brand_root.glob("*.svg")} == {
        "beer-run-logo-loop.svg",
        "beer-run-loading.svg",
        "beer-run-mark.svg",
        "beer-run-wordmark-dark.svg",
        "beer-run-wordmark.svg",
    }
    assert client.get(f"/assets/assets/brand/final/beer-run-mark.svg?v={ASSET_VERSION}").status_code == 200
    assert client.get(f"/assets/assets/brand/final/beer-run-loading.svg?v={ASSET_VERSION}").status_code == 200
    assert "prefers-reduced-motion: reduce" in (final_brand_root / "beer-run-loading.svg").read_text(encoding="utf-8")


def test_foundation_encodes_theme_motion_and_responsive_contracts():
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    theme = (FRONTEND_ROOT / "js" / "theme.js").read_text(encoding="utf-8")
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert ':root[data-theme="light"]' in css
    assert ':root[data-theme="dark"]' in css
    assert "@media (min-width: 768px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert "repeat(5, minmax(0, 1fr))" in css
    assert 'matchMedia("(prefers-color-scheme: dark)")' in theme
    assert 'addEventListener("change"' in theme
    assert "beer_run_revamp_theme_preference" in theme
    assert "data-run-home" in html
    assert "access_token" not in html


def test_system_theme_does_not_freeze_an_early_browser_reading():
    result = run_node_module(r'''
      import fs from "node:fs";
      import assert from "node:assert/strict";
      import { createThemeController } from "./src/frontend/app/js/theme.js";
      const html = fs.readFileSync("src/frontend/app/index.html", "utf8");
      const bootstrap = html.match(/<script>([\s\S]*?)<\/script>/)[1];
      const earlyStyle = html.match(/<style>([\s\S]*?)<\/style>/)[1];
      assert.ok(html.indexOf("<style>") < html.indexOf('rel="stylesheet"'));
      assert.ok(earlyStyle.includes("color-scheme: light"));
      assert.ok(earlyStyle.includes('data-theme="dark"'));
      assert.ok(earlyStyle.includes('data-theme="system"'));
      assert.ok(earlyStyle.includes('@media (prefers-color-scheme: dark)'));
      const cases = [];
      for (const saved of [null, "invalid", "system", "light", "dark"]) {
        for (const dark of [false, true]) {
          let stored = saved;
          const storage = { getItem: () => stored, setItem: (_key, value) => { stored = value; } };
          const root = { dataset: {} };
          const document = { documentElement: root };
          const localStorage = storage;
          const matchMedia = () => { throw new Error("Bootstrap must let CSS resolve the system theme"); };
          eval(bootstrap);
          const expected = saved === "light" || saved === "dark" ? saved : "system";
          assert.equal(root.dataset.theme, expected);
          // An old or transient concrete theme must not pin system mode at startup.
          root.dataset.theme = dark ? "dark" : "light";
          let listener;
          const media = {
            get matches() { throw new Error("System appearance must stay live in CSS"); },
            addEventListener: (_type, callback) => { listener = callback; },
            removeEventListener: () => {},
          };
          globalThis.matchMedia = () => media;
          const controller = createThemeController({ root, storage });
          assert.equal(root.dataset.theme, expected);
          listener();
          assert.equal(root.dataset.theme, expected);
          controller.setPreference("dark");
          assert.equal(root.dataset.theme, "dark");
          assert.equal(stored, "dark");
          controller.setPreference("light");
          assert.equal(root.dataset.theme, "light");
          assert.equal(stored, "light");
          controller.setPreference("system");
          assert.equal(root.dataset.theme, "system");
          assert.equal(stored, "system");
          cases.push({ saved, dark, initial: expected });
          controller.destroy();
        }
      }
      const root = { dataset: {} };
      const controller = createThemeController({ root, storage: { getItem: () => null } });
      assert.equal(root.dataset.theme, "system");
      controller.destroy();
      console.log(JSON.stringify(cases));
    ''')
    assert len(result) == 10


def test_run_home_preserves_scoped_data_and_stale_refresh_boundaries():
    javascript_root = FRONTEND_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    selection = (javascript_root / "run-selection.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    ui = (javascript_root / "ui.js").read_text(encoding="utf-8")
    standings = (javascript_root / "standings.js").read_text(encoding="utf-8")

    assert '"/api/me"' in api
    assert '"/api/beer-runs"' in api
    assert "/leaderboard" in api
    assert "/entries" in api
    assert 'view: "public"' in api
    assert '"beerRunJpn.selectedRun.user."' in selection
    assert "Promise.all" in home
    assert "contextGeneration" in home
    assert "refreshGeneration" in home
    assert "has_wrapped" in ui
    assert "textContent" in ui
    assert "innerHTML" not in ui
    assert "showModal" not in ui
    assert "fetchLeaderboard" in standings
    assert "metricRequest" in standings
    assert "history.pushState" in standings
    assert "sessionStorage" in standings
    assert "metricLeaderboard" in standings
    assert "Load more" in standings
    assert "showSelectedEntryContext" in standings
    assert "Drink map context" in standings
    assert "activityBars" not in ui
    assert "createRouteLine" not in ui
    assert "pulse-bars" not in ui
    assert "createPulse" not in ui
    assert "home-identity__stamp" not in ui
    assert "createWrappedCard" not in ui
    assert "total_alcohol" in ui
    assert "home-identity--has-wrapped" in ui
    assert '"Latest"' not in ui


def test_run_resolution_requires_an_explicit_or_remembered_choice():
    result = run_node_module("""
      import { createRunHomeController } from './src/frontend/app/js/run-home.js';
      import { createRunSelectionState } from './src/frontend/app/js/run-selection.js';
      const root = { querySelector: () => null, querySelectorAll: () => [], dispatchEvent: () => {} };
      const locationLike = { href: 'https://example.test/#run' };
      const historyLike = { replaceState: () => {} };
      let token = null;
      let removed = false;
      let storedId = null;
      let detailCalls = [];
      let dataCalls = [];
      const run = { id: 42, name: 'Remembered Crew', is_public: true };
      const api = {
        fetchCurrentUser: async () => ({ ok: true, data: { id: 7 } }),
        fetchMyBeerRuns: async () => ({ ok: true, data: [run] }),
        fetchBeerRun: async (id) => { detailCalls.push(Number(id)); return Number(id) === 42 ? { ok: true, data: run } : { ok: false, status: 404 }; },
        fetchLeaderboard: async (id) => { dataCalls.push(id); return { ok: true, data: [] }; },
        fetchEntries: async () => ({ ok: true, data: [] }),
      };
      const create = () => createRunHomeController({
        root, api, auth: { getAccessToken: () => token }, selection: createRunSelectionState(),
        storage: { getItem: () => storedId, removeItem: () => { removed = true; } },
        locationLike, historyLike,
      });
      const guest = create(); await guest.initialize();
      const guestRun = guest.getSnapshot().currentRun;
      token = 'test-token';
      const member = create(); await member.initialize();
      const memberRun = member.getSnapshot().currentRun;
      storedId = '404';
      const stale = create(); await stale.initialize();
      const staleRun = stale.getSnapshot().currentRun;
      storedId = '42';
      const remembered = create(); await remembered.initialize();
      console.log(JSON.stringify({ guestRun, memberRun, staleRun, removed, remembered: remembered.getSnapshot().currentRun.id, dataCalls, detailCalls }));
    """)
    assert result["guestRun"] is None
    assert result["memberRun"] is None
    assert result["staleRun"] is None
    assert result["removed"] is True
    assert result["remembered"] == 42
    assert result["dataCalls"] == [42]
    assert result["detailCalls"] == [404, 42]


def test_tour_visit_detection_respects_prior_visits_and_storage_failures():
    result = run_node_module("""
      import { hasVisited, TOUR_STORAGE_KEY } from './src/frontend/app/js/tour.js';
      const storage = (values) => ({ getItem: (key) => values[key] || null, length: Object.keys(values).length, key: (i) => Object.keys(values)[i] });
      console.log(JSON.stringify({
        fresh: hasVisited(storage({})),
        themeOnly: hasVisited(storage({ beer_run_revamp_theme_preference: 'dark' })),
        declined: hasVisited(storage({ [TOUR_STORAGE_KEY]: 'declined' })),
        oldGuide: hasVisited(storage({ beer_run_revamp_onboarding_complete: 'route-stamp-v5' })),
        signedIn: hasVisited(storage({ access_token: 'test-token' })),
        remembered: hasVisited(storage({ 'beerRunJpn.selectedRun.user.7': '42' })),
        blocked: hasVisited({ getItem: () => { throw Error('Storage disabled'); } }),
      }));
    """)
    assert result == {"fresh": False, "themeOnly": False, "declined": True, "oldGuide": True, "signedIn": True, "remembered": True, "blocked": False}


def test_tour_includes_real_runner_and_map_actions_when_data_exists():
    result = run_node_module("""
      import { buildTourSteps } from './src/frontend/app/js/tour.js';
      const data = { leaderboard: [{ username: 'A Runner' }], entries: [{ id: 12, latitude: 35, longitude: 139 }] };
      const full = buildTourSteps({ data });
      console.log(JSON.stringify({
        ids: full.map((step) => step.id),
        runner: full.find((step) => step.id === 'runner').username,
        pin: full.find((step) => step.id === 'map-pin').entryId,
        finalButtons: full.at(-1).popover.showButtons,
        empty: buildTourSteps().map((step) => step.id),
        offlineMap: buildTourSteps({ data, mapAvailable: false }).map((step) => step.id),
        nullLocation: buildTourSteps({ data: { entries: [{ id: 1, latitude: null, longitude: 0 }] } }).map((step) => step.id),
        tabs: full.filter((step) => step.clickDestination).map((step) => ({ destination: step.clickDestination, source: step.source.id, interactive: step.disableActiveInteraction === false, next: step.popover.showButtons.includes('next') })),
      }));
    """)
    assert result["ids"] == ["featured", "run", "switcher", "tab-standings", "standings", "runner-choice", "runner", "tab-map", "map", "map-pin", "map-detail", "tab-log", "log", "finish"]
    assert result["runner"] == "A Runner"
    assert result["pin"] == 12
    assert result["finalButtons"] == ["next", "close"]
    assert "runner" not in result["empty"]
    assert "map-pin" not in result["empty"]
    assert "map-pin" not in result["offlineMap"]
    assert "map-pin" not in result["nullLocation"]
    assert result["tabs"] == [
        {"destination": "standings", "source": "switcher", "interactive": True, "next": False},
        {"destination": "map", "source": "runner", "interactive": True, "next": False},
        {"destination": "log", "source": "map-detail", "interactive": True, "next": False},
    ]


def test_tour_scrolls_targets_clear_of_the_mobile_menu_and_browser_chrome():
    result = run_node_module("""
      import { scrollTourTargetIntoView } from './src/frontend/app/js/tour.js';
      const check = ({ top, bottom, menu = true, viewport = null, fixed = false }) => {
        const calls = [];
        const target = {
          closest: () => fixed ? {} : null,
          getBoundingClientRect: () => ({ top, bottom }),
          scrollIntoView: (options) => calls.push(options),
        };
        const root = { querySelector: () => ({
          getClientRects: () => menu ? [{}] : [],
          getBoundingClientRect: () => ({ top: 676 }),
        }) };
        scrollTourTargetIntoView(target, root, { innerHeight: 744, visualViewport: viewport });
        return calls;
      };
      console.log(JSON.stringify({
        obscuredByMenu: check({ top: 655, bottom: 703 }),
        belowFold: check({ top: 820, bottom: 868 }),
        visible: check({ top: 300, bottom: 348 }),
        desktop: check({ top: 655, bottom: 703, menu: false }),
        browserChrome: check({ top: 610, bottom: 658, viewport: { height: 620, offsetTop: 0 } }),
        aboveViewport: check({ top: 0, bottom: 48, viewport: { height: 620, offsetTop: 56 } }),
        fixedMenu: check({ top: 681, bottom: 744, fixed: true }),
      }));
    """)

    scroll = [{"behavior": "instant", "block": "center", "inline": "nearest"}]
    assert result == {
        "obscuredByMenu": scroll, "belowFold": scroll, "visible": [],
        "desktop": [], "browserChrome": scroll, "aboveViewport": scroll,
        "fixedMenu": [],
    }


def test_tour_targets_the_visible_menu_for_each_device():
    result = run_node_module("""
      import { visibleTourTab } from './src/frontend/app/js/tour.js';
      const desktop = { name: 'desktop', getClientRects: () => [] };
      const mobile = { name: 'mobile', getClientRects: () => [{}] };
      const root = { querySelectorAll: () => [desktop, mobile] };
      const phone = visibleTourTab('map', root).name;
      desktop.getClientRects = () => [{}];
      mobile.getClientRects = () => [];
      console.log(JSON.stringify({ phone, desktop: visibleTourTab('map', root).name }));
    """)
    assert result == {"phone": "mobile", "desktop": "desktop"}


def test_navigation_disables_run_pages_until_a_run_is_selected():
    result = run_node_module("""
      import { bindNavigation } from './src/frontend/app/js/navigation.js';
      let click;
      let pushed = 0;
      let opened = null;
      const navigated = [];
      globalThis.window = { addEventListener: () => {} };
      globalThis.history = { pushState: () => { pushed++; } };
      const links = ['run', 'standings', 'log', 'map', 'you'].map((destination) => ({
        dataset: { destination }, href: '#' + destination, attrs: {},
        classList: { remove: () => {}, toggle: () => {} },
        setAttribute(key, value) { this.attrs[key] = value; },
        removeAttribute(key) { delete this.attrs[key]; },
        getAttribute(key) { return this.attrs[key]; },
      }));
      const nav = bindNavigation({ querySelectorAll: () => links, addEventListener: (_, callback) => { click = callback; }, dispatchEvent: (event) => { navigated.push([event.detail.destination, opened]); } }, { onNavigate: (destination) => { opened = destination; } });
      const disabled = links.filter((link) => link.attrs['aria-disabled'] === 'true').map((link) => link.dataset.destination);
      const tap = () => click({ target: { closest: () => links[1] }, preventDefault: () => {} });
      tap(); const before = pushed;
      nav.setRunAvailable(true); tap();
      console.log(JSON.stringify({ disabled, before, pushed, opened, navigated, enabled: links.every((link) => !link.attrs['aria-disabled']) }));
    """)
    assert result == {"disabled": ["standings", "log", "map"], "before": 0, "pushed": 1, "opened": "standings", "navigated": [["standings", "standings"]], "enabled": True}


def test_sync_indicator_tracks_api_state_independently_of_run_selection():
    result = run_node_module("""
      import { setSyncStatus } from './src/frontend/app/js/ui.js';
      const controls = { dataset: {} };
      const region = {};
      const root = { querySelectorAll: (selector) => selector === '.sync-controls' ? [controls] : [region] };
      setSyncStatus(root, 'Synced 19:00');
      const ready = { ...controls.dataset };
      setSyncStatus(root, 'Connection unavailable');
      const failed = { ...controls.dataset };
      setSyncStatus(root, 'Syncing public runs');
      console.log(JSON.stringify({ ready, failed, pending: controls.dataset, text: region.textContent }));
    """)
    assert result == {"ready": {"syncState": "ready"}, "failed": {"syncState": "error"}, "pending": {"syncState": "pending"}, "text": "Syncing public runs"}


def test_run_home_has_responsive_content_and_feedback_contracts():
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for class_name in (
        "home-identity",
        "home-identity__metrics",
        "wrapped-pulltab",
        "home-dashboard",
        "standings-card",
        "standings-list",
        "activity-list",
        "home-empty",
        "home-unavailable",
        "home-error",
        "player-history",
        "standings-link",
    ):
        assert f".{class_name}" in css
    assert "aria-live=\"polite\"" in html
    assert "repeat(5, minmax(0, 1fr))" in css
    assert "min-height: 100dvh" in css
    assert "prefers-reduced-motion: reduce" in css


def test_annotated_ui_cleanup_removes_redundancy_and_keeps_alignment_rules():
    javascript_root = FRONTEND_ROOT / "js"
    ui = (javascript_root / "ui.js").read_text(encoding="utf-8")
    standings = (javascript_root / "standings.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    map_module = (javascript_root / "map.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    for copy in (
        "Sign in to add a pour.",
        "Ranked by pure alcohol",
        "Continue logging drinks and switch between your runs.",
        "Welcome back",
        "Current legal terms loaded.",
        "Filter by runner and open a drink without leaving the map.",
    ):
        assert copy not in "\n".join((ui, standings, auth, map_module))

    assert 'top.append(createAccountAvatar(username), el("strong", "", `Rank ${index + 1}`));' in standings
    assert "Ranked by ${" not in standings
    assert "standings-legend" not in standings
    assert 'const ranking = el("div", "standings-ranking");' in standings
    assert "scoreStrip" not in standings
    assert "run-score-strip" not in css
    assert 'const pageHeading = heading("Leaderboard", "Standings", "");' in standings
    assert ".page-heading.standings-heading" in css
    assert ".standings-ranking { display: grid; gap: var(--space-3); }" in css
    assert ".standings-toolbar { min-height: 40px; display: flex; align-items: center; justify-content: flex-end;" in css
    assert "padding: var(--space-4); border: 1px solid var(--color-border);" not in css.split(".standings-toolbar {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    assert 'const toolbarCopy = el("strong", "standings-toolbar__label", "Sort");' in standings
    assert ".standings-toggle__button.is-selected { background: transparent;" in css
    assert "--standing-progress" in standings
    assert ".competition-list--full .competition-row::after" in css
    assert 'String(index + 1).padStart(2, "0")' in standings
    assert 'metric === "volume" ? liters(runner.total_liters) : alcohol(runner.total_alcohol)' in standings
    assert ".home-view-only" not in css
    assert ".auth-field { min-width: 0; display: grid; align-content: start;" in css
    assert ".auth-legal__status:empty { display: none; }" in css
    narrow_mobile_rules = css.split("@media (max-width: 420px)", maxsplit=1)[1].split("@media", maxsplit=1)[0]
    assert ".home-identity__wrapped { grid-template-columns: 1fr; align-content: center;" in narrow_mobile_rules
    assert ".wrapped-pulltab { width: 100%; }" in narrow_mobile_rules


def test_sync_controls_keep_timestamped_manual_and_automatic_refresh():
    javascript_root = FRONTEND_ROOT / "js"
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    standings = (javascript_root / "standings.js").read_text(encoding="utf-8")
    ui = (javascript_root / "ui.js").read_text(encoding="utf-8")
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert "const AUTO_REFRESH_INTERVAL_MS = 30_000;" in app
    assert "window.setInterval" in app
    assert "void runHome.refresh({ background: true });" in app
    assert "function sameSnapshotData(left, right)" in home
    assert "const dataChanged = !sameSnapshotData(lastData, nextData);" in home
    assert "const presentationChanged = dataChanged || retainedRefreshError;" in home
    assert "if (presentationChanged) renderRunHome" in home
    assert "if (presentationChanged) notify();" in home
    assert "changed: dataChanged" in home
    assert "setMetricPending(true);" in standings
    assert "paintStandings(true);" not in standings
    assert "existingRanking.replaceWith(ranking);" in standings
    assert "paintStandings(false, { rankingOnly: true });" in standings
    assert 'changeMetric(metric, { force: true })' in standings
    assert 'value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })' in home
    assert "`Synced ${formatSyncTime(refreshedAt)}`" in home
    assert 'controls.classList.toggle("is-syncing", pending);' in ui
    assert html.count('class="sync-dot"') == 1
    assert "Refresh data</span>" not in html
    assert html.count('title="Refresh data"><span class="icon icon--refresh"') == 1
    assert "mobile-sync" not in html
    assert ".sync-controls {" in css
    assert ".desktop-sidebar__footer { position: fixed;" in css
    desktop_footer_rule = re.search(r"\.desktop-sidebar__footer \{([^}]+)\}", css)
    assert desktop_footer_rule is not None
    assert "left: var(--space-4);" in desktop_footer_rule.group(1)
    assert "width: 160px;" in desktop_footer_rule.group(1)
    assert "padding: 0;" in desktop_footer_rule.group(1)
    assert "transform: none;" in desktop_footer_rule.group(1)
    assert "left: calc(192px + (100vw - 192px) / 2)" not in css
    assert ".refresh-button--icon { width: 44px; justify-content: center; padding: 0; border-radius: 50%; }" in css
    assert ".desktop-sidebar__footer .refresh-button { min-height: 44px; }" in css
    assert "@keyframes refresh-hover-spin { to { transform: rotate(360deg); } }" in css
    assert ".sync-controls .refresh-button:not(.is-loading):hover .icon { animation: refresh-hover-spin 420ms" in css
    assert ".sync-controls .refresh-button:active:not(:disabled)" in css
    assert "rotate(120deg) scale(0.88)" not in css
    assert ".refresh-button.is-loading .icon { animation: refresh-spin 900ms linear infinite; }" in css
    assert "75px - 68px - env(safe-area-inset-bottom)" in css


def test_run_library_and_quick_switcher_contracts_are_present():
    javascript_root = FRONTEND_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'new URLSearchParams({ view: "mine" })' in api
    assert 'new URLSearchParams({ view: "public", q: search })' in api
    assert "createRunLibraryController" in app
    assert "openSwitcher" in app
    assert "selectedPrimaryDestination" in app
    assert "QUICK_SWITCHER_LIMIT = 6" in library
    assert "QUICK_SEARCH_LIMIT = 20" in library
    assert 'dialog.showModal()' in library
    assert 'dialog.addEventListener("keydown"' in library
    assert 'event.key !== "Escape"' in library
    assert 'dialog.addEventListener("cancel"' in library
    assert 'event.target === dialog' in library
    assert "dataset.quickRunSearch" in library
    assert 'action("Open full run library"' in library
    assert 'action("Manage run"' in library
    assert "current_user_role === \"owner\"" in library
    assert 'if (run.has_wrapped)' in library
    assert '"Open Wrapped"' in library
    assert 'wrapped.href = `/wrapped?run=${encodeURIComponent(run.id)}`' in library
    assert 'result.status === 401' in home
    assert '[403, 404]' in home
    assert 'beer-run:session-rejected' in home
    rejected_session_handler = home.split("async function recoverFromRejectedSession", 1)[1].split(
        "async function refresh", 1
    )[0]
    assert "removeSelectedRunId" not in rejected_session_handler
    assert "removeSelectedRunId" in home
    assert "firstFallbackRun" not in home
    assert 'reason: "choose"' in home
    assert "run-switcher-dialog" in html
    assert 'aria-expanded="false"' in html
    assert ".run-quick-switcher" in css
    assert ".quick-switcher-panel" in css
    assert "body.run-switcher-open" in css
    assert "--run-switcher-scrollbar-width" in css
    assert ".run-library-discovery" in css


def test_run_share_url_and_shared_run_query_helpers_are_strict():
    module_uri = (FRONTEND_ROOT / "js" / "run-selection.js").as_uri()
    result = run_node_module(
        f"""
        import {{ buildRunShareUrl, removeSharedRunFromUrl, sharedRunFromUrl }} from {module_uri!r};
        const shared = {{ href: "https://beer.example/trip?invite=one&x=keep&run=2&invite=two&run=3#map" }};
        let replaced = "";
        console.log(JSON.stringify({{
          share: buildRunShareUrl(17, shared),
          valid: sharedRunFromUrl({{ href: "https://beer.example/?run=17" }}),
          duplicate: sharedRunFromUrl(shared),
          malformed: sharedRunFromUrl({{ href: "https://beer.example/?run=17x" }}),
          empty: sharedRunFromUrl({{ href: "https://beer.example/?run=" }}),
          absent: sharedRunFromUrl({{ href: "https://beer.example/?x=keep" }}),
          removed: removeSharedRunFromUrl(shared, {{ replaceState(_state, _title, value) {{ replaced = value; }} }}),
          replacement: replaced,
        }}));
        """
    )

    share = result["share"]
    assert share == "https://beer.example/trip?x=keep&run=17#map"
    assert result["valid"] == {"present": True, "valid": True, "id": 17}
    assert result["duplicate"] == {"present": True, "valid": False, "id": None}
    assert result["malformed"] == {"present": True, "valid": False, "id": None}
    assert result["empty"] == {"present": True, "valid": False, "id": None}
    assert result["absent"] == {"present": False, "valid": False, "id": None}
    assert result["removed"] is True
    assert result["replacement"] == "/trip?invite=one&x=keep&invite=two#map"


def test_ordinary_sharing_and_deep_link_resolution_are_wired_to_the_selected_run():
    javascript_root = FRONTEND_ROOT / "js"
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    selection = (javascript_root / "run-selection.js").read_text(encoding="utf-8")

    assert 'action("Share run", "run-library-current__utility")' in library
    assert "dataset.libraryShare" in library
    assert "buildRunShareUrl(run.id)" in library
    assert 'typeof navigator.share === "function"' in library
    assert 'navigator.clipboard.writeText(url)' in library
    assert 'window.prompt("Copy this run link", url)' in library
    assert library.index('typeof navigator.share === "function"') < library.index("navigator.clipboard.writeText(url)")
    assert library.index("navigator.clipboard.writeText(url)") < library.index('window.prompt("Copy this run link", url)')
    assert 'url.searchParams.delete("invite")' in selection
    assert 'url.searchParams.delete("run")' in selection
    assert 'url.searchParams.getAll("run")' in selection

    resolver = home.split("async function resolveCurrentRun", 1)[1].split("function currentRequest", 1)[0]
    assert resolver.index("sharedRunFromUrl(locationLike)") < resolver.index("api.fetchMyBeerRuns")
    assert "api.fetchBeerRun(shared.id" in resolver
    assert "[403, 404].includes(sharedResult.status)" in resolver
    assert "removeSharedRunFromUrl(locationLike, historyLike)" in resolver
    assert "resolved.shared && currentUser" in home
    assert "saveSelectedRunId(currentUser.id, currentRun.id, storage)" in home


def test_drink_configuration_validation_and_fallback_are_strict():
    module_uri = (FRONTEND_ROOT / "js" / "log.js").as_uri()
    result = run_node_module(
        f"""
        import {{ BUILT_IN_DRINK_CONFIG, validateDrinkConfig }} from {module_uri!r};
        const valid = validateDrinkConfig({{
          types: ["Beer", "Sake"],
          quantities: [{{ label: "330ml", value: 0.33 }}, {{ label: "1L", value: 1 }}],
        }});
        console.log(JSON.stringify({{
          valid,
          builtIn: BUILT_IN_DRINK_CONFIG,
          empty: validateDrinkConfig({{ types: [], quantities: [] }}),
          malformedType: validateDrinkConfig({{ types: [" Beer"], quantities: [{{ label: "330ml", value: 0.33 }}] }}),
          duplicateType: validateDrinkConfig({{ types: ["Beer", "beer"], quantities: [{{ label: "330ml", value: 0.33 }}] }}),
          reservedType: validateDrinkConfig({{ types: ["other"], quantities: [{{ label: "330ml", value: 0.33 }}] }}),
          malformedQuantity: validateDrinkConfig({{ types: ["Beer"], quantities: [{{ label: "330ml", value: "0.33" }}] }}),
          duplicateQuantity: validateDrinkConfig({{ types: ["Beer"], quantities: [{{ label: "small", value: 0.33 }}, {{ label: "large", value: 0.33 }}] }}),
        }}));
        """
    )

    assert result["valid"] == {
        "types": ["Beer", "Sake", "Other"],
        "quantities": [["330ml", 0.33], ["1L", 1], ["Other", "other"]],
    }
    assert result["builtIn"]["types"][-1] == "Other"
    assert result["builtIn"]["quantities"][-1] == ["Other", "other"]
    for key in ("empty", "malformedType", "duplicateType", "reservedType", "malformedQuantity", "duplicateQuantity"):
        assert result[key] is None

    api = (FRONTEND_ROOT / "js" / "api.js").read_text(encoding="utf-8")
    log = (FRONTEND_ROOT / "js" / "log.js").read_text(encoding="utf-8")
    assert 'readJson(fetchImpl, "/api/config", { signal, cache: "no-store" })' in api
    assert "validateDrinkConfig(result.data) || BUILT_IN_DRINK_CONFIG" in log
    assert "drinkConfig = BUILT_IN_DRINK_CONFIG" in log
    assert "void loadDrinkConfig()" in log


def test_create_and_manage_run_contracts_are_present():
    javascript_root = FRONTEND_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    for method in (
        "createBeerRun",
        "updateBeerRun",
        "fetchBeerRunMembers",
        "createBeerRunInvite",
        "leaveBeerRun",
        "deleteBeerRun",
    ):
        assert method in api
    assert 'method: "POST"' in api
    assert 'method: "PATCH"' in api
    assert 'method: "DELETE"' in api
    assert '"Content-Type": "application/json"' in api

    assert 'renderCreate()' in library
    assert 'renderManage()' in library
    assert '/^[A-Za-z0-9 _-]{3,64}$/' in library
    assert 'form.elements.visibility.value === "public"' in library
    assert '["owner", "member"].includes' in library
    assert 'exactText: run.name' in library
    assert 'showConfirmation({' in library
    assert '"Keep this run"' in library
    assert 'members.length === 1 ? "person" : "people"' in library
    assert 'eyebrow: "Membership change"' in library
    assert 'run.is_public' in library
    assert 'const trigger = event.currentTarget' in library
    assert '[401, 403, 404].includes(result.status)' in library
    assert 'navigator.clipboard.writeText' in library
    assert "let inviteStatus = null;" in library
    assert 'innerHTML' not in library
    assert "currentRun = { ...currentRun, ...run };" in home
    assert "updateRunSwitcher(root, currentRun, currentUser);" in home

    for class_name in (
        "manage-flow",
        "manage-form",
        "manage-choice-group",
        "manage-members",
        "manage-danger",
    ):
        assert f".{class_name}" in css


def test_account_and_shared_destructive_confirmation_contracts_are_present():
    javascript_root = FRONTEND_ROOT / "js"
    account = (javascript_root / "account.js").read_text(encoding="utf-8")
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    confirmation = (javascript_root / "confirmation.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    map_source = (javascript_root / "map.js").read_text(encoding="utf-8")
    theme = (javascript_root / "theme.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert '"/api/me/deletion-summary"' in api
    assert 'writeJson(fetchImpl, "/api/me"' in api
    assert 'body: { password, confirmation }' in api
    assert '/entries/${encodeURIComponent(entryId)}`' in api

    assert 'name = "account-theme"' in account
    assert '["system", "System", "Match your device"]' in account
    assert 'theme.setPreference(event.target.value)' in account
    assert 'ACCOUNT_CONFIRMATION = "DELETE MY ACCOUNT"' in account
    assert 'autocomplete: "current-password"' in confirmation
    assert 'result?.status === 409' in account
    assert "Run ownership can't be transferred yet." in account
    assert 'Other users\' accounts, entries, photos, and runs will not be deleted.' in account
    assert 'plural(entries, "entry", "entries")' in account
    assert 'recovery is pending' in account

    assert 'let activeDialog = null' in confirmation
    assert 'if (activeDialog)' in confirmation
    assert 'dialog.setAttribute("aria-modal", "true")' in confirmation
    assert 'dialog.setAttribute("aria-labelledby"' in confirmation
    assert 'dialog.setAttribute("aria-describedby"' in confirmation
    assert 'actions.append(cancel, confirm)' in confirmation
    assert 'dialog.addEventListener("cancel"' in confirmation
    assert 'event.target === dialog && !pending' in confirmation
    assert 'panel.querySelectorAll("button, input")' in confirmation
    assert 'requestAnimationFrame(restore)' in confirmation
    assert 'dialog.showModal()' in confirmation
    assert 'innerHTML' not in confirmation
    assert 'window.confirm' not in confirmation
    assert 'window.alert' not in confirmation

    assert 'showConfirmation({' in map_source
    assert 'safeLabel: "Keep drink"' in map_source
    assert 'api.deleteEntry(' in map_source
    assert 'if (root.querySelector("dialog[open]")) return;' in map_source
    assert 'const SELECTED_ENTRY_ZOOM = 16;' in map_source
    assert 'map.setView(center, zoom, { animate: false })' in map_source
    assert 'zoomToShowLayer' not in map_source
    assert 'cluster.spiderfy()' in map_source
    assert 'markerGroup?.removeLayer?.(marker)' not in map_source
    assert 'window.L.divIcon({ html: pin' in map_source
    assert 'marker.on("click", () => { stopReplay(); focusEntry(entry, { recenter: false }); })' in map_source
    assert 'autoPanOnFocus: false' in map_source
    assert 'maxZoom: 15, animate: false' in map_source
    assert 'resizeMap(true);' in map_source
    assert 'showConfirmation({' in library
    assert 'safeLabel: "Stay in this run"' in library
    assert 'exactText: run.name' in library

    assert 'removeSelectedRunId(user.id)' in app
    assert 'inviteController.reset()' in app
    assert 'url.searchParams.delete("invite")' in app
    assert 'url.searchParams.delete("run")' in app
    assert 'services.auth.removeAccessToken()' in app
    assert 'resetPrivateSurfaces()' in app
    assert 'currentUser?.id !== userId' in app
    assert 'reason: "identity-changed"' in account
    assert 'reason: "session-rejected"' in account
    assert 'result?.dismiss' in confirmation
    assert 'committed: true' in app
    assert 'committed: true' in map_source
    assert 'reconcileRunMutation(outcome' in library

    assert 'THEME_PREFERENCES = new Set(["system", "light", "dark"])' in theme
    assert 'storage.setItem(THEME_STORAGE_KEY, preference)' in theme
    assert 'guard.dataset.themeTransitionGuard' in theme

    for class_name in (
        "account-content",
        "account-summary",
        "account-stats",
        "account-theme-options",
        "account-danger",
        "confirmation-dialog",
        "confirmation-panel",
        "confirmation-actions",
    ):
        assert f".{class_name}" in css
    assert '.confirmation-dialog .button--danger:disabled' in css


def test_login_and_signup_preserve_auth_and_resume_contracts():
    javascript_root = FRONTEND_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    log = (javascript_root / "log.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert '"/token"' in api
    assert '"/api/signup"' in api
    assert '"/api/legal/metadata"' in api
    assert '"Content-Type": "application/x-www-form-urlencoded"' in api
    assert '"Content-Type": "application/json"' in api

    assert 'autocomplete: "username"' in auth
    assert 'autocomplete: "current-password"' in auth
    assert auth.count('autocomplete: "new-password"') == 2
    assert 'form.autocomplete = "on"' in auth
    assert 'terms_version: legalMetadata.terms_version' in auth
    assert 'terms_agreed: true' in auth
    assert 'role", "alert"' in auth
    assert 'aria-live", "assertive"' in auth
    assert 'setPending(form, true, "Logging in...")' in auth
    assert 'setPending(form, true, "Creating account...")' in auth
    assert 'The username or password is incorrect.' in auth
    assert 'That signup code is not valid.' in auth
    assert 'Check your connection and try again.' in auth
    assert 'input:not(:disabled)' in auth
    assert 'querySelectorAll("[data-auth-close]")' in auth
    assert 'scrollIntoView({ block: "center", behavior: "smooth" })' in auth
    assert 'storage.setItem(ACCESS_TOKEN_KEY, token)' in auth
    assert 'storage.removeItem(ACCESS_TOKEN_KEY)' in auth
    assert 'innerHTML' not in auth
    assert 'window.alert' not in auth

    assert 'createAuthController' in app
    assert 'validateStoredSession' in app
    assert 'beer-run:session-rejected' in app
    assert 'destination.startsWith("#invite")' in app
    assert 'ensureContentSurface();' in app
    assert 'restoreAuthDestination(returnTo)' in app
    assert 'requestedDestination === "#you" && !runHome.getSnapshot().currentUser' in app
    assert 'closeDestination' in app
    assert 'let closeTo = "#run"' in auth
    assert 'onClose?.({ returnTo, closeTo })' in auth
    assert 'beer-run:open-auth' in log
    assert 'returnTo: "#log"' in log
    assert 'beer-run:open-auth' in library
    assert 'returnTo: "#runs"' in library

    for class_name in (
        "auth-view",
        "auth-mobile-header",
        "auth-desktop-header",
        "auth-panel",
        "auth-form",
        "auth-field__input",
        "auth-legal__choice",
        "auth-submit",
        "auth-alternate",
        "log-auth-prompt",
    ):
        assert f".{class_name}" in css
    assert 'body.auth-view-open' in css
    assert 'scroll-padding-block: 88px 42dvh' in css
    assert 'scroll-margin-block: 88px 44dvh' in css


def test_legal_views_reuse_authoritative_documents_and_keep_signup_versioning():
    javascript_root = FRONTEND_ROOT / "js"
    legal = (javascript_root / "legal.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert 'terms: { url: "/terms", label: "Terms" }' in legal
    assert 'privacy: { url: "/privacy", label: "Privacy" }' in legal
    assert 'source.querySelector(".legal-document")' in legal
    assert 'aria-label", "Legal documents"' in legal
    assert 'aria-label", "On this page"' in legal
    assert 'dataset.legalDocument = name' in legal
    assert 'role", "alert"' in legal
    assert '"#terms" || location.hash === "#privacy"' in app
    assert 'terms_version: legalMetadata.terms_version' in auth
    assert 'terms_agreed: true' in auth
    assert '.legal-view__tab[aria-current="page"]' in css
    assert '.legal-sections__link' in css
    assert '@media (max-width: 560px)' in css
    assert '.legal-copy table, .legal-copy tbody, .legal-copy tr, .legal-copy td { display: block; }' in css
    assert 'min-width: 42rem' not in css


def test_invite_preview_auth_resume_and_acceptance_contracts_are_present():
    javascript_root = FRONTEND_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    invite = (javascript_root / "invite.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert '`/api/invites/${encodeURIComponent(code)}`' in api
    assert '`/api/invites/${encodeURIComponent(code)}/accept`' in api
    assert 'cache: "no-store"' in api
    assert 'getAll("invite")' in invite
    assert 'values.length !== 1' in invite
    assert 'PENDING_INVITE_KEY' in invite
    assert 'PENDING_INVITE_INTENT_KEY' in invite
    assert 'validInvitePreview' in invite
    assert 'validAcceptedRun' in invite
    assert 'validateOwnerInviteResponse' in invite
    assert 'reconcileAcceptedMembership' in invite
    assert 'token !== auth.getAccessToken()' in invite
    assert 'context !== getSnapshot()?.contextGeneration' in invite
    assert 'storage.getItem(PENDING_INVITE_INTENT_KEY) === code' in invite
    assert 'url.searchParams.delete("invite")' in invite
    assert 'innerHTML' not in invite
    assert 'preview.is_public' not in invite
    assert 'preview.member_count' not in invite
    assert 'preview.owner' not in invite

    assert 'createInviteController' in app
    assert 'inviteController.cancelAuthContinuation()' in app
    assert 'inviteController.hasInviteRoute()' in app
    assert 'location.hash === "#invite"' in app
    assert 'navigation.selectDestination("run", { notify: false })' in app
    assert 'buildInviteShareUrl(invite.data, run.id)' in library
    assert '[401, 403, 404].includes(invite.status)' in library
    assert 'navigator.clipboard.writeText(url)' in library
    assert 'navigator.share' in library

    for class_name in (
        "invite-content",
        "invite-ticket",
        "invite-ticket__mark",
        "invite-actions",
        "invite-status",
        "invite-notice",
        "manage-invite",
        "manage-invite__url",
    ):
        assert f".{class_name}" in css


def test_map_and_drink_detail_contracts_are_present():
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    source = (FRONTEND_ROOT / "js" / "map.js").read_text(encoding="utf-8")

    assert "leaflet.markercluster" in html
    assert "leaflet.js" in html
    assert "markerClusterGroup" in source
    assert "const requestedEntryId = entryId ?? sessionStorage.getItem(SELECTED_ENTRY_KEY);" in source
    assert "updateMapSelection(markerGroup, markers, selectedEntryId, selectedLayer)" in source
    assert '"Show all pins"' in source
    assert 'event.key === "Escape"' in source
    assert 'alt: accessibleTitle' in source
    assert "tileerror" in source
    assert "Map tiles are offline" in source
    assert "Photo unavailable" in source
    assert "no saved location" in source
    assert "sessionStorage.removeItem(SELECTED_ENTRY_KEY)" in source
    assert 'entry.username === snapshot.identity.username' in source
    assert 'role === "owner" || role === "member"' in source
    assert "Open details" not in source
    assert ".main-content--map" in css
    assert ".map-workspace.has-detail .map-unmapped" in css
    assert "z-index: 1100" in css
    assert "@media (max-width: 767px)" in css
    assert "object-fit: contain" in css
    assert "requestFullscreen" in source
    assert "document.exitFullscreen" in source
    assert 'typeof document.exitFullscreen !== "function"' in source
    assert 'typeof workspace.requestFullscreen !== "function"' in source
    assert "if (workspace && nativeFullscreenElement() === workspace)" in source
    assert "is-fullscreen-fallback" in source
    assert "invalidateSize" in source
    assert "Enter full screen map" in source
    assert "Exit full screen map" in source
    assert "map-fullscreen-control__icon--expand" in source
    assert "map-fullscreen-control__icon--collapse" in source
    assert ".map-workspace:fullscreen" in css


def test_log_edit_photo_location_and_success_contracts_are_present():
    css = (FRONTEND_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    source = (FRONTEND_ROOT / "js" / "log.js").read_text(encoding="utf-8")
    api = (FRONTEND_ROOT / "js" / "api.js").read_text(encoding="utf-8")

    assert 'field("Custom drink name", "drink_type_custom"' in source
    assert 'event.target.name === "drink_type"' in source
    assert 'event.target.value === "Other"' in source
    assert 'URL.createObjectURL(file)' in source
    assert 'dataset.clearSelectedPhoto' in source
    assert 'input.value = ""' in source
    assert '["750 ml", 0.75]' in source
    assert '["1 L", 1]' in source
    assert 'data.photoPreview' not in source
    assert 'dataset.photoPreview' in source
    assert 'navigator.geolocation.getCurrentPosition' in source
    assert 'enableHighAccuracy: false' in source
    assert 'maximumAge: 300000' in source
    assert 'captureLocation();' in source
    assert '"Recapture location"' in source
    assert '"icon icon--refresh"' in source
    assert '"Show captured coordinates"' in source
    assert '"Captured coordinates"' in source
    assert '.log-coordinate-info:focus-within .log-coordinate-info__tooltip' in css
    assert 'photo_action' in source
    assert 'snapshotKey()' in source
    assert 'receiptView(saved)' in source
    assert 'createEntry(beerRunId' in api
    assert 'updateEntry(beerRunId' in api
    assert '.log-photo-preview' in css
    assert 'object-fit: contain' in css
    assert '.log-location-field__dot' in css
    assert '.success-receipt' in css


def test_vendored_foundation_assets_and_licenses_are_present():
    assets = FRONTEND_ROOT / "assets"
    required = [
        assets / "fonts" / "atkinson-hyperlegible-next-latin-wght-normal.woff2",
        assets / "fonts" / "barlow-condensed-latin-600-normal.woff2",
        assets / "fonts" / "barlow-condensed-latin-700-normal.woff2",
        assets / "licenses" / "atkinson-hyperlegible-next-OFL.txt",
        assets / "licenses" / "barlow-condensed-OFL.txt",
        assets / "licenses" / "phosphor-icons-MIT.txt",
    ]
    required.extend(
        assets / "icons" / f"{name}.svg"
        for name in ("house", "trophy", "plus", "map-trifold", "user", "caret-down", "arrow-clockwise", "beer-stein")
    )

    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

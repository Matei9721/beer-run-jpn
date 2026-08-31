import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVAMP_ROOT = PROJECT_ROOT / "frontend_revamp" / "app"
ASSET_VERSION = "revamp-021-19"


def test_revamp_preview_is_distinct_from_production_root(client):
    preview = client.get("/revamp-preview")
    production = client.get("/")

    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("text/html")
    assert "data-revamp-preview" in preview.text
    assert "data-run-home" in preview.text
    assert production.status_code == 200
    assert production.content == (PROJECT_ROOT / "templates" / "index.html").read_bytes()
    assert "data-revamp-preview" not in production.text
    assert "/revamp-assets/" not in production.text


def test_revamp_assets_use_an_isolated_namespace(client):
    stylesheet = client.get(f"/revamp-assets/css/foundation.css?v={ASSET_VERSION}")
    module = client.get(f"/revamp-assets/js/app.js?v={ASSET_VERSION}")
    missing = client.get("/revamp-assets/css/does-not-exist.css")

    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert module.status_code == 200
    assert "javascript" in module.headers["content-type"]
    assert missing.status_code == 404


def test_preview_references_only_versioned_revamp_entry_assets(client):
    html = client.get("/revamp-preview").text
    asset_urls = re.findall(r'(?:href|src)="(/[^"]+)"', html)

    assert asset_urls == [
        f"/revamp-assets/css/foundation.css?v={ASSET_VERSION}",
        f"/revamp-assets/js/app.js?v={ASSET_VERSION}",
    ]
    assert "/static/css/" not in html
    assert "/static/js/" not in html


def test_revamp_module_boundaries_exist_and_imports_resolve():
    javascript_root = REVAMP_ROOT / "js"
    expected_modules = {
        "api.js",
        "app.js",
        "auth.js",
        "form-state.js",
        "map.js",
        "navigation.js",
        "run-selection.js",
        "run-home.js",
        "standings.js",
        "theme.js",
        "ui.js",
    }
    assert {path.name for path in javascript_root.glob("*.js")} == expected_modules

    app_source = (javascript_root / "app.js").read_text(encoding="utf-8")
    imports = re.findall(r'from "(\./[^"?]+\.js)\?v=([^"?]+)"', app_source)
    assert {Path(path).name for path, _ in imports} == expected_modules - {"app.js"}
    assert {version for _, version in imports} == {ASSET_VERSION}
    assert all((javascript_root / path.removeprefix("./")).is_file() for path, _ in imports)


def test_foundation_encodes_theme_motion_and_responsive_contracts():
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    theme = (REVAMP_ROOT / "js" / "theme.js").read_text(encoding="utf-8")
    html = (REVAMP_ROOT / "index.html").read_text(encoding="utf-8")

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


def test_run_home_preserves_scoped_data_and_stale_refresh_boundaries():
    javascript_root = REVAMP_ROOT / "js"
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


def test_run_home_has_responsive_content_and_feedback_contracts():
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (REVAMP_ROOT / "index.html").read_text(encoding="utf-8")

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


def test_vendored_foundation_assets_and_licenses_are_present():
    assets = REVAMP_ROOT / "assets"
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
        for name in ("house", "trophy", "plus", "map-trifold", "user", "caret-down", "arrow-clockwise")
    )

    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

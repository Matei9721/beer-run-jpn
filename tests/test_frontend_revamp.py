import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVAMP_ROOT = PROJECT_ROOT / "frontend_revamp" / "app"
ASSET_VERSION = "revamp-072-12"


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
        "account.js",
        "api.js",
        "app.js",
        "auth.js",
        "confirmation.js",
        "form-state.js",
        "invite.js",
        "legal.js",
        "log.js",
        "map.js",
        "navigation.js",
        "run-library.js",
        "run-selection.js",
        "run-home.js",
        "standings.js",
        "system-states.js",
        "theme.js",
        "ui.js",
    }
    assert {path.name for path in javascript_root.glob("*.js")} == expected_modules

    app_source = (javascript_root / "app.js").read_text(encoding="utf-8")
    imports = re.findall(r'from "(\./[^"?]+\.js)\?v=([^"?]+)"', app_source)
    assert {Path(path).name for path, _ in imports} == expected_modules - {"app.js", "confirmation.js"}
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


def test_annotated_ui_cleanup_removes_redundancy_and_keeps_alignment_rules():
    javascript_root = REVAMP_ROOT / "js"
    ui = (javascript_root / "ui.js").read_text(encoding="utf-8")
    standings = (javascript_root / "standings.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    map_module = (javascript_root / "map.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    for copy in (
        "Sign in to add a pour.",
        "Ranked by pure alcohol",
        "Continue logging drinks and switch between your runs.",
        "Welcome back",
        "Current legal terms loaded.",
        "Filter by runner and open a drink without leaving the map.",
    ):
        assert copy not in "\n".join((ui, standings, auth, map_module))

    assert 'top.append(avatar(username), el("strong", "", `Rank ${index + 1}`));' in standings
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
    javascript_root = REVAMP_ROOT / "js"
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    standings = (javascript_root / "standings.js").read_text(encoding="utf-8")
    ui = (javascript_root / "ui.js").read_text(encoding="utf-8")
    html = (REVAMP_ROOT / "index.html").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

    assert "const AUTO_REFRESH_INTERVAL_MS = 30_000;" in app
    assert "window.setInterval" in app
    assert "void runHome.refresh();" in app
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
    javascript_root = REVAMP_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (REVAMP_ROOT / "index.html").read_text(encoding="utf-8")

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
    assert "Open Wrapped" not in library
    assert 'result.status === 401' in home
    assert '[403, 404]' in home
    assert 'beer-run:session-rejected' in home
    rejected_session_handler = home.split("async function recoverFromRejectedSession", 1)[1].split(
        "async function refresh", 1
    )[0]
    assert "removeSelectedRunId" not in rejected_session_handler
    assert "removeSelectedRunId" in home
    assert "firstFallbackRun" in home
    assert "run-switcher-dialog" in html
    assert 'aria-expanded="false"' in html
    assert ".run-quick-switcher" in css
    assert ".quick-switcher-panel" in css
    assert "body.run-switcher-open" in css
    assert "--run-switcher-scrollbar-width" in css
    assert ".run-library-discovery" in css


def test_create_and_manage_run_contracts_are_present():
    javascript_root = REVAMP_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    home = (javascript_root / "run-home.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

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
    javascript_root = REVAMP_ROOT / "js"
    account = (javascript_root / "account.js").read_text(encoding="utf-8")
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    confirmation = (javascript_root / "confirmation.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    map_source = (javascript_root / "map.js").read_text(encoding="utf-8")
    theme = (javascript_root / "theme.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

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
    assert 'map.setView(marker.getLatLng(), Math.max(map.getZoom(), SELECTED_ENTRY_ZOOM)' in map_source
    assert 'markerGroup.zoomToShowLayer(marker, revealMarker)' in map_source
    assert 'markerGroup?.removeLayer?.(marker)' not in map_source
    assert 'window.L.divIcon' not in map_source
    assert 'marker.on("click", () => focusEntry(entry))' in map_source
    assert 'maxZoom: 15, animate: false' in map_source
    assert map_source.count('resizeMap();') >= 3
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
    javascript_root = REVAMP_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    log = (javascript_root / "log.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

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
    assert 'returnTo === "#you" && !runHome.getSnapshot().currentUser' in app
    assert 'closeDestination' in app
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
    javascript_root = REVAMP_ROOT / "js"
    legal = (javascript_root / "legal.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    auth = (javascript_root / "auth.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

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
    javascript_root = REVAMP_ROOT / "js"
    api = (javascript_root / "api.js").read_text(encoding="utf-8")
    app = (javascript_root / "app.js").read_text(encoding="utf-8")
    invite = (javascript_root / "invite.js").read_text(encoding="utf-8")
    library = (javascript_root / "run-library.js").read_text(encoding="utf-8")
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")

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
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    html = (REVAMP_ROOT / "index.html").read_text(encoding="utf-8")
    source = (REVAMP_ROOT / "js" / "map.js").read_text(encoding="utf-8")

    assert "leaflet.markercluster" in html
    assert "leaflet.js" in html
    assert "markerClusterGroup" in source
    assert "const requestedEntryId = entryId ?? sessionStorage.getItem(SELECTED_ENTRY_KEY);" in source
    assert "marker.setZIndexOffset?.(selected ? 1000 : 0);" in source
    assert '"Show all pins"' in source
    assert 'event.key === "Escape"' in source
    assert 'alt: accessibleTitle' in source
    assert "tileerror" in source
    assert "Map tiles are offline" in source
    assert "Photo unavailable" in source
    assert "missing or invalid coordinates" in source
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
    assert "is-fullscreen-fallback" in source
    assert "invalidateSize" in source
    assert "refreshClusters" in source
    assert "Enter full screen map" in source
    assert "Exit full screen map" in source
    assert "map-fullscreen-control__icon--expand" in source
    assert "map-fullscreen-control__icon--collapse" in source
    assert ".map-workspace:fullscreen" in css


def test_log_edit_photo_location_and_success_contracts_are_present():
    css = (REVAMP_ROOT / "css" / "foundation.css").read_text(encoding="utf-8")
    source = (REVAMP_ROOT / "js" / "log.js").read_text(encoding="utf-8")
    api = (REVAMP_ROOT / "js" / "api.js").read_text(encoding="utf-8")

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
        for name in ("house", "trophy", "plus", "map-trifold", "user", "caret-down", "arrow-clockwise", "beer-stein")
    )

    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

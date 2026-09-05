import { createAccountController } from "./account.js?v=revamp-047-10";
import { createApiClient } from "./api.js?v=revamp-047-10";
import { createAuthController, createAuthState } from "./auth.js?v=revamp-047-10";
import { createFormState } from "./form-state.js?v=revamp-047-10";
import { createInviteController } from "./invite.js?v=revamp-047-10";
import { createMapController } from "./map.js?v=revamp-047-10";
import { createLogController } from "./log.js?v=revamp-047-10";
import { bindNavigation } from "./navigation.js?v=revamp-047-10";
import { createRunHomeController } from "./run-home.js?v=revamp-047-10";
import { createRunLibraryController } from "./run-library.js?v=revamp-047-10";
import { createRunSelectionState, removeSelectedRunId } from "./run-selection.js?v=revamp-047-10";
import { createStandingsController } from "./standings.js?v=revamp-047-10";
import { bindThemeControls, createThemeController } from "./theme.js?v=revamp-047-10";
import { bindPreviewFeedback, setSyncStatus } from "./ui.js?v=revamp-047-10";

const services = Object.freeze({
  api: createApiClient(),
  auth: createAuthState(),
  form: createFormState(),
  runs: createRunSelectionState(),
});

const theme = createThemeController();
bindThemeControls(theme, document.querySelector("[data-theme-controls]"));
const runHome = createRunHomeController({
  api: services.api,
  auth: services.auth,
  selection: services.runs,
  root: document,
});
let standings;
let mapController;
let logController;
let runLibrary;
let authController;
let inviteController;
let accountController;
const ensureContentSurface = () => {
  let surface = document.querySelector("[data-run-home]");
  if (surface) return surface;
  surface = document.createElement("div");
  surface.className = "home-content";
  surface.dataset.runHome = "";
  document.querySelector("main")?.replaceChildren(surface);
  return surface;
};
const navigation = bindNavigation(document, { onNavigate: (destination) => {
  if (authController?.isActive()) authController.close({ notify: false });
  if (inviteController?.isActive()) inviteController.dismiss({ notify: false });
  if (destination !== "you") accountController?.hide();
  runLibrary?.hide();
  if (destination === "standings") {
    logController.hide();
    mapController.hide();
    ensureContentSurface();
    standings.showStandings();
  } else if (destination === "map") {
    logController.hide();
    standings.hide();
    mapController.show();
  }
  else if (destination === "log") {
    standings.hide();
    mapController.hide();
    logController.show();
  }
  else if (destination === "you" && !runHome.getSnapshot().currentUser) {
    logController.hide();
    standings.hide();
    mapController.hide();
    history.replaceState(null, "", "#login");
    authController.show("login", { returnTo: "#you" });
  } else if (destination === "you") {
    logController.hide();
    standings.hide();
    mapController.hide();
    accountController.show();
  } else {
    logController.hide();
    standings.hide();
    mapController.hide();
    ensureContentSurface();
    if (destination === "run") runHome.showHome();
  }
} });
standings = createStandingsController({
  root: document,
  api: services.api,
  auth: services.auth,
  getSnapshot: runHome.getSnapshot,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
mapController = createMapController({
  root: document,
  api: services.api,
  auth: services.auth,
  getSnapshot: runHome.getSnapshot,
  refresh: runHome.refresh,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
logController = createLogController({
  root: document,
  api: services.api,
  auth: services.auth,
  formState: services.form,
  getSnapshot: runHome.getSnapshot,
  refresh: runHome.refresh,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
const showRun = () => {
  history.pushState(null, "", "#run");
  navigation.selectDestination("run");
};
const showJoinedRun = ({ joinedRun } = {}) => {
  history.replaceState(null, "", `${location.pathname}#run`);
  navigation.selectDestination("run");
  const status = document.querySelector("[data-sync-status]");
  if (status && joinedRun?.name) status.textContent = `Joined ${joinedRun.name}`;
};
const showLibrary = (view = "library", { push = true } = {}) => {
  runLibrary.closeSwitcher({ restoreFocus: false, immediate: true });
  logController.hide();
  standings.hide();
  mapController.hide();
  navigation.clearDestination();
  if (push) history.pushState(null, "", `#${view === "library" ? "runs" : view}`);
  runLibrary.show(view);
};
const selectedPrimaryDestination = () => (
  document.querySelector(".nav-item[aria-current='page']")?.dataset.destination || "run"
);
const quickSwitchRun = async (run, options) => {
  const destination = selectedPrimaryDestination();
  const result = await runHome.selectRun(run, options);
  const restoredDestination = result?.ok ? destination : "run";
  history.replaceState(null, "", `#${restoredDestination}`);
  navigation.selectDestination(restoredDestination);
  document.querySelector("main")?.focus({ preventScroll: true });
  return result;
};
const reconcileSelectionIdentity = async () => {
  const destination = selectedPrimaryDestination();
  const result = await runHome.initialize();
  if (!runLibrary?.isActive()) {
    const restoredDestination = result?.ok ? destination : "run";
    history.replaceState(null, "", `#${restoredDestination}`);
    navigation.selectDestination(restoredDestination);
  }
  return result;
};
runLibrary = createRunLibraryController({
  root: document,
  api: services.api,
  auth: services.auth,
  getSnapshot: runHome.getSnapshot,
  onSelectRun: runHome.selectRun,
  onQuickSelectRun: quickSwitchRun,
  onIdentityChange: reconcileSelectionIdentity,
  onOpenLibrary: () => showLibrary(),
  onShowRun: showRun,
});
inviteController = createInviteController({
  root: document,
  api: services.api,
  auth: services.auth,
  getSnapshot: runHome.getSnapshot,
  onSelectRun: runHome.selectRun,
  onShowRun: showJoinedRun,
  onDismiss: () => {
    history.replaceState(null, "", `${location.pathname}#run`);
    navigation.selectDestination("run");
  },
});
const restoreAuthDestination = (destination = "#run") => {
  const safeDestination = ["#run", "#standings", "#log", "#map", "#runs", "#create", "#manage", "#you"].includes(destination)
    ? destination
    : destination.startsWith("#invite") ? destination : "#run";
  const isInviteDestination = safeDestination.startsWith("#invite");
  history.replaceState(null, "", safeDestination);
  if (safeDestination === "#invite") {
    navigation.selectDestination("run", { notify: false });
    void inviteController.show();
  }
  else if (safeDestination === "#runs") showLibrary("library", { push: false });
  else if (safeDestination === "#create") showLibrary("create", { push: false });
  else if (safeDestination === "#manage") showLibrary("manage", { push: false });
  else navigation.selectDestination(isInviteDestination ? "run" : safeDestination.slice(1));
  document.querySelector("main")?.focus({ preventScroll: true });
};
authController = createAuthController({
  root: document,
  api: services.api,
  auth: services.auth,
  onAuthenticated: async ({ returnTo }) => {
    ensureContentSurface();
    const result = await reconcileSelectionIdentity();
    restoreAuthDestination(returnTo);
    return result?.data?.identity || runHome.getSnapshot().currentUser;
  },
  onClose: ({ returnTo }) => {
    if (returnTo.startsWith("#invite")) inviteController.cancelAuthContinuation();
    const closeDestination = returnTo === "#you" && !runHome.getSnapshot().currentUser
      ? "#run"
      : returnTo;
    restoreAuthDestination(closeDestination);
  },
});
const resetPrivateSurfaces = () => {
  runLibrary.hide();
  logController.reset();
  standings.reset();
  mapController.reset();
};
const showPublicFallback = async (message) => {
  accountController?.completeSuccess();
  resetPrivateSurfaces();
  ensureContentSurface();
  history.replaceState(null, "", `${location.pathname}#run`);
  const result = await runHome.initialize();
  navigation.selectDestination("run");
  setSyncStatus(document, message);
  return result;
};
accountController = createAccountController({
  root: document,
  api: services.api,
  auth: services.auth,
  theme,
  getSnapshot: runHome.getSnapshot,
  onSignOut: async () => {
    services.auth.removeAccessToken();
    await showPublicFallback("Signed out. Showing the public run.");
  },
  onDeleteAccount: async ({ userId, token, password, confirmation }) => {
    const user = runHome.getSnapshot().currentUser;
    if (!user || user.id !== userId || services.auth.getAccessToken() !== token) {
      return { ok: false, reason: "identity-changed" };
    }
    const result = await services.api.deleteAccount(password, confirmation, token);
    if (!result.ok || result.data?.deleted !== true) return result;
    if (runHome.getSnapshot().currentUser?.id !== userId || services.auth.getAccessToken() !== token) {
      setSyncStatus(document, "The account you confirmed was deleted. Your current browser session was kept.");
      return { ...result, ok: true, committed: true, currentSessionKept: true };
    }
    removeSelectedRunId(user.id);
    inviteController.reset();
    const url = new URL(location.href);
    url.searchParams.delete("invite");
    url.searchParams.delete("run");
    history.replaceState(null, "", `${url.pathname}${url.search}#run`);
    services.auth.removeAccessToken();
    void showPublicFallback("Your account and personal data were deleted.").catch(() => {
      ensureContentSurface();
      history.replaceState(null, "", `${location.pathname}#run`);
      navigation.selectDestination("run");
      setSyncStatus(document, "Your account was deleted. Refresh to reload the public run.");
    });
    return { ...result, committed: true };
  },
  onManageOwnedRun: async (ownedRun) => {
    const result = await services.api.fetchBeerRun(ownedRun.id, services.auth.getAccessToken());
    if (result.status === 401) return { ok: false, sessionRejected: true };
    if (!result.ok || result.data?.current_user_role !== "owner") {
      return {
        ok: false,
        message: [401, 403, 404].includes(result.status)
          ? "That run is no longer owned by this account. Retry the account summary."
          : "That run could not be opened. Try again.",
      };
    }
    await runHome.selectRun(result.data, { persist: true });
    accountController.hide();
    showLibrary("manage");
    return { ok: true };
  },
  onSessionRejected: () => {
    services.auth.removeAccessToken();
    accountController?.hide();
    ensureContentSurface();
    void runHome.initialize();
    history.replaceState(null, "", "#login");
    authController.show("login", {
      returnTo: "#you",
      message: "Your session is no longer valid. Log in again to open your account.",
    });
  },
});
document.addEventListener("beer-run:session-rejected", () => {
  services.auth.removeAccessToken();
  accountController?.hide();
  resetPrivateSurfaces();
  ensureContentSurface();
  void runHome.initialize();
  const destination = ["#login", "#signup"].includes(location.hash) ? "#run" : location.hash || "#run";
  history.replaceState(null, "", "#login");
  authController.show("login", {
    returnTo: destination,
    message: "Your session is no longer valid. Log in again to continue.",
  });
});
document.querySelector("[data-run-switcher]")?.addEventListener("click", () => runLibrary.openSwitcher());
document.addEventListener("beer-run:open-player", (event) => {
  navigation.selectDestination("standings");
  standings.showPlayer(event.detail.username);
});
runHome.subscribe((snapshot) => {
  if (!snapshot.data) {
    standings.reset();
    mapController.reset();
    logController.reset();
    return;
  }
  standings.refresh();
  mapController.refresh();
});
document.addEventListener("click", (event) => {
  const entryLink = event.target.closest("[data-entry-id][data-destination='map']");
  if (!entryLink) return;
  mapController.show(entryLink.dataset.entryId);
});
bindPreviewFeedback(document, { onRefresh: () => (
  runLibrary.isActive() ? runLibrary.refresh() : runHome.refresh()
) });
const restoreDestination = () => {
  if (location.hash === "#login" || location.hash === "#signup") {
    authController.show(location.hash.slice(1), {
      returnTo: inviteController.hasInviteRoute() ? "#invite" : "#run",
    });
    return;
  }
  if (authController.isActive()) authController.close({ notify: false });
  if (location.hash === "#invite") {
    runLibrary.hide();
    logController.hide();
    standings.hide();
    mapController.hide();
    navigation.selectDestination("run", { notify: false });
    void inviteController.show();
    return;
  }
  inviteController.hide();
  const match = location.hash.match(/^#standings\/(.+)$/);
  if (location.hash === "#runs") showLibrary("library", { push: false });
  else if (location.hash === "#create") showLibrary("create", { push: false });
  else if (location.hash === "#manage") showLibrary("manage", { push: false });
  else if (match) {
    navigation.selectDestination("standings");
    standings.showPlayer(decodeURIComponent(match[1]), false);
  } else if (location.hash === "#standings") navigation.selectDestination("standings");
  else if (location.hash === "#map") navigation.selectDestination("map");
  else if (location.hash === "#log") navigation.selectDestination("log");
  else if (location.hash === "#you") navigation.selectDestination("you");
  else navigation.selectDestination("run");
};
window.addEventListener("popstate", restoreDestination);
const reconcileIdentity = async () => {
  const inviteWasActive = inviteController.isActive();
  await reconcileSelectionIdentity();
  if (inviteWasActive && location.hash === "#invite") {
    await inviteController.show();
    return;
  }
  if (runLibrary.isActive()) await runLibrary.refresh();
  if (runLibrary.isSwitcherOpen()) await runLibrary.refreshSwitcher();
  if (location.hash === "#you") navigation.selectDestination("you");
};
window.addEventListener("storage", (event) => {
  if (event.key === "access_token") void reconcileIdentity();
});
document.addEventListener("beer-run:auth-changed", () => void reconcileIdentity());
void (async () => {
  if (inviteController.hasInviteRoute() && !["#login", "#signup"].includes(location.hash)) {
    history.replaceState(null, "", `${location.pathname}${location.search}#invite`);
  }
  const destinationBeforeValidation = ["#login", "#signup"].includes(location.hash)
    ? (inviteController.hasInviteRoute() ? "#invite" : "#run")
    : location.hash || "#run";
  const session = await authController.validateStoredSession();
  await runHome.initialize();
  if (session.status === "stale") {
    history.replaceState(null, "", "#login");
    authController.show("login", {
      returnTo: destinationBeforeValidation,
      message: "Your session is no longer valid. Log in again to continue.",
    });
    return;
  }
  restoreDestination();
})();

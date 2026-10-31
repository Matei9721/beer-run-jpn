import {
  removeSharedRunFromUrl,
  readSelectedRunId,
  removeSelectedRunId,
  saveSelectedRunId,
  sharedRunFromUrl,
} from "./run-selection.js?v=beerrun-105-tour-end";
import { clearSystemNotice, setSystemNotice } from "./system-states.js?v=beerrun-126-wait-indicators";
import { createRunDiscoveryController } from "./run-discovery.js?v=beerrun-126-wait-indicators";
import {
  renderRunHome,
  renderRunHomeError,
  renderRunHomeLoading,
  renderRunHomeUnavailable,
  setRefreshPending,
  setSyncStatus,
  updateRunSwitcher,
} from "./ui.js?v=beerrun-126-wait-indicators";

function sameRun(left, right) {
  return left && right && Number(left.id) === Number(right.id);
}

function sameSnapshotData(left, right) {
  if (!left || !right) return false;
  return JSON.stringify(left) === JSON.stringify(right);
}

function failureMessage(result) {
  if (result?.network) return "Connection unavailable. Refresh to try again.";
  return "This run could not be loaded. Refresh to try again.";
}

function formatSyncTime(value) {
  return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function createRunHomeController({
  api,
  auth,
  selection,
  root = document,
  storage = localStorage,
  locationLike = location,
  historyLike = history,
  now = () => new Date(),
}) {
  let currentUser = null;
  let currentRun = null;
  let lastData = null;
  let contextGeneration = 0;
  let refreshGeneration = 0;
  let refreshController = null;
  let resolutionController = null;
  let retainedRefreshError = false;
  const listeners = new Set();
  const discovery = createRunDiscoveryController({ root, api, onSelectRun: selectRun });

  function ensureHomeTarget() {
    let target = root.querySelector("[data-run-home]");
    if (target) return target;
    target = document.createElement("div");
    target.className = "home-content";
    target.dataset.runHome = "";
    target.dataset.homeState = "loading";
    root.querySelector("main")?.replaceChildren(target);
    return target;
  }

  function notify() {
    listeners.forEach((listener) => listener({ currentRun, currentUser, data: lastData }));
  }

  function invalidateRefreshWork() {
    refreshGeneration += 1;
    refreshController?.abort();
    resolutionController?.abort();
    refreshController = null;
    resolutionController = null;
  }

  async function resolveCurrentRun(signal, sessionRun = null) {
    let token = auth.getAccessToken();
    let identity = null;
    let sessionRejected = false;

    if (token) {
      const identityResult = await api.fetchCurrentUser(token, signal);
      if (identityResult.ok) identity = identityResult.data;
      else if (identityResult.status === 401) {
        auth.removeAccessToken();
        token = null;
        sessionRejected = true;
      }
    }

    const shared = sharedRunFromUrl(locationLike);
    if (shared.present && !shared.valid) removeSharedRunFromUrl(locationLike, historyLike);
    if (shared.valid) {
      const sharedResult = await api.fetchBeerRun(shared.id, identity ? token : null, signal);
      if (sharedResult.ok) {
        return { run: sharedResult.data, identity, reason: "ready", sessionRejected, shared: true };
      }
      if ([403, 404].includes(sharedResult.status)) {
        removeSharedRunFromUrl(locationLike, historyLike);
      }
    }

    if (identity) {
      const storedRunId = readSelectedRunId(identity.id, storage);
      const runsResult = await api.fetchMyBeerRuns(token, signal);
      let selected = runsResult.ok && storedRunId
        ? runsResult.data.find((run) => Number(run.id) === Number(storedRunId))
        : null;

      if (!selected && storedRunId) {
        const storedResult = await api.fetchBeerRun(storedRunId, token, signal);
        if (storedResult.ok) selected = storedResult.data;
        else if ([403, 404].includes(storedResult.status)) removeSelectedRunId(identity.id, storage);
      }

      if (selected) return { run: selected, identity, reason: "ready", sessionRejected };
    }

    if (sessionRun?.is_public) {
      const sessionResult = await api.fetchBeerRun(sessionRun.id, identity ? token : null, signal);
      if (sessionResult.ok) return { run: sessionResult.data, identity, reason: "ready", sessionRejected };
    }

    return {
      run: null,
      identity,
      reason: "choose",
      sessionRejected,
    };
  }

  function currentRequest(run, context, request) {
    return context === contextGeneration
      && request === refreshGeneration
      && sameRun(run, currentRun)
      && !refreshController?.signal.aborted;
  }

  async function recoverFromAccessLoss(run, context) {
    if (context !== contextGeneration || !sameRun(run, currentRun)) return { stale: true };
    if (currentUser) removeSelectedRunId(currentUser.id, storage);
    invalidateRefreshWork();
    contextGeneration += 1;
    currentRun = null;
    lastData = null;
    retainedRefreshError = false;
    selection.clear();
    notify();
    renderRunHomeUnavailable(root, {
      title: "This run is no longer available",
      message: "Choose another run to continue.",
    });
    setSyncStatus(root, "Run unavailable. Choose another run.");
    return initialize();
  }

  async function recoverFromRejectedSession(run, context) {
    if (context !== contextGeneration || !sameRun(run, currentRun)) return { stale: true };
    auth.removeAccessToken();
    invalidateRefreshWork();
    contextGeneration += 1;
    currentUser = null;
    currentRun = null;
    lastData = null;
    retainedRefreshError = false;
    selection.clear();
    notify();
    const result = await initialize();
    root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
    return result;
  }

  async function refresh({ initial = false, context = contextGeneration, run = currentRun } = {}) {
    if (!run) return discovery.refresh();
    const request = ++refreshGeneration;
    refreshController?.abort();
    refreshController = new AbortController();
    const signal = refreshController.signal;
    const token = auth.getAccessToken();

    setRefreshPending(root, true);
    setSyncStatus(root, initial ? "Loading run data" : "Syncing run data");
    const [runResult, leaderboardResult, entriesResult] = await Promise.all([
      api.fetchBeerRun(run.id, token, signal),
      api.fetchLeaderboard(run.id, token, signal),
      api.fetchEntries(run.id, token, signal),
    ]);

    if (!currentRequest(run, context, request)) return { stale: true };
    refreshController = null;
    setRefreshPending(root, false);

    const results = [runResult, leaderboardResult, entriesResult];
    if (results.some((result) => result.status === 401)) {
      return recoverFromRejectedSession(run, context);
    }
    if (results.some((result) => [403, 404].includes(result.status))) {
      return recoverFromAccessLoss(run, context);
    }

    if (!results.every((result) => result.ok)) {
      const failedResult = results.find((result) => !result.ok);
      const message = failedResult?.network
        ? "Connection unavailable. Showing the latest available data."
        : "The latest run update could not be loaded. Showing the last saved view.";
      if (lastData) {
        renderRunHome(root, { ...lastData, errorMessage: message, now: now() });
        retainedRefreshError = true;
        setSystemNotice(root, {
          kind: failedResult?.network ? "offline" : "error",
          title: failedResult?.network ? "Connection paused" : "Refresh incomplete",
          message,
        });
      } else {
        renderRunHomeError(root, { run, identity: currentUser, message: failureMessage(failedResult) });
      }
      setSyncStatus(root, message);
      return { ok: false, retained: Boolean(lastData) };
    }

    const nextData = {
      run: runResult.data,
      identity: currentUser,
      leaderboard: Array.isArray(leaderboardResult.data) ? leaderboardResult.data : [],
      entries: Array.isArray(entriesResult.data) ? entriesResult.data : [],
    };
    const dataChanged = !sameSnapshotData(lastData, nextData);
    currentRun = nextData.run;
    selection.selectRun(currentRun);
    lastData = nextData;
    const refreshedAt = now();
    const presentationChanged = dataChanged || retainedRefreshError;
    if (presentationChanged) renderRunHome(root, { ...lastData, now: refreshedAt });
    retainedRefreshError = false;
    if (presentationChanged) notify();
    clearSystemNotice(root);
    setSyncStatus(root, `Synced ${formatSyncTime(refreshedAt)}`);
    return { ok: true, data: lastData, changed: dataChanged };
  }

  async function initialize() {
    const sessionRun = currentRun?.is_public ? currentRun : null;
    discovery.hide();
    invalidateRefreshWork();
    const context = ++contextGeneration;
    currentUser = null;
    currentRun = null;
    lastData = null;
    retainedRefreshError = false;
    selection.clear();
    notify();
    renderRunHomeLoading(root);
    setRefreshPending(root, false);
    setSyncStatus(root, "Loading run data");

    resolutionController = new AbortController();
    const resolved = await resolveCurrentRun(resolutionController.signal, sessionRun);
    if (context !== contextGeneration) return { stale: true };
    resolutionController = null;
    currentUser = resolved.identity;
    if (!resolved.run) {
      notify();
      root.dispatchEvent(new CustomEvent("beer-run:selection-required"));
      if (!discovery.isActive()) discovery.show();
      setRefreshPending(root, false);
      if (resolved.sessionRejected) root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
      return resolved;
    }

    currentRun = resolved.run;
    selection.selectRun(currentRun);
    if (resolved.shared && currentUser) saveSelectedRunId(currentUser.id, currentRun.id, storage);
    const result = await refresh({ initial: true, context, run: currentRun });
    if (resolved.sessionRejected) root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
    return result;
  }

  function selectRun(run, { persist = false } = {}) {
    if (!run) return refresh({ run: currentRun });
    discovery.hide();
    if (sameRun(run, currentRun)) {
      currentRun = { ...currentRun, ...run };
      selection.selectRun(currentRun);
      if (persist && currentUser) saveSelectedRunId(currentUser.id, currentRun.id, storage);
      if (persist) removeSharedRunFromUrl(locationLike, historyLike);
      updateRunSwitcher(root, currentRun, currentUser);
      notify();
      return refresh({ run: currentRun });
    }
    invalidateRefreshWork();
    contextGeneration += 1;
    currentRun = run;
    lastData = null;
    retainedRefreshError = false;
    selection.selectRun(run);
    if (persist && currentUser) saveSelectedRunId(currentUser.id, run.id, storage);
    if (persist) removeSharedRunFromUrl(locationLike, historyLike);
    notify();
    renderRunHomeLoading(root);
    setSyncStatus(root, `Loading ${run.name}`);
    return refresh({ initial: true, context: contextGeneration, run });
  }

  return {
    initialize,
    refresh: (options = {}) => currentRun ? refresh() : discovery.refresh(options),
    selectRun,
    hideDiscovery: discovery.hide,
    showDiscovery: () => {
      invalidateRefreshWork();
      contextGeneration += 1;
      currentRun = null;
      lastData = null;
      selection.clear();
      removeSharedRunFromUrl(locationLike, historyLike);
      notify();
      ensureHomeTarget();
      return discovery.showOverview();
    },
    showHome: () => {
      ensureHomeTarget();
      if (lastData) renderRunHome(root, { ...lastData, now: now() });
      else if (!currentRun) {
        if (!discovery.isActive()) discovery.show();
      }
      else renderRunHomeLoading(root);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot: () => ({ currentRun, currentUser, data: lastData, contextGeneration, refreshGeneration }),
  };
}

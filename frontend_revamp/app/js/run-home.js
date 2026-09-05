import {
  DEFAULT_RUN_NAME,
  readSelectedRunId,
  removeSelectedRunId,
  saveSelectedRunId,
} from "./run-selection.js?v=revamp-025-12";
import { clearSystemNotice, setSystemNotice } from "./system-states.js?v=revamp-056-11";
import {
  renderRunHome,
  renderRunHomeError,
  renderRunHomeLoading,
  renderRunHomeUnavailable,
  setRefreshPending,
  setSyncStatus,
  updateRunSwitcher,
} from "./ui.js?v=revamp-056-11";

function sameRun(left, right) {
  return left && right && Number(left.id) === Number(right.id);
}

function firstFallbackRun(runs) {
  return runs.find((run) => !run.is_public) || runs.find((run) => run.is_public) || null;
}

function failureMessage(result) {
  if (result?.network) return "Connection unavailable. Refresh to try again.";
  return "This run could not be loaded. Refresh to try again.";
}

export function createRunHomeController({ api, auth, selection, root = document, storage = localStorage, now = () => new Date() }) {
  let currentUser = null;
  let currentRun = null;
  let lastData = null;
  let contextGeneration = 0;
  let refreshGeneration = 0;
  let refreshController = null;
  let resolutionController = null;
  const listeners = new Set();

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

  async function resolveCurrentRun(signal) {
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
      const fallback = runsResult.ok ? firstFallbackRun(runsResult.data) : null;
      if (fallback) return { run: fallback, identity, reason: "ready", sessionRejected };
    }

    const fallbackResult = await api.findPublicBeerRunByName(DEFAULT_RUN_NAME, identity ? token : null, signal);
    if (fallbackResult.ok && fallbackResult.data.length) {
      return { run: fallbackResult.data[0], identity, reason: "ready", sessionRejected };
    }
    return {
      run: null,
      identity,
      reason: fallbackResult.network ? "network" : "missing",
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
    selection.clear();
    notify();
    renderRunHomeUnavailable(root, {
      title: "This run is no longer available",
      message: "Choosing the next public run now.",
    });
    setSyncStatus(root, "Run unavailable. Choosing another run.");
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
    selection.clear();
    notify();
    const result = await initialize();
    root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
    return result;
  }

  async function refresh({ initial = false, context = contextGeneration, run = currentRun } = {}) {
    if (!run) return initialize();
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

    currentRun = runResult.data;
    selection.selectRun(currentRun);
    lastData = {
      run: currentRun,
      identity: currentUser,
      leaderboard: Array.isArray(leaderboardResult.data) ? leaderboardResult.data : [],
      entries: Array.isArray(entriesResult.data) ? entriesResult.data : [],
    };
    renderRunHome(root, { ...lastData, now: now() });
    notify();
    clearSystemNotice(root);
    setSyncStatus(root, "Synced just now");
    return { ok: true, data: lastData };
  }

  async function initialize() {
    invalidateRefreshWork();
    const context = ++contextGeneration;
    currentUser = null;
    currentRun = null;
    lastData = null;
    selection.clear();
    notify();
    renderRunHomeLoading(root);
    setRefreshPending(root, false);
    setSyncStatus(root, "Loading run data");

    resolutionController = new AbortController();
    const resolved = await resolveCurrentRun(resolutionController.signal);
    if (context !== contextGeneration) return { stale: true };
    resolutionController = null;
    currentUser = resolved.identity;
    if (!resolved.run) {
      renderRunHomeUnavailable(root, {
        title: resolved.reason === "network" ? "Connection unavailable" : "No run available",
        message: resolved.reason === "network"
          ? "BeerRun could not reach the run service. Use Refresh to try again."
          : "The public BeerRunJPN run is not available right now.",
        retry: resolved.reason === "network",
      });
      setRefreshPending(root, false);
      setSyncStatus(root, resolved.reason === "network" ? "Connection unavailable" : "No run available");
      if (resolved.sessionRejected) root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
      return resolved;
    }

    currentRun = resolved.run;
    selection.selectRun(currentRun);
    const result = await refresh({ initial: true, context, run: currentRun });
    if (resolved.sessionRejected) root.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
    return result;
  }

  function selectRun(run, { persist = false } = {}) {
    if (!run) return refresh({ run: currentRun });
    if (sameRun(run, currentRun)) {
      currentRun = { ...currentRun, ...run };
      selection.selectRun(currentRun);
      if (persist && currentUser) saveSelectedRunId(currentUser.id, currentRun.id, storage);
      updateRunSwitcher(root, currentRun, currentUser);
      notify();
      return refresh({ run: currentRun });
    }
    invalidateRefreshWork();
    contextGeneration += 1;
    currentRun = run;
    lastData = null;
    selection.selectRun(run);
    if (persist && currentUser) saveSelectedRunId(currentUser.id, run.id, storage);
    notify();
    renderRunHomeLoading(root);
    setSyncStatus(root, `Loading ${run.name}`);
    return refresh({ initial: true, context: contextGeneration, run });
  }

  return {
    initialize,
    refresh: () => refresh(),
    selectRun,
    showHome: () => {
      ensureHomeTarget();
      if (lastData) renderRunHome(root, { ...lastData, now: now() });
      else renderRunHomeLoading(root);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot: () => ({ currentRun, currentUser, data: lastData, contextGeneration, refreshGeneration }),
  };
}

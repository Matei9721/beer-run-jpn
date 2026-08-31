import {
  DEFAULT_RUN_NAME,
  readSelectedRunId,
  removeSelectedRunId,
} from "./run-selection.js?v=revamp-020-7";
import {
  renderRunHome,
  renderRunHomeError,
  renderRunHomeLoading,
  renderRunHomeUnavailable,
  setRefreshPending,
  setSyncStatus,
} from "./ui.js?v=revamp-020-7";

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

  function invalidateRefreshWork() {
    refreshGeneration += 1;
    refreshController?.abort();
    refreshController = null;
  }

  async function resolveCurrentRun(signal) {
    const token = auth.getAccessToken();
    let identity = null;

    if (token) {
      const identityResult = await api.fetchCurrentUser(token, signal);
      if (identityResult.ok) identity = identityResult.data;
    }

    if (identity) {
      const runsResult = await api.fetchBeerRuns(token, signal);
      if (runsResult.ok) {
        const storedRunId = readSelectedRunId(identity.id, storage);
        let selected = storedRunId
          ? runsResult.data.find((run) => Number(run.id) === Number(storedRunId))
          : null;

        if (!selected && storedRunId) {
          const storedResult = await api.fetchBeerRun(storedRunId, token, signal);
          if (storedResult.ok) selected = storedResult.data;
          else if (storedResult.status === 404) removeSelectedRunId(identity.id, storage);
        }

        if (selected) return { run: selected, identity, reason: "ready" };
        const fallback = firstFallbackRun(runsResult.data);
        if (fallback) return { run: fallback, identity, reason: "ready" };
      }
    }

    const fallbackResult = await api.findPublicBeerRunByName(DEFAULT_RUN_NAME, identity ? token : null, signal);
    if (fallbackResult.ok && fallbackResult.data.length) {
      return { run: fallbackResult.data[0], identity, reason: "ready" };
    }
    return {
      run: null,
      identity,
      reason: fallbackResult.network ? "network" : "missing",
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
    renderRunHomeUnavailable(root, {
      title: "This run is no longer available",
      message: "Choosing the next public run now.",
    });
    setSyncStatus(root, "Run unavailable. Choosing another run.");
    return initialize();
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
    if (results.some((result) => result.status === 404)) {
      return recoverFromAccessLoss(run, context);
    }

    if (!results.every((result) => result.ok)) {
      const message = results.find((result) => !result.ok)?.network
        ? "Connection unavailable. Showing the latest available data."
        : "The latest run update could not be loaded. Showing the last saved view.";
      if (lastData) {
        renderRunHome(root, { ...lastData, errorMessage: message, now: now() });
      } else {
        renderRunHomeError(root, { run, identity: currentUser, message: failureMessage(results.find((result) => !result.ok)) });
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
    renderRunHomeLoading(root);
    setRefreshPending(root, false);
    setSyncStatus(root, "Loading run data");

    const resolved = await resolveCurrentRun();
    if (context !== contextGeneration) return { stale: true };
    currentUser = resolved.identity;
    if (!resolved.run) {
      renderRunHomeUnavailable(root, {
        title: resolved.reason === "network" ? "Connection unavailable" : "No run available",
        message: resolved.reason === "network"
          ? "BeerRun could not reach the run service. Use Refresh to try again."
          : "The public BeerRunJPN run is not available right now.",
      });
      setRefreshPending(root, false);
      setSyncStatus(root, resolved.reason === "network" ? "Connection unavailable" : "No run available");
      return resolved;
    }

    currentRun = resolved.run;
    selection.selectRun(currentRun);
    return refresh({ initial: true, context, run: currentRun });
  }

  function selectRun(run) {
    if (!run || sameRun(run, currentRun)) return refresh({ run: currentRun });
    invalidateRefreshWork();
    contextGeneration += 1;
    currentRun = run;
    lastData = null;
    selection.selectRun(run);
    renderRunHomeLoading(root);
    setSyncStatus(root, `Loading ${run.name}`);
    return refresh({ initial: true, context: contextGeneration, run });
  }

  return {
    initialize,
    refresh: () => refresh(),
    selectRun,
    getSnapshot: () => ({ currentRun, currentUser, data: lastData, contextGeneration, refreshGeneration }),
  };
}

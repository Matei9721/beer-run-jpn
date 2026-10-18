export const SELECTED_RUN_STORAGE_PREFIX = "beerRunJpn.selectedRun.user.";
const RUN_ID_PATTERN = /^[1-9]\d*$/;

export function sharedRunFromUrl(locationLike = location) {
  const url = new URL(locationLike.href);
  const values = url.searchParams.getAll("run");
  if (!values.length) return { present: false, valid: false, id: null };
  if (values.length !== 1 || !RUN_ID_PATTERN.test(values[0])) {
    return { present: true, valid: false, id: null };
  }
  const id = Number(values[0]);
  return Number.isSafeInteger(id) && id > 0
    ? { present: true, valid: true, id }
    : { present: true, valid: false, id: null };
}

export function removeSharedRunFromUrl(locationLike = location, historyLike = history) {
  const url = new URL(locationLike.href);
  if (!url.searchParams.has("run")) return false;
  url.searchParams.delete("run");
  historyLike.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  return true;
}

export function buildRunShareUrl(runId, locationLike = location) {
  const id = Number(runId);
  if (!Number.isSafeInteger(id) || id <= 0) return null;
  const url = new URL(locationLike.href);
  url.searchParams.delete("invite");
  url.searchParams.delete("run");
  url.searchParams.set("run", String(id));
  return url.href;
}

export function selectedRunStorageKey(userId) {
  return `${SELECTED_RUN_STORAGE_PREFIX}${userId}`;
}

export function readSelectedRunId(userId, storage = localStorage) {
  return storage.getItem(selectedRunStorageKey(userId));
}

export function saveSelectedRunId(userId, beerRunId, storage = localStorage) {
  storage.setItem(selectedRunStorageKey(userId), String(beerRunId));
}

export function removeSelectedRunId(userId, storage = localStorage) {
  storage.removeItem(selectedRunStorageKey(userId));
}

export function createRunSelectionState(initialRun = null) {
  let selectedRun = initialRun;
  let generation = 0;

  return {
    getSelectedRun: () => selectedRun,
    getGeneration: () => generation,
    selectRun(run) {
      if (Number(selectedRun?.id) !== Number(run?.id)) generation += 1;
      selectedRun = run;
      return selectedRun;
    },
    clear() {
      if (selectedRun !== null) generation += 1;
      selectedRun = null;
    },
  };
}

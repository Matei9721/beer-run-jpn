export const DEFAULT_RUN_NAME = "BeerRunJPN";
export const SELECTED_RUN_STORAGE_PREFIX = "beerRunJpn.selectedRun.user.";

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

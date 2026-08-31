export function createRunSelectionState(initialRun = null) {
  let selectedRun = initialRun;
  return {
    getSelectedRun: () => selectedRun,
    selectRun(run) { selectedRun = run; },
    clear() { selectedRun = null; },
  };
}

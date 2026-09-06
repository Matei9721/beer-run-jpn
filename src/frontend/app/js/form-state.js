export function createFormState(initialValues = {}) {
  let values = { ...initialValues };
  let pending = false;
  return {
    getValues: () => ({ ...values }),
    update(nextValues) { values = { ...values, ...nextValues }; },
    isPending: () => pending,
    setPending(nextPending) { pending = Boolean(nextPending); },
    reset() { values = { ...initialValues }; pending = false; },
  };
}

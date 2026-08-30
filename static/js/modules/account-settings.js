const CONFIRMATION = 'DELETE MY ACCOUNT';

function nonNegativeCount(value) {
    const count = Number(value);
    return Number.isInteger(count) && count >= 0 ? count : 0;
}

function ownedRunsFrom(summary) {
    return Array.isArray(summary?.owned_runs)
        ? summary.owned_runs.filter(run => run && Number.isInteger(Number(run.id)) && typeof run.name === 'string')
        : [];
}

function failureMessage(result) {
    const detail = result?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail.message === 'string' && detail.message) return detail.message;
    if (result?.status === 401) return 'Your session is no longer valid. Log in again before retrying.';
    if (result?.status === 422) return 'Check your password and type the confirmation exactly as shown.';
    if (result?.network) return 'Connection unavailable. Nothing was deleted; check your connection and try again.';
    return 'Your account could not be deleted. Nothing was removed; try again.';
}

export function createAccountSettings({ onFetchSummary, onDelete, onManageOwnedRun }) {
    const modal = document.getElementById('account-settings-modal');
    const dialog = document.getElementById('account-settings-dialog');
    const close = document.getElementById('close-account-settings');
    const status = document.getElementById('account-settings-status');
    const error = document.getElementById('account-settings-error');
    const summaryRoot = document.getElementById('account-deletion-summary');
    const entryCount = document.getElementById('account-entry-count');
    const membershipCount = document.getElementById('account-membership-count');
    const ownedRunCount = document.getElementById('account-owned-run-count');
    const blocker = document.getElementById('account-owned-runs-blocker');
    const ownedRunsList = document.getElementById('account-owned-runs-list');
    const form = document.getElementById('delete-account-form');
    const password = document.getElementById('delete-account-password');
    const confirmation = document.getElementById('delete-account-confirmation');
    const cancel = document.getElementById('cancel-delete-account');
    const submit = document.getElementById('confirm-delete-account');

    let open = false;
    let pending = false;
    let blocked = false;
    let generation = 0;
    let controller = null;
    let returnFocus = null;

    function updateSubmit() {
        submit.disabled = pending || blocked || !password.value || confirmation.value !== CONFIRMATION;
    }

    function setPending(value, message = '') {
        pending = value;
        close.disabled = value;
        cancel.disabled = value;
        password.disabled = value;
        confirmation.disabled = value;
        submit.textContent = value ? 'Deleting account…' : 'Delete my account';
        status.textContent = message;
        updateSubmit();
    }

    function clearFeedback() {
        status.textContent = '';
        error.textContent = '';
    }

    function renderSummary(summary) {
        const ownedRuns = ownedRunsFrom(summary);
        const reportedOwnedCount = summary?.owned_run_count ?? summary?.owned_runs_count;
        entryCount.textContent = String(nonNegativeCount(summary?.entry_count ?? summary?.entries_count));
        membershipCount.textContent = String(nonNegativeCount(summary?.membership_count ?? summary?.memberships_count));
        ownedRunCount.textContent = String(nonNegativeCount(reportedOwnedCount ?? ownedRuns.length));
        blocked = ownedRuns.length > 0;
        blocker.hidden = !blocked;
        ownedRunsList.replaceChildren();
        for (const run of ownedRuns) {
            const item = document.createElement('li');
            const name = document.createElement('span');
            const manage = document.createElement('button');
            name.textContent = run.name;
            manage.type = 'button';
            manage.className = 'account-owned-run-action';
            manage.textContent = 'Manage run';
            manage.addEventListener('click', () => onManageOwnedRun?.(run));
            item.append(name, manage);
            ownedRunsList.append(item);
        }
        form.hidden = blocked;
        summaryRoot.hidden = false;
        updateSubmit();
    }

    async function loadSummary() {
        const acceptedGeneration = generation;
        controller = new AbortController();
        status.textContent = 'Loading account summary…';
        error.textContent = '';
        summaryRoot.hidden = true;
        const result = await onFetchSummary(controller.signal);
        if (!open || acceptedGeneration !== generation) return;
        controller = null;
        status.textContent = '';
        if (!result?.ok) {
            error.textContent = result?.status === 401
                ? 'Your session is no longer valid. Close account settings and log in again.'
                : (result?.network
                    ? 'Connection unavailable. Your account summary could not be loaded; close and try again.'
                    : 'Your account summary could not be loaded. Close and try again.');
            return;
        }
        renderSummary(result.data || {});
    }

    function dismiss({ restoreFocus = true } = {}) {
        if (!open || pending) return;
        generation += 1;
        controller?.abort();
        controller = null;
        open = false;
        modal.hidden = true;
        document.body.classList.remove('account-settings-open');
        form.reset();
        blocked = false;
        summaryRoot.hidden = true;
        ownedRunsList.replaceChildren();
        clearFeedback();
        updateSubmit();
        if (restoreFocus && returnFocus?.isConnected) returnFocus.focus();
        returnFocus = null;
    }

    function focusableElements() {
        return [...dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), [href]')]
            .filter(element => !element.hidden && element.offsetParent !== null);
    }

    function onKeyDown(event) {
        if (!open) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            dismiss();
            return;
        }
        if (event.key !== 'Tab') return;
        const elements = focusableElements();
        if (!elements.length) {
            event.preventDefault();
            dialog.focus();
            return;
        }
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    async function submitDeletion(event) {
        event.preventDefault();
        if (pending || blocked || !password.value || confirmation.value !== CONFIRMATION) return;
        clearFeedback();
        setPending(true, 'Deleting your account and personal data…');
        const acceptedGeneration = generation;
        controller = new AbortController();
        const result = await onDelete(password.value, confirmation.value, controller.signal);
        if (!open || acceptedGeneration !== generation) return;
        controller = null;
        if (result?.ok && result.data?.deleted === true) return;

        setPending(false);
        error.textContent = failureMessage(result);
        const conflictRuns = result?.status === 409 ? ownedRunsFrom(result.detail) : [];
        if (conflictRuns.length) {
            renderSummary({
                entry_count: entryCount.textContent,
                membership_count: membershipCount.textContent,
                owned_runs: conflictRuns,
            });
            status.textContent = 'Ownership changed. Resolve these runs before trying again.';
            return;
        }
        password.focus();
    }

    close.addEventListener('click', () => dismiss());
    cancel.addEventListener('click', () => dismiss());
    modal.addEventListener('click', event => {
        if (event.target === modal) dismiss();
    });
    dialog.addEventListener('keydown', onKeyDown);
    password.addEventListener('input', updateSubmit);
    confirmation.addEventListener('input', updateSubmit);
    form.addEventListener('submit', submitDeletion);

    function reset() {
        generation += 1;
        controller?.abort();
        controller = null;
        pending = false;
        close.disabled = false;
        cancel.disabled = false;
        password.disabled = false;
        confirmation.disabled = false;
        submit.textContent = 'Delete my account';
        open = false;
        modal.hidden = true;
        document.body.classList.remove('account-settings-open');
        form.reset();
        summaryRoot.hidden = true;
        ownedRunsList.replaceChildren();
        clearFeedback();
        updateSubmit();
        returnFocus = null;
    }

    return {
        open() {
            if (open) return;
            open = true;
            generation += 1;
            returnFocus = document.activeElement;
            form.reset();
            blocked = false;
            clearFeedback();
            updateSubmit();
            modal.hidden = false;
            document.body.classList.add('account-settings-open');
            close.focus();
            void loadSummary();
        },
        dismiss,
        reset,
        completeSuccess: reset,
    };
}

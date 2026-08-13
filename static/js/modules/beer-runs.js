const STORAGE_PREFIX = 'beerRunJpn.selectedRun.user.';

export function selectedRunStorageKey(userId) {
    return `${STORAGE_PREFIX}${userId}`;
}

export function readSelectedRunId(userId) {
    return localStorage.getItem(selectedRunStorageKey(userId));
}

export function saveSelectedRunId(userId, beerRunId) {
    localStorage.setItem(selectedRunStorageKey(userId), String(beerRunId));
}

export function removeSelectedRunId(userId) {
    localStorage.removeItem(selectedRunStorageKey(userId));
}

function runButton(run, currentRunId, selectRun) {
    const isCurrent = Number(run.id) === Number(currentRunId);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'run-choice';
    button.classList.toggle('selected', isCurrent);
    button.classList.toggle(run.is_public ? 'public-run' : 'private-run');
    button.setAttribute('aria-pressed', String(isCurrent));
    if (isCurrent) button.setAttribute('aria-current', 'true');
    button.addEventListener('click', () => selectRun(run));

    const initial = document.createElement('span');
    initial.className = 'run-choice-initial';
    initial.setAttribute('aria-hidden', 'true');
    initial.textContent = (run.name || '?').trim().slice(0, 1).toUpperCase();
    button.appendChild(initial);

    const copy = document.createElement('span');
    copy.className = 'run-choice-copy';
    const heading = document.createElement('span');
    heading.className = 'run-choice-heading';

    const name = document.createElement('span');
    name.className = 'run-choice-name';
    name.textContent = run.name;
    heading.appendChild(name);

    const badge = document.createElement('span');
    badge.className = 'run-choice-badge';
    badge.textContent = isCurrent ? 'Current' : (run.is_public ? 'Public' : 'Private');
    heading.appendChild(badge);
    copy.appendChild(heading);

    const details = document.createElement('span');
    details.className = 'run-choice-details';
    const role = run.current_user_role ? ` \u00b7 ${run.current_user_role}` : '';
    details.textContent = `${run.member_count} member${run.member_count === 1 ? '' : 's'}${role}`;
    copy.appendChild(details);
    button.appendChild(copy);

    const arrow = document.createElement('span');
    arrow.className = 'run-choice-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '\u203a';
    button.appendChild(arrow);
    return button;
}

export function createBeerRunPicker({ onSelectRun, onSearchPublicRuns, onShareRun }) {
    const trigger = document.getElementById('beer-run-trigger');
    const triggerName = document.getElementById('beer-run-trigger-name');
    const triggerMeta = document.getElementById('beer-run-trigger-meta');
    const dialog = document.getElementById('beer-run-picker');
    const sheet = document.getElementById('beer-run-picker-sheet');
    const closeButton = document.getElementById('close-beer-run-picker');
    const status = document.getElementById('beer-run-picker-status');
    const currentSummary = document.getElementById('beer-run-picker-current');
    const currentSummaryName = document.getElementById('beer-run-picker-current-name');
    const shareButton = document.getElementById('share-beer-run');
    const membershipSection = document.getElementById('beer-run-members-section');
    const memberships = document.getElementById('beer-run-members');
    const searchInput = document.getElementById('public-run-search');
    const searchStatus = document.getElementById('public-run-search-status');
    const searchResults = document.getElementById('public-run-results');

    let currentRun = null;
    let myRuns = [];
    let identity = null;
    let searchGeneration = 0;
    let searchController = null;
    let lastFocusedElement = null;

    function selectable(run) {
        void Promise.resolve(onSelectRun(run)).then(() => close());
    }

    function renderTrigger() {
        if (!currentRun) {
            triggerName.textContent = 'Choose a beer run';
            triggerMeta.textContent = '';
            currentSummary.hidden = true;
            return;
        }
        triggerName.textContent = currentRun.name;
        const access = currentRun.current_user_role ? currentRun.current_user_role : 'view only';
        triggerMeta.textContent = `${currentRun.is_public ? 'Public' : 'Private'} \u00b7 ${access}`;
        currentSummaryName.textContent = currentRun.name;
        currentSummary.hidden = false;
    }

    function renderMemberships() {
        membershipSection.hidden = !identity;
        memberships.replaceChildren();
        if (!identity) return;
        if (!myRuns.length) {
            const note = document.createElement('p');
            note.className = 'run-picker-note';
            note.textContent = 'Create or join a run to add it here.';
            memberships.appendChild(note);
            return;
        }
        myRuns.forEach(run => memberships.appendChild(runButton(run, currentRun?.id, selectable)));
    }

    function renderSearchResults(runs) {
        searchResults.replaceChildren();
        const known = new Set(myRuns.map(run => Number(run.id)));
        runs.forEach(run => {
            const button = runButton(run, currentRun?.id, selectable);
            if (known.has(Number(run.id))) {
                const details = button.querySelector('.run-choice-details');
                details.textContent += ' \u00b7 In My runs';
            }
            searchResults.appendChild(button);
        });
    }

    async function search() {
        const query = searchInput.value.trim();
        searchGeneration += 1;
        const generation = searchGeneration;
        if (searchController) searchController.abort();
        searchController = null;
        searchResults.replaceChildren();

        if (query.length === 0) {
            searchStatus.textContent = '';
            return;
        }
        if (query.length < 2) {
            searchStatus.textContent = 'Type at least 2 characters to search public runs.';
            return;
        }

        searchStatus.textContent = 'Searching public runs...';
        searchController = new AbortController();
        const result = await onSearchPublicRuns(query, searchController.signal);
        if (generation !== searchGeneration || result?.aborted) return;
        if (!result?.ok) {
            searchStatus.textContent = 'Public search is unavailable. Please try again.';
            return;
        }
        renderSearchResults(result.data);
        searchStatus.textContent = result.data.length
            ? `${result.data.length} public run${result.data.length === 1 ? '' : 's'} found.`
            : 'No public runs match that name.';
    }

    function focusableElements() {
        return [...sheet.querySelectorAll('button:not([disabled]), input:not([disabled]), [href]')]
            .filter(element => !element.hidden && element.offsetParent !== null);
    }

    function onKeyDown(event) {
        if (dialog.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            close();
            return;
        }
        if (event.key !== 'Tab') return;
        const elements = focusableElements();
        if (!elements.length) return;
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

    function open() {
        if (trigger.disabled) return;
        lastFocusedElement = document.activeElement;
        dialog.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        closeButton.focus();
    }

    function close() {
        if (dialog.hidden) return;
        dialog.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        if (searchController) searchController.abort();
        searchController = null;
        lastFocusedElement?.focus?.();
    }

    trigger.addEventListener('click', open);
    closeButton.addEventListener('click', close);
    shareButton.addEventListener('click', () => {
        if (currentRun) void onShareRun?.(currentRun);
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) close();
    });
    document.addEventListener('keydown', onKeyDown);
    searchInput.addEventListener('input', search);

    return {
        setAvailability(state, message = '') {
            trigger.disabled = state !== 'ready';
            if (state === 'loading') {
                triggerName.textContent = 'Loading beer run...';
                triggerMeta.textContent = '';
            } else if (state === 'error') {
                triggerName.textContent = 'Beer runs unavailable';
                triggerMeta.textContent = '';
            }
            status.textContent = message;
        },
        setIdentity(user) {
            identity = user;
            renderMemberships();
        },
        setMemberships(runs) {
            myRuns = runs || [];
            renderMemberships();
        },
        setCurrentRun(run) {
            currentRun = run || null;
            renderTrigger();
            renderMemberships();
        },
        announce(message) {
            status.textContent = message;
        },
        close,
    };
}

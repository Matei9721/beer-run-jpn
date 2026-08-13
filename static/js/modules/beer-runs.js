import { isCreatedBeerRunResponse, validateBeerRunName } from './beer-run-create.js?v=3';

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
    button.dataset.runId = String(run.id);
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

export function createBeerRunPicker({ onSelectRun, onSearchPublicRuns, onShareRun, onCreateRun, onFetchMembers }) {
    const trigger = document.getElementById('beer-run-trigger');
    const triggerName = document.getElementById('beer-run-trigger-name');
    const triggerMeta = document.getElementById('beer-run-trigger-meta');
    const dialog = document.getElementById('beer-run-picker');
    const sheet = document.getElementById('beer-run-picker-sheet');
    const closeButton = document.getElementById('close-beer-run-picker');
    const pickerIntro = sheet.querySelector('.run-picker-heading .run-picker-intro');
    const status = document.getElementById('beer-run-picker-status');
    const currentSummary = document.getElementById('beer-run-picker-current');
    const currentSummaryName = document.getElementById('beer-run-picker-current-name');
    const rosterSection = document.getElementById('beer-run-roster');
    const rosterStatus = document.getElementById('beer-run-roster-status');
    const rosterList = document.getElementById('beer-run-roster-list');
    const shareButton = document.getElementById('share-beer-run');
    const membershipSection = document.getElementById('beer-run-members-section');
    const memberships = document.getElementById('beer-run-members');
    const createAction = document.getElementById('create-beer-run');
    const libraryView = document.getElementById('beer-run-library-view');
    const createView = document.getElementById('create-beer-run-view');
    const createForm = document.getElementById('create-beer-run-form');
    const createNameInput = document.getElementById('create-beer-run-name');
    const createVisibilityOptions = [...createForm.querySelectorAll('input[name="visibility"]')];
    const createError = document.getElementById('create-beer-run-error');
    const createStatus = document.getElementById('create-beer-run-status');
    const createSubmit = document.getElementById('submit-create-beer-run');
    const createCancel = document.getElementById('cancel-create-beer-run');
    const searchInput = document.getElementById('public-run-search');
    const searchStatus = document.getElementById('public-run-search-status');
    const searchResults = document.getElementById('public-run-results');

    let currentRun = null;
    let myRuns = [];
    let identity = null;
    let searchGeneration = 0;
    let searchController = null;
    let lastFocusedElement = null;
    let createLastFocusedElement = null;
    let createMode = false;
    let createPending = false;
    let memberGeneration = 0;
    let memberController = null;

    function selectable(run) {
        void Promise.resolve(onSelectRun(run)).catch(() => {});
        queueMicrotask(() => {
            const selected = [...sheet.querySelectorAll('.run-choice')]
                .find(button => button.dataset.runId === String(run.id));
            selected?.focus();
        });
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
        createAction.hidden = !identity;
        memberships.replaceChildren();
        if (!identity) return;
        if (!myRuns.length) {
            const note = document.createElement('p');
            note.className = 'run-picker-note';
            note.textContent = 'You do not belong to any runs yet.';
            memberships.appendChild(note);
            return;
        }
        myRuns.forEach(run => memberships.appendChild(runButton(run, currentRun?.id, selectable)));
    }

    function renderRoster(result) {
        rosterList.replaceChildren();
        if (!result?.length) {
            rosterStatus.textContent = 'No members found.';
            return;
        }
        result.forEach(member => {
            const item = document.createElement('li');
            item.className = 'run-roster-item';
            const name = document.createElement('span');
            name.className = 'run-roster-name';
            name.textContent = member.username;
            const role = document.createElement('span');
            role.className = 'run-roster-role';
            role.textContent = member.role === 'owner' ? 'Owner' : 'Member';
            item.append(name, role);
            rosterList.appendChild(item);
        });
        rosterStatus.textContent = `${result.length} member${result.length === 1 ? '' : 's'}.`;
    }

    async function loadRoster() {
        memberGeneration += 1;
        const generation = memberGeneration;
        if (memberController) memberController.abort();
        memberController = null;
        rosterList.replaceChildren();
        if (!currentRun) {
            rosterSection.hidden = true;
            return;
        }
        rosterSection.hidden = false;
        rosterStatus.textContent = 'Loading members...';
        memberController = new AbortController();
        const result = await onFetchMembers?.(currentRun.id, memberController.signal);
        if (generation !== memberGeneration || result?.aborted) return;
        if (!result?.ok) {
            rosterStatus.textContent = 'Members are unavailable right now.';
            return;
        }
        renderRoster(result.data);
    }

    function setCreateFeedback(message = '', assertive = false) {
        createError.textContent = assertive ? message : '';
        createStatus.textContent = assertive ? '' : message;
    }

    function resetCreateView({ restoreFocus = false } = {}) {
        createMode = false;
        createPending = false;
        createForm.reset();
        setCreateFeedback();
        createSubmit.disabled = false;
        createSubmit.textContent = 'Create run';
        libraryView.hidden = false;
        createView.hidden = true;
        document.getElementById('beer-run-picker-title').textContent = 'Choose a run';
        pickerIntro.textContent = 'Switch the whole trip view, or discover a public crew.';
        renderTrigger();
        if (restoreFocus) (createLastFocusedElement || createAction)?.focus?.();
        createLastFocusedElement = null;
    }

    function openCreate() {
        if (!identity || createPending) return;
        createLastFocusedElement = document.activeElement;
        createMode = true;
        libraryView.hidden = true;
        createView.hidden = false;
        currentSummary.hidden = true;
        rosterSection.hidden = true;
        document.getElementById('beer-run-picker-title').textContent = 'Create a run';
        pickerIntro.textContent = 'Choose who can see the run, then invite people later.';
        setCreateFeedback();
        createNameInput.focus();
    }

    async function submitCreate(event) {
        event.preventDefault();
        if (createPending || !identity) return;
        const validation = validateBeerRunName(createNameInput.value);
        if (!validation.valid) {
            setCreateFeedback(validation.message, true);
            createNameInput.focus();
            return;
        }

        createPending = true;
        createSubmit.disabled = true;
        createCancel.disabled = true;
        const selectedVisibility = createVisibilityOptions.find(option => option.checked)?.value;
        const isPublic = selectedVisibility === 'public';
        setCreateFeedback(`Creating your ${isPublic ? 'public' : 'private'} run...`);
        const result = await onCreateRun?.(validation.name, isPublic);
        createCancel.disabled = false;

        if (result?.ok && isCreatedBeerRunResponse(result.data, validation.name, isPublic)) {
            upsertMembership(result.data);
            resetCreateView();
            close({ focusElement: trigger });
            status.textContent = `Created ${result.data.name}.`;
            return;
        }

        createPending = false;
        createSubmit.disabled = false;
        if (result?.aborted || result?.stale) {
            setCreateFeedback('');
            return;
        }
        if (result?.status === 401 && result?.handled) {
            resetCreateView();
            close({ focusElement: trigger });
            return;
        }
        if (result?.status === 409) {
            setCreateFeedback('That run name is already in use. Try another.', true);
        } else if (result?.status === 422) {
            setCreateFeedback(result.detail || 'Use 3–64 characters: letters, numbers, spaces, underscores, or hyphens.', true);
        } else {
            setCreateFeedback(result?.detail || 'We could not confirm the new run. Check My runs before trying again.', true);
        }
        createNameInput.focus();
    }

    function upsertMembership(run) {
        const next = myRuns.filter(item => Number(item.id) !== Number(run.id));
        next.push(run);
        next.sort((left, right) => {
            const nameOrder = left.name.localeCompare(right.name, undefined, { sensitivity: 'base' });
            return nameOrder || Number(left.id) - Number(right.id);
        });
        myRuns = next;
        renderMemberships();
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
        void loadRoster();
    }

    function close({ focusElement = null } = {}) {
        if (dialog.hidden) return;
        if (createMode) resetCreateView();
        dialog.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        if (searchController) searchController.abort();
        searchController = null;
        memberGeneration += 1;
        if (memberController) memberController.abort();
        memberController = null;
        (focusElement || lastFocusedElement)?.focus?.();
    }

    trigger.addEventListener('click', open);
    closeButton.addEventListener('click', close);
    createAction.addEventListener('click', openCreate);
    createCancel.addEventListener('click', () => {
        resetCreateView({ restoreFocus: true });
        if (!dialog.hidden) void loadRoster();
    });
    createForm.addEventListener('submit', submitCreate);
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
            if (!user && createMode) {
                resetCreateView();
                if (!dialog.hidden) close({ focusElement: trigger });
            }
            identity = user;
            renderMemberships();
            if (!dialog.hidden) void loadRoster();
        },
        setMemberships(runs) {
            myRuns = runs || [];
            renderMemberships();
        },
        upsertMembership,
        setCurrentRun(run) {
            currentRun = run || null;
            renderTrigger();
            renderMemberships();
            if (!dialog.hidden) void loadRoster();
        },
        announce(message) {
            status.textContent = message;
        },
        close,
    };
}

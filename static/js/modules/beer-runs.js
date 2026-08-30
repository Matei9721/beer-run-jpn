import { isCreatedBeerRunResponse, validateBeerRunName } from './beer-run-create.js?v=3';
import { validateOwnerInviteResponse } from './invites.js?v=3';

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

export function createBeerRunPicker({ onSelectRun, onSearchPublicRuns, onShareRun, onCreateRun, onRenameRun, onLeaveRun, onFetchMembers, onCreateInvite }) {
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
    const inviteButton = document.getElementById('invite-beer-run');
    const manageButton = document.getElementById('manage-beer-run');
    const leaveButton = document.getElementById('leave-beer-run');
    const ownerGuidance = document.getElementById('beer-run-owner-guidance');
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
    const renameView = document.getElementById('rename-beer-run-view');
    const renameForm = document.getElementById('rename-beer-run-form');
    const renameNameInput = document.getElementById('rename-beer-run-name');
    const renameError = document.getElementById('rename-beer-run-error');
    const renameStatus = document.getElementById('rename-beer-run-status');
    const renameSubmit = document.getElementById('submit-rename-beer-run');
    const renameCancel = document.getElementById('cancel-rename-beer-run');
    const renameConfirmBackdrop = document.getElementById('rename-beer-run-confirm');
    const renameConfirmCopy = document.getElementById('rename-beer-run-confirm-copy');
    const renameConfirmCancel = document.getElementById('cancel-rename-beer-run-confirm');
    const renameConfirmSubmit = document.getElementById('confirm-rename-beer-run');
    const searchInput = document.getElementById('public-run-search');
    const searchStatus = document.getElementById('public-run-search-status');
    const searchResults = document.getElementById('public-run-results');
    const inviteView = document.getElementById('invite-beer-run-view');
    const inviteOwnerError = document.getElementById('invite-owner-error');
    const inviteOwnerStatus = document.getElementById('invite-owner-status');
    const inviteOwnerResult = document.getElementById('invite-owner-result');
    const inviteOwnerUrl = document.getElementById('invite-owner-url');
    const inviteOwnerActionsEmpty = document.getElementById('invite-owner-actions-empty');
    const generateInvite = document.getElementById('generate-invite-link');
    const retryInvite = document.getElementById('retry-invite-link');
    const copyInvite = document.getElementById('copy-invite-link');
    const shareInvite = document.getElementById('share-invite-link');
    const backInvite = document.getElementById('back-invite-link');
    const cancelInvite = document.getElementById('cancel-invite-link');
    const leaveConfirmBackdrop = document.getElementById('leave-beer-run-confirm');
    const leaveConfirmCopy = document.getElementById('leave-beer-run-confirm-copy');
    const leaveConfirmCancel = document.getElementById('cancel-leave-beer-run');
    const leaveConfirmSubmit = document.getElementById('confirm-leave-beer-run');

    let currentRun = null;
    let myRuns = [];
    let identity = null;
    let searchGeneration = 0;
    let searchController = null;
    let lastFocusedElement = null;
    let createLastFocusedElement = null;
    let createMode = false;
    let createPending = false;
    let renameLastFocusedElement = null;
    let renameMode = false;
    let renamePending = false;
    let renameConfirmationName = '';
    let renameConfirmationLastFocusedElement = null;
    let memberGeneration = 0;
    let memberController = null;
    let inviteMode = false;
    let invitePending = false;
    let inviteGeneration = 0;
    let inviteLastFocusedElement = null;
    let inviteData = null;
    let leaveMode = false;
    let leavePending = false;
    let leaveConfirmationLastFocusedElement = null;

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
            inviteButton.hidden = true;
            manageButton.hidden = true;
            leaveButton.hidden = true;
            ownerGuidance.hidden = true;
            return;
        }
        triggerName.textContent = currentRun.name;
        const access = currentRun.current_user_role ? currentRun.current_user_role : 'view only';
        triggerMeta.textContent = `${currentRun.is_public ? 'Public' : 'Private'} \u00b7 ${access}`;
        currentSummaryName.textContent = currentRun.name;
        currentSummary.hidden = false;
        inviteButton.hidden = !(identity && currentRun.current_user_role === 'owner');
        manageButton.hidden = !(identity && currentRun.current_user_role === 'owner');
        leaveButton.hidden = !(identity && currentRun.current_user_role === 'member');
        ownerGuidance.hidden = !(identity && currentRun.current_user_role === 'owner');
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

    function setRenameFeedback(message = '', assertive = false) {
        renameError.textContent = assertive ? message : '';
        renameStatus.textContent = assertive ? '' : message;
    }

    function closeRenameConfirmation({ restoreFocus = true } = {}) {
        if (renameConfirmBackdrop.hidden) return;
        renameConfirmBackdrop.hidden = true;
        sheet.inert = false;
        const focusTarget = renameConfirmationLastFocusedElement || renameNameInput;
        renameConfirmationName = '';
        renameConfirmationLastFocusedElement = null;
        if (restoreFocus) focusTarget?.focus?.();
    }

    function openRenameConfirmation(name) {
        renameConfirmationName = name;
        renameConfirmationLastFocusedElement = document.activeElement;
        renameConfirmCopy.textContent = `Are you sure you want to rename “${currentRun.name}” to “${name}”? Your members, entries, invite link, and history will stay attached to this run.`;
        sheet.inert = true;
        renameConfirmBackdrop.hidden = false;
        renameConfirmCancel.focus();
    }

    function resetRenameView({ restoreFocus = false } = {}) {
        closeRenameConfirmation({ restoreFocus: false });
        renameMode = false;
        renamePending = false;
        renameForm.reset();
        setRenameFeedback();
        renameSubmit.disabled = false;
        renameView.hidden = true;
        libraryView.hidden = false;
        document.getElementById('beer-run-picker-title').textContent = 'Choose a run';
        pickerIntro.textContent = 'Switch the whole trip view, or discover a public crew.';
        renderTrigger();
        if (restoreFocus) (renameLastFocusedElement || manageButton)?.focus?.();
        renameLastFocusedElement = null;
    }

    function openRename() {
        if (!identity || !currentRun || currentRun.current_user_role !== 'owner' || renamePending) return;
        renameLastFocusedElement = document.activeElement;
        renameMode = true;
        libraryView.hidden = true;
        createView.hidden = true;
        renameView.hidden = false;
        inviteView.hidden = true;
        currentSummary.hidden = true;
        rosterSection.hidden = true;
        document.getElementById('beer-run-picker-title').textContent = 'Manage run';
        pickerIntro.textContent = 'Update the name shown across BeerRunJPN.';
        renameNameInput.value = currentRun.name;
        setRenameFeedback();
        renameNameInput.focus();
        renameNameInput.select();
    }

    function closeLeaveConfirmation({ restoreFocus = true } = {}) {
        if (leaveConfirmBackdrop.hidden) return;
        leaveConfirmBackdrop.hidden = true;
        sheet.inert = false;
        const focusTarget = leaveConfirmationLastFocusedElement || leaveButton;
        leaveConfirmationLastFocusedElement = null;
        if (restoreFocus) focusTarget?.focus?.();
    }

    function resetLeaveConfirmation({ restoreFocus = false } = {}) {
        closeLeaveConfirmation({ restoreFocus: false });
        leaveMode = false;
        leavePending = false;
        leaveConfirmSubmit.disabled = false;
        leaveConfirmCancel.disabled = false;
        leaveConfirmSubmit.textContent = 'Leave run';
        if (restoreFocus) leaveButton.focus();
    }

    function openLeaveConfirmation() {
        if (!identity || !currentRun || currentRun.current_user_role !== 'member' || leavePending) return;
        leaveMode = true;
        leaveConfirmationLastFocusedElement = document.activeElement;
        leaveConfirmCopy.textContent = `Leave “${currentRun.name}”? You will stop being a member, but your previous entries and photos will remain visible in this run's history.`;
        sheet.inert = true;
        leaveConfirmBackdrop.hidden = false;
        leaveConfirmCancel.focus();
    }

    async function confirmLeave() {
        if (leavePending || !leaveMode || !identity || !currentRun
            || currentRun.current_user_role !== 'member') return;
        const run = currentRun;
        leavePending = true;
        leaveConfirmSubmit.disabled = true;
        leaveConfirmCancel.disabled = true;
        leaveConfirmSubmit.textContent = 'Leaving...';
        const result = await onLeaveRun?.(run);
        if (result?.ok) {
            resetLeaveConfirmation();
            close({ focusElement: trigger });
            status.textContent = result.stale
                ? `You were already removed from ${run.name}.`
                : `Left ${run.name}. Your entries remain in that run's history.`;
            return;
        }

        if (result?.aborted || result?.stale || (result?.status === 401 && result?.handled)) {
            resetLeaveConfirmation();
            if (result?.status === 401 && result?.handled) close({ focusElement: trigger });
            return;
        }

        leavePending = false;
        leaveConfirmSubmit.disabled = false;
        leaveConfirmCancel.disabled = false;
        leaveConfirmSubmit.textContent = 'Leave run';
        resetLeaveConfirmation({ restoreFocus: false });
        status.textContent = result?.status === 409
            ? (result.detail || 'Owners must transfer ownership or delete the run before leaving.')
            : (result?.network
                ? 'We could not confirm that you left the run. Check your connection and try again.'
                : 'We could not leave this run. Please try again.');
    }

    async function submitRename(event) {
        event.preventDefault();
        if (renamePending || !identity || !currentRun) return;
        const validation = validateBeerRunName(renameNameInput.value);
        if (!validation.valid) {
            setRenameFeedback(validation.message, true);
            renameNameInput.focus();
            return;
        }
        openRenameConfirmation(validation.name);
    }

    async function confirmRename() {
        if (renamePending || !identity || !currentRun || !renameConfirmationName) return;
        const newName = renameConfirmationName;
        closeRenameConfirmation({ restoreFocus: false });
        renamePending = true;
        renameSubmit.disabled = true;
        setRenameFeedback('Saving the new name...');
        const originalRunId = currentRun.id;
        const result = await onRenameRun?.(currentRun, newName);
        if (result?.ok && result.data && Number(result.data.id) === Number(originalRunId)
            && result.data.name === newName && result.data.current_user_role === 'owner') {
            currentRun = result.data;
            upsertMembership(result.data);
            resetRenameView();
            status.textContent = `Renamed to ${result.data.name}.`;
            return;
        }
        renamePending = false;
        renameSubmit.disabled = false;
        if (result?.aborted || result?.stale) {
            setRenameFeedback();
            return;
        }
        if (result?.status === 401 && result?.handled) {
            resetRenameView();
            close({ focusElement: trigger });
            return;
        }
        if (result?.status === 409) {
            setRenameFeedback('That run name is already in use. Try another.', true);
        } else if (result?.status === 422) {
            setRenameFeedback(result.detail || 'Use 3–64 characters: letters, numbers, spaces, underscores, or hyphens.', true);
        } else {
            setRenameFeedback(result?.detail || 'We could not save the new name. Try again.', true);
        }
        renameNameInput.focus();
        renameNameInput.select();
    }

    function setInviteFeedback(message = '', assertive = false) {
        inviteOwnerError.textContent = assertive ? message : '';
        inviteOwnerStatus.textContent = assertive ? '' : message;
    }

    function resetInviteView({ restoreFocus = false } = {}) {
        inviteGeneration += 1;
        inviteMode = false;
        invitePending = false;
        inviteData = null;
        inviteView.hidden = true;
        libraryView.hidden = false;
        inviteOwnerResult.hidden = true;
        inviteOwnerActionsEmpty.hidden = false;
        retryInvite.hidden = true;
        shareInvite.hidden = true;
        inviteOwnerUrl.value = '';
        generateInvite.disabled = false;
        generateInvite.textContent = 'Create invite link';
        setInviteFeedback();
        document.getElementById('beer-run-picker-title').textContent = 'Choose a run';
        pickerIntro.textContent = 'Switch the whole trip view, or discover a public crew.';
        renderTrigger();
        if (restoreFocus) (inviteLastFocusedElement || inviteButton)?.focus?.();
        inviteLastFocusedElement = null;
    }

    function openInvite() {
        if (!identity || !currentRun || currentRun.current_user_role !== 'owner' || invitePending) return;
        inviteLastFocusedElement = document.activeElement;
        inviteMode = true;
        libraryView.hidden = true;
        createView.hidden = true;
        inviteView.hidden = false;
        currentSummary.hidden = true;
        rosterSection.hidden = true;
        document.getElementById('beer-run-picker-title').textContent = 'Invite people';
        pickerIntro.textContent = 'Share a permanent link that lets someone join this run.';
        setInviteFeedback();
        generateInvite.focus();
    }

    function renderInviteResponse(result) {
        const data = result?.data;
        if (!result?.ok || !data || (result.status !== 200 && result.status !== 201)
            || Number(data.beer_run_id) !== Number(currentRun?.id)) return false;
        const validated = validateOwnerInviteResponse(data, currentRun?.id);
        if (!validated) return false;
        inviteData = data;
        inviteOwnerUrl.value = validated.url;
        inviteOwnerResult.hidden = false;
        inviteOwnerActionsEmpty.hidden = true;
        retryInvite.hidden = false;
        shareInvite.hidden = !navigator.share;
        setInviteFeedback(`Invite link ready for ${data.beer_run_name}.`);
        return true;
    }

    async function requestInvite() {
        if (invitePending || !currentRun || currentRun.current_user_role !== 'owner') return;
        const generation = ++inviteGeneration;
        invitePending = true;
        generateInvite.disabled = true;
        retryInvite.disabled = true;
        inviteOwnerResult.hidden = true;
        inviteOwnerActionsEmpty.hidden = false;
        inviteOwnerUrl.value = '';
        inviteData = null;
        setInviteFeedback('Creating invite link...');
        const result = await onCreateInvite?.(currentRun);
        if (generation !== inviteGeneration || inviteMode === false) return;
        retryInvite.disabled = false;
        invitePending = false;
        if (result?.ok && renderInviteResponse(result)) return;
        if (result?.status === 401 && result?.handled) {
            resetInviteView();
            close({ focusElement: trigger });
            return;
        }
        setInviteFeedback(result?.status === 403
            ? 'You are no longer the owner of this run.'
            : 'We could not create the invite link. Try again.', true);
        retryInvite.hidden = false;
        generateInvite.disabled = false;
        inviteOwnerActionsEmpty.hidden = false;
    }

    async function copyInviteLink() {
        if (!inviteData || !inviteOwnerUrl.value) return;
        try {
            await navigator.clipboard.writeText(inviteOwnerUrl.value);
            setInviteFeedback('Invite link copied.');
        } catch (error) {
            window.prompt('Copy this invite link', inviteOwnerUrl.value);
        }
    }

    async function shareInviteLink() {
        if (!inviteData || !navigator.share) return;
        try {
            await navigator.share({
                title: `${inviteData.beer_run_name} · BeerRunJPN`,
                text: `Join ${inviteData.beer_run_name} in BeerRunJPN`,
                url: inviteOwnerUrl.value,
            });
            setInviteFeedback('Share sheet opened.');
        } catch (error) {
            if (error?.name !== 'AbortError') setInviteFeedback('Invite link is ready to copy.');
        }
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
        const root = !renameConfirmBackdrop.hidden
            ? renameConfirmBackdrop
            : (!leaveConfirmBackdrop.hidden ? leaveConfirmBackdrop : sheet);
        return [...root.querySelectorAll('button:not([disabled]), input:not([disabled]), [href]')]
            .filter(element => !element.hidden
                && element.offsetParent !== null
                && !element.closest('[hidden]')
                && !element.closest('[inert]'));
    }

    function onKeyDown(event) {
        if (dialog.hidden) return;
        if (!renameConfirmBackdrop.hidden && event.key === 'Escape') {
            event.preventDefault();
            closeRenameConfirmation();
            return;
        }
        if (!leaveConfirmBackdrop.hidden && event.key === 'Escape') {
            event.preventDefault();
            resetLeaveConfirmation({ restoreFocus: true });
            return;
        }
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
        if (renameMode) resetRenameView();
        if (inviteMode) resetInviteView();
        if (leaveMode) resetLeaveConfirmation();
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
    inviteButton.addEventListener('click', openInvite);
    manageButton.addEventListener('click', openRename);
    leaveButton.addEventListener('click', openLeaveConfirmation);
    createCancel.addEventListener('click', () => {
        resetCreateView({ restoreFocus: true });
        if (!dialog.hidden) void loadRoster();
    });
    createForm.addEventListener('submit', submitCreate);
    renameForm.addEventListener('submit', submitRename);
    renameCancel.addEventListener('click', () => resetRenameView({ restoreFocus: true }));
    renameConfirmCancel.addEventListener('click', () => closeRenameConfirmation());
    renameConfirmSubmit.addEventListener('click', confirmRename);
    leaveConfirmCancel.addEventListener('click', () => resetLeaveConfirmation({ restoreFocus: true }));
    leaveConfirmSubmit.addEventListener('click', confirmLeave);
    shareButton.addEventListener('click', () => {
        if (currentRun) void onShareRun?.(currentRun);
    });
    generateInvite.addEventListener('click', requestInvite);
    retryInvite.addEventListener('click', requestInvite);
    copyInvite.addEventListener('click', copyInviteLink);
    shareInvite.addEventListener('click', shareInviteLink);
    backInvite.addEventListener('click', () => resetInviteView({ restoreFocus: true }));
    cancelInvite.addEventListener('click', () => resetInviteView({ restoreFocus: true }));
    dialog.addEventListener('click', event => {
        if (event.target === dialog) close();
    });
    renameConfirmBackdrop.addEventListener('click', event => {
        if (event.target === renameConfirmBackdrop) closeRenameConfirmation();
    });
    leaveConfirmBackdrop.addEventListener('click', event => {
        if (event.target === leaveConfirmBackdrop) resetLeaveConfirmation({ restoreFocus: true });
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
            if ((createMode || renameMode || inviteMode || leaveMode) && (!user || user.id !== identity?.id)) {
                resetCreateView();
                resetRenameView();
                resetInviteView();
                resetLeaveConfirmation();
                if (!dialog.hidden) close({ focusElement: trigger });
            }
            identity = user;
            renderTrigger();
            renderMemberships();
            if (!dialog.hidden) void loadRoster();
        },
        setMemberships(runs) {
            myRuns = runs || [];
            renderMemberships();
        },
        upsertMembership,
        setCurrentRun(run) {
            if (inviteMode && Number(run?.id) !== Number(currentRun?.id)) resetInviteView();
            if (renameMode && Number(run?.id) !== Number(currentRun?.id)) resetRenameView();
            if (leaveMode && Number(run?.id) !== Number(currentRun?.id)) resetLeaveConfirmation();
            currentRun = run || null;
            renderTrigger();
            renderMemberships();
            if (!dialog.hidden) void loadRoster();
        },
        isOwner() {
            return Boolean(identity && currentRun?.current_user_role === 'owner');
        },
        hasMembership(beerRunId) {
            return Boolean(identity && myRuns.some(run => Number(run.id) === Number(beerRunId)
                && (run.current_user_role === 'member' || run.current_user_role === 'owner')));
        },
        announce(message) {
            status.textContent = message;
        },
        close,
    };
}

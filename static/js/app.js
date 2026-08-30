import * as api from './modules/api.js?v=22';
import * as auth from './modules/auth.js?v=13';
import * as signup from './modules/signup.js?v=2';
import * as beerRuns from './modules/beer-runs.js?v=14';
import * as invites from './modules/invites.js?v=4';
import { createAccountSettings } from './modules/account-settings.js?v=1';
import { isCreatedBeerRunResponse } from './modules/beer-run-create.js?v=2';
import * as mapMod from './modules/map.js?v=14';
import * as ui from './modules/ui.js?v=13';
import { createEntryManagement } from './modules/entry-management.js?v=4';

document.addEventListener('DOMContentLoaded', () => {
    const INSTRUCTIONS_STORAGE_KEY = 'beerRunJpn.hideInstructions';
    const WRAPPED_ENDED_STORAGE_KEY = 'beerRunJpn.hideWrappedEndedNotice';
    const DEFAULT_RUN_NAME = 'BeerRunJPN';

    let lastRefreshTime = new Date();
    let currentLeaderboard = [];
    let currentEntries = [];
    let currentRun = null;
    let currentUser = null;
    let legalMetadata = null;
    let startupModalsPending = true;
    let authValidationComplete = false;
    let contextGeneration = 0;
    let refreshGeneration = 0;
    let refreshController = null;
    let mutationGeneration = 0;
    let mutationController = null;
    let inviteFlow = null;
    let accountSettings = null;

    const picker = beerRuns.createBeerRunPicker({
        onSelectRun: run => selectRun(run, { persist: Boolean(currentUser) }),
        onSearchPublicRuns: (query, signal) => api.searchPublicBeerRuns(query, auth.getToken(), signal),
        onShareRun: shareRun,
        onCreateRun: handleCreateBeerRun,
        onRenameRun: handleRenameBeerRun,
        onLeaveRun: handleLeaveBeerRun,
        onDeleteRun: handleDeleteBeerRun,
        onCreateInvite: handleCreateInvite,
        onFetchMembers: (beerRunId, signal) => api.fetchBeerRunMembers(beerRunId, auth.getToken(), signal),
    });

    const entryManager = createEntryManagement({
        onCreate: handleCreateEntry,
        onUpdate: handleUpdateEntry,
        onDelete: handleDeleteEntry,
        onMutationSuccess: handleEntryMutationSuccess,
        onCancelEdit: handleCancelEdit,
    });

    mapMod.configureEntryActions({
        canManageEntry,
        onEntrySelected: (entry, canManage) => entryManager.selectEntry(entry, canManage),
        onDetailClosed: () => entryManager.clearSelectedEntry(),
        onEdit: entry => {
            if (!canManageEntry(entry) || !entryManager.beginEdit(entry)) return false;
            activateTab('log-tab', { preserveDetail: true });
            return true;
        },
        onDelete: entry => entryManager.openDelete(entry),
    });

    function canWriteCurrentRun() {
        return currentRun?.current_user_role === 'owner' || currentRun?.current_user_role === 'member';
    }

    function canManageEntry(entry) {
        return Boolean(
            entry
            && currentUser
            && canWriteCurrentRun()
            && entry.username === currentUser.username
            && currentEntries.some(currentEntry => Number(currentEntry.id) === Number(entry.id))
        );
    }

    function updateAuthForContext() {
        auth.updateAuthUI(
            currentUser ? auth.AUTH_STATES.AUTHENTICATED : auth.AUTH_STATES.UNAUTHENTICATED,
            canWriteCurrentRun(),
        );
    }

    function clearTripState(message = 'Loading run data...') {
        invalidateMutationWork();
        currentLeaderboard = [];
        currentEntries = [];
        const userFilter = document.getElementById('user-filter');
        userFilter.innerHTML = '<option value="">All Users</option>';
        userFilter.value = '';
        mapMod.clearRunState();
        const mapEmptyState = document.getElementById('map-empty-state');
        if (mapEmptyState) mapEmptyState.hidden = true;
        ui.clearUserModal();
        if (message) ui.renderRunLoading(document.getElementById('leaderboard-data'));
    }

    function cancelRefresh() {
        refreshGeneration += 1;
        if (refreshController) refreshController.abort();
        refreshController = null;
    }

    function invalidateMutationWork() {
        mutationGeneration += 1;
        if (mutationController) mutationController.abort();
        mutationController = null;
        entryManager.resetForContextChange();
    }

    function setCurrentRun(run, { persist = false, message = '' } = {}) {
        const changed = Number(currentRun?.id) !== Number(run?.id);
        if (changed) {
            cancelRefresh();
            clearTripState();
        }
        currentRun = run || null;
        picker.setCurrentRun(currentRun);
        updateWrappedForContext();
        if (persist && currentUser && currentRun) {
            beerRuns.saveSelectedRunId(currentUser.id, currentRun.id);
        }
        updateAuthForContext();
        if (changed) void entryManager.requestInitialLocation();
        if (message) picker.announce(message);
    }

    function wrappedNoticeStorageKey() {
        return currentRun ? `${WRAPPED_ENDED_STORAGE_KEY}.${currentRun.id}` : null;
    }

    function updateWrappedForContext() {
        const available = Boolean(currentRun?.has_wrapped);
        const href = available ? `/wrapped?run=${encodeURIComponent(currentRun.id)}` : '/wrapped';
        for (const link of [
            document.getElementById('wrapped-tab-link'),
            document.getElementById('wrapped-ended-open'),
        ]) {
            link.hidden = !available;
            link.href = href;
        }
        if (!available) document.getElementById('wrapped-ended-modal').style.display = 'none';
    }

    function setSyncStatus(message, syncing = false) {
        document.getElementById('sync-status').innerText = message;
        document.getElementById('sync-dot').classList.toggle('syncing', syncing);
    }

    function sharedRunIdFromUrl() {
        const value = new URL(window.location.href).searchParams.get('run');
        return value && /^\d+$/.test(value) ? value : null;
    }

    function shareUrlForRun(run) {
        const url = new URL(window.location.href);
        url.searchParams.delete('invite');
        url.searchParams.set('run', String(run.id));
        return url.toString();
    }

    async function shareRun(run) {
        const url = shareUrlForRun(run);
        const shareData = {
            title: `${run.name} · BeerRun`,
            text: `Open ${run.name} in BeerRun`,
            url,
        };

        if (navigator.share) {
            try {
                await navigator.share(shareData);
                picker.announce('Share sheet opened.');
                return;
            } catch (error) {
                if (error?.name === 'AbortError') return;
            }
        }

        try {
            await navigator.clipboard.writeText(url);
            picker.announce('Run link copied.');
        } catch (error) {
            window.prompt('Copy this run link', url);
        }
    }

    function createRequestIsStale(user, token, generation) {
        return generation !== contextGeneration
            || currentUser?.id !== user.id
            || auth.getToken() !== token;
    }

    async function reconcileCreatedBeerRun(name, isPublic, user, token, generation) {
        const result = await api.fetchMyBeerRuns(token);
        if (createRequestIsStale(user, token, generation)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (!result.ok) return result;
        const created = result.data.find(run => (
            run.name === name
            && run.is_public === isPublic
            && run.current_user_role === 'owner'
        ));
        return created
            ? { ok: true, data: created, reconciled: true }
            : { ok: false, status: 500, detail: 'We could not confirm the new run. Check My runs before trying again.' };
    }

    async function handleCreateBeerRun(name, isPublic) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token) return { ok: false, status: 401 };

        let result = await api.createBeerRun(name, isPublic, token);
        if (createRequestIsStale(user, token, generation)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { ok: false, status: 401, handled: true };
        }

        let created = result.ok && isCreatedBeerRunResponse(result.data, name, isPublic)
            ? result.data
            : null;
        if (!created && (result.network || result.ok)) {
            result = await reconcileCreatedBeerRun(name, isPublic, user, token, generation);
            if (result.status === 401) {
                handleRejectedSession();
                return { ok: false, status: 401, handled: true };
            }
            if (createRequestIsStale(user, token, generation)) {
                return { ok: false, aborted: true, stale: true };
            }
            created = result.ok ? result.data : null;
        }
        if (!created) return result;

        setCurrentRun(created, { persist: true, message: `Created ${created.name}.` });
        picker.setAvailability('ready');
        await refreshData(true);
        return { ok: true, data: created };
    }

    async function handleRenameBeerRun(run, name) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token || !run || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, status: 401 };
        }
        const result = await api.updateBeerRun(run.id, { name }, token);
        if (createRequestIsStale(user, token, generation)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { ok: false, status: 401, handled: true };
        }
        if (result.status === 403 || result.status === 404) {
            await initializeRunContext({ notice: 'Your owner access changed. Refreshing runs.' });
            return { ok: false, status: result.status, detail: result.detail };
        }
        if (result.ok) {
            setCurrentRun(result.data, { persist: false });
            await refreshData(true);
        }
        return result;
    }

    async function handleLeaveBeerRun(run) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token || !run || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, status: 401 };
        }

        const result = await api.leaveBeerRun(run.id, token);
        if (generation !== contextGeneration || currentUser?.id !== user.id
            || auth.getToken() !== token || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { ok: false, status: 401, handled: true };
        }
        if (result.status === 404) {
            await recoverFromAccessLoss(run, {
                notice: 'Your membership was already removed. Choosing another available run.',
            });
            return { ok: true, status: result.status, stale: true };
        }
        if (result.status === 409) {
            await initializeRunContext({
                notice: 'Owners must transfer ownership or delete the run before leaving.',
            });
            return result;
        }
        if (result.ok) {
            await recoverFromAccessLoss(run, {
                notice: `You left ${run.name}. Your entries remain in that run's history.`,
            });
        }
        return result;
    }

    async function handleDeleteBeerRun(run) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token || !run || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, status: 401 };
        }

        const result = await api.deleteBeerRun(run.id, token);
        if (generation !== contextGeneration || currentUser?.id !== user.id
            || auth.getToken() !== token || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { ok: false, status: 401, handled: true };
        }
        if (result.status === 404) {
            await recoverFromAccessLoss(run, {
                notice: 'This run was already removed. Choosing another available run.',
            });
            return { ok: true, status: result.status, stale: true };
        }
        if (result.status === 403) {
            await initializeRunContext({ notice: 'Your owner access changed. Refreshing runs.' });
            return result;
        }
        if (result.ok) {
            picker.removeRun(run.id);
            await recoverFromAccessLoss(run, {
                notice: `Deleted ${run.name}. Choosing another available run.`,
            });
        }
        return result;
    }

    async function handleCreateInvite(run) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token || !run || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, status: 401 };
        }
        const result = await api.createBeerRunInvite(run.id, token);
        if (generation !== contextGeneration || currentUser?.id !== user.id || auth.getToken() !== token
            || Number(currentRun?.id) !== Number(run.id)) {
            return { ok: false, aborted: true, stale: true };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { ok: false, status: 401, handled: true };
        }
        if (result.status === 403) {
            await initializeRunContext({ notice: 'Your owner access changed. Refreshing runs.' });
        } else if (result.status === 404) {
            await recoverFromAccessLoss(run);
        }
        return result;
    }

    async function reconcileInviteMembership(beerRunId, user, token, generation) {
        if (!user || !token) return null;
        const result = await api.fetchMyBeerRuns(token);
        if (generation !== contextGeneration || currentUser?.id !== user.id || auth.getToken() !== token) return null;
        if (!result.ok) {
            if (result.status === 401) handleRejectedSession();
            return null;
        }
        return result.data.find(run => Number(run.id) === Number(beerRunId)
            && (run.current_user_role === 'member' || run.current_user_role === 'owner')) || null;
    }

    async function handleAcceptedInvite(run) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token) return false;
        picker.upsertMembership(run);
        setCurrentRun(run, { persist: true, message: `Joined ${run.name}.` });
        picker.setAvailability('ready');
        await refreshData(true);
        if (generation !== contextGeneration || currentUser?.id !== user.id || auth.getToken() !== token) return false;
        const reconciled = await api.fetchMyBeerRuns(token);
        if (generation !== contextGeneration || currentUser?.id !== user.id || auth.getToken() !== token) return false;
        if (reconciled.status === 401) {
            handleRejectedSession();
            return false;
        }
        if (reconciled.ok) {
            picker.setMemberships(reconciled.data);
        } else {
            picker.announce('Joined run. My runs could not refresh; try again later.');
        }
        return true;
    }

    inviteFlow = invites.createInviteFlow({
        getCurrentUser: () => currentUser,
        getToken: () => auth.getToken(),
        getContextGeneration: () => contextGeneration,
        isMemberOfRun: beerRunId => picker.hasMembership(beerRunId)
            || (Number(currentRun?.id) === Number(beerRunId)
                && (currentRun?.current_user_role === 'member' || currentRun?.current_user_role === 'owner')),
        onOpenAuth: mode => {
            auth.openLoginModal();
            auth.setAuthMode(mode);
        },
        onAccepted: handleAcceptedInvite,
        onRejectedSession: handleRejectedSession,
        onReconcile: reconcileInviteMembership,
        onAllowStartup: showStartupModals,
    });

    async function openOwnedRunManagement(runSummary) {
        accountSettings?.reset();
        const result = await api.fetchBeerRun(runSummary.id, auth.getToken());
        if (result.status === 401) {
            handleRejectedSession();
            return;
        }
        if (!result.ok || result.data?.current_user_role !== 'owner') {
            picker.announce('That run is no longer owned by this account. Reopen Account settings to refresh.');
            document.getElementById('beer-run-trigger').click();
            return;
        }
        if (Number(currentRun?.id) !== Number(result.data.id)) {
            await selectRun(result.data, { persist: true });
        } else {
            setCurrentRun(result.data, { persist: false });
        }
        document.getElementById('beer-run-trigger').click();
        document.getElementById('manage-beer-run').click();
    }

    async function deleteCurrentAccount(password, confirmation, signal) {
        const user = currentUser;
        const token = auth.getToken();
        const generation = contextGeneration;
        if (!user || !token) return { ok: false, status: 401 };
        const result = await api.deleteAccount(password, confirmation, token, signal);
        if (generation !== contextGeneration || currentUser?.id !== user.id || auth.getToken() !== token) {
            return { ok: false, aborted: true, stale: true };
        }
        if (!result.ok || result.data?.deleted !== true) return result;

        beerRuns.removeSelectedRunId(user.id);
        inviteFlow?.reset();
        const url = new URL(window.location.href);
        url.searchParams.delete('invite');
        url.searchParams.delete('run');
        window.history.replaceState({}, '', url);
        auth.removeToken();
        accountSettings?.completeSuccess();
        auth.closeLoginModal();
        resetIdentity();
        await initializeRunContext({ notice: 'Your account and personal data were deleted.' });
        return result;
    }

    accountSettings = createAccountSettings({
        onFetchSummary: signal => api.fetchAccountDeletionSummary(auth.getToken(), signal),
        onDelete: deleteCurrentAccount,
        onManageOwnedRun: openOwnedRunManagement,
    });

    async function resolveDefaultRun(signal = null) {
        const result = await api.findPublicBeerRunByName(DEFAULT_RUN_NAME, auth.getToken(), signal);
        if (!result.ok) return { run: null, reason: result.network ? 'network' : 'missing' };
        return { run: result.data[0] || null, reason: result.data.length ? 'ready' : 'missing' };
    }

    async function initializeRunContext({ notice = '' } = {}) {
        invalidateMutationWork();
        const generation = ++contextGeneration;
        picker.setAvailability('loading');
        picker.setIdentity(currentUser);
        picker.setMemberships([]);

        let myRuns = [];
        if (currentUser) {
            const mineResult = await api.fetchMyBeerRuns(auth.getToken());
            if (generation !== contextGeneration) return;
            if (mineResult.status === 401) {
                handleRejectedSession();
                return;
            }
            if (mineResult.ok) myRuns = mineResult.data;
        }
        picker.setMemberships(myRuns);

        let selected = null;
        const sharedRunId = sharedRunIdFromUrl();
        if (sharedRunId) {
            const sharedResult = await api.fetchBeerRun(sharedRunId, auth.getToken());
            if (generation !== contextGeneration) return;
            if (sharedResult.ok) selected = sharedResult.data;
        }

        if (!selected && currentUser) {
            const storedRunId = beerRuns.readSelectedRunId(currentUser.id);
            if (storedRunId) {
                selected = myRuns.find(run => Number(run.id) === Number(storedRunId)) || null;
                if (!selected) {
                    const storedResult = await api.fetchBeerRun(storedRunId, auth.getToken());
                    if (generation !== contextGeneration) return;
                    if (storedResult.ok) selected = storedResult.data;
                    else if (storedResult.status === 404) beerRuns.removeSelectedRunId(currentUser.id);
                }
            }
        }

        if (!selected && currentUser) {
            selected = myRuns.find(run => !run.is_public)
                || myRuns.find(run => run.is_public)
                || null;
        }

        if (!selected) {
            const fallback = await resolveDefaultRun();
            if (generation !== contextGeneration) return;
            selected = fallback.run;
            if (!selected) {
                currentRun = null;
                picker.setCurrentRun(null);
                updateWrappedForContext();
                picker.setAvailability('error', fallback.reason === 'network'
                    ? 'Connection unavailable. Refresh to try again.'
                    : 'BeerRunJPN is not available.');
                clearTripState('No beer run is available right now.');
                updateAuthForContext();
                return;
            }
        }

        setCurrentRun(selected, { persist: false, message: notice });
        picker.setAvailability('ready');
        await refreshData(true);
    }

    async function selectRun(run, { persist = false } = {}) {
        if (!run || Number(run.id) === Number(currentRun?.id)) return;
        setCurrentRun(run, { persist, message: `Showing ${run.name}.` });
        picker.setAvailability('ready');
        await refreshData(true);
    }

    async function recoverFromAccessLoss(run, { notice = 'Your selected run is no longer available. Choosing your default run instead.' } = {}) {
        if (!currentRun || Number(currentRun.id) !== Number(run.id)) return;
        cancelRefresh();
        if (currentUser) beerRuns.removeSelectedRunId(currentUser.id);
        const url = new URL(window.location.href);
        if (url.searchParams.get('run') === String(run.id)) {
            url.searchParams.delete('run');
            window.history.replaceState({}, '', url);
        }
        currentRun = null;
        picker.setCurrentRun(null);
        updateWrappedForContext();
        clearTripState('This beer run is no longer available.');
        updateAuthForContext();
        await initializeRunContext({ notice });
    }

    async function refreshData(isManual = false, { allowFallback = true } = {}) {
        const run = currentRun;
        if (!run) return;

        const requestContext = contextGeneration;
        const requestGeneration = ++refreshGeneration;
        if (refreshController) refreshController.abort();
        refreshController = new AbortController();
        const signal = refreshController.signal;
        const userFilter = document.getElementById('user-filter');
        const selectedUsername = userFilter.value;
        setSyncStatus('Syncing...', true);

        const [leaderboardResult, entriesResult] = await Promise.all([
            api.fetchLeaderboard(run.id, auth.getToken(), signal),
            api.fetchEntries(run.id, selectedUsername, auth.getToken(), signal),
        ]);
        if (requestGeneration !== refreshGeneration || requestContext !== contextGeneration || Number(currentRun?.id) !== Number(run.id)) return;

        const missing = result => !result.ok && result.status === 404;
        if (missing(leaderboardResult) || missing(entriesResult)) {
            setSyncStatus('Selected run is no longer available.');
            if (allowFallback) await recoverFromAccessLoss(run);
            return;
        }
        if (!leaderboardResult.ok || !entriesResult.ok) {
            setSyncStatus('Connection unavailable; retrying');
            return;
        }

        // Render this pair only after both scoped reads have succeeded for the
        // same run and refresh generation.
        currentLeaderboard = leaderboardResult.data;
        currentEntries = entriesResult.data;
        ui.renderLeaderboard(currentLeaderboard, document.getElementById('leaderboard-data'));

        const options = ['<option value="">All Users</option>'];
        currentLeaderboard.forEach(user => {
            options.push(`<option value="${user.username}">${user.username}</option>`);
        });
        userFilter.innerHTML = options.join('');
        userFilter.value = selectedUsername;
        mapMod.updateMarkers(currentEntries, isManual);
        const mapEmptyState = document.getElementById('map-empty-state');
        if (mapEmptyState) {
            mapEmptyState.hidden = currentEntries.length > 0;
            mapEmptyState.textContent = 'No mapped drinks in this run yet.';
        }

        const openHistoryUsername = ui.getOpenUserModalUsername();
        if (openHistoryUsername) {
            const historyRendered = ui.showUserModal(
                openHistoryUsername,
                currentLeaderboard,
                currentEntries,
                focusEntryOnMap,
            );
            if (!historyRendered) {
                ui.clearUserModal();
                picker.announce('That drink history is no longer available.');
            }
        }

        lastRefreshTime = new Date();
        setSyncStatus(`Synced ${lastRefreshTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    }

    function createMutationSnapshot(entry, interactionGeneration) {
        const user = currentUser;
        const run = currentRun;
        const token = auth.getToken();
        if (!entry || !user || !run || !token || !canWriteCurrentRun()) return null;

        if (mutationController) mutationController.abort();
        const generation = ++mutationGeneration;
        mutationController = new AbortController();
        return {
            userId: user.id,
            token,
            contextGeneration,
            runId: run.id,
            entryId: entry.id,
            interactionGeneration,
            mutationGeneration: generation,
            signal: mutationController.signal,
        };
    }

    function mutationSnapshotIsCurrent(snapshot) {
        return Boolean(
            snapshot
            && snapshot.mutationGeneration === mutationGeneration
            && snapshot.contextGeneration === contextGeneration
            && currentUser?.id === snapshot.userId
            && auth.getToken() === snapshot.token
            && Number(currentRun?.id) === Number(snapshot.runId)
            && entryManager.isInteractionCurrent(snapshot.entryId, snapshot.interactionGeneration)
        );
    }

    function finishMutation(snapshot) {
        if (snapshot?.mutationGeneration === mutationGeneration) mutationController = null;
    }

    function createRequestIsCurrent(snapshot) {
        return Boolean(
            snapshot.contextGeneration === contextGeneration
            && currentUser?.id === snapshot.userId
            && auth.getToken() === snapshot.token
            && Number(currentRun?.id) === Number(snapshot.runId)
            && entryManager.getInteractionGeneration() === snapshot.interactionGeneration
        );
    }

    async function handleCreateEntry({ formData, interactionGeneration }) {
        const token = auth.getToken();
        if (!token || !currentUser) {
            updateAuthForContext();
            return { ok: false, message: 'You must be logged in.' };
        }
        if (!currentRun) return { ok: false, message: 'Choose an available beer run first.' };
        if (!canWriteCurrentRun()) return { ok: false, message: `You are not a member of ${currentRun.name}.` };

        const snapshot = {
            userId: currentUser.id,
            token,
            contextGeneration,
            runId: currentRun.id,
            interactionGeneration,
        };
        let response;
        try {
            response = await api.submitEntry(snapshot.runId, formData, token);
        } catch (error) {
            if (!createRequestIsCurrent(snapshot)) return { stale: true };
            return { ok: false, message: 'Upload failed. Check your connection and try again.' };
        }
        if (!createRequestIsCurrent(snapshot)) return { stale: true };
        if (response.ok) {
            void refreshData(true);
            return { ok: true };
        }
        if (response.status === 401) {
            handleRejectedSession();
            return { stale: true };
        }
        if (response.status === 404) {
            await recoverFromAccessLoss(currentRun);
            return { stale: true };
        }
        if (response.status === 422) {
            return { ok: false, message: 'Upload failed. Check the entry details and try again.' };
        }
        return { ok: false, message: 'Upload failed. Please try again.' };
    }

    async function executeEntryMutation(kind, entry, formData, interactionGeneration) {
        const snapshot = createMutationSnapshot(entry, interactionGeneration);
        if (!snapshot) {
            return { ok: false, message: 'Your session or selected run changed. Reopen the entry and try again.' };
        }

        const result = kind === 'edit'
            ? await api.patchEntry(snapshot.runId, snapshot.entryId, formData, snapshot.token, snapshot.signal)
            : await api.deleteEntry(snapshot.runId, snapshot.entryId, snapshot.token, snapshot.signal);
        if (!mutationSnapshotIsCurrent(snapshot) || result?.aborted) return { stale: true };
        finishMutation(snapshot);

        if (result.ok) {
            return { ok: true, message: kind === 'edit' ? 'Changes saved.' : 'Entry deleted.' };
        }
        if (result.status === 401) {
            handleRejectedSession();
            return { stale: true };
        }
        if (result.status === 404 && result.detail === 'Beer-run not found') {
            await recoverFromAccessLoss(currentRun);
            return { stale: true };
        }
        if (result.status === 404 && result.detail === 'Entry not found') {
            mapMod.closeDetail();
            setSyncStatus('Entry no longer available; refreshing.');
            picker.announce('This entry is no longer available.');
            void refreshData(true);
            return { stale: true };
        }
        if (result.status === 422) {
            return { ok: false, message: 'Check the entry details and photo choice, then try again.' };
        }
        if (result.network) {
            return {
                ok: false,
                message: kind === 'edit'
                    ? 'Connection lost before the update was confirmed. Refresh before trying again.'
                    : 'Connection lost before deletion was confirmed. Refresh before trying again.',
            };
        }
        return {
            ok: false,
            message: kind === 'edit'
                ? 'Unable to update entry. Please try again.'
                : 'Unable to delete entry. Please try again.',
        };
    }

    function handleUpdateEntry({ entry, formData, interactionGeneration }) {
        return executeEntryMutation('edit', entry, formData, interactionGeneration);
    }

    function handleDeleteEntry({ entry, interactionGeneration }) {
        return executeEntryMutation('delete', entry, null, interactionGeneration);
    }

    function handleEntryMutationSuccess(kind) {
        mapMod.closeDetail();
        picker.announce(kind === 'edit' ? 'Entry updated.' : 'Entry deleted.');
        void refreshData(true);
    }

    function handleCancelEdit(entry) {
        const currentEntry = currentEntries.find(item => Number(item.id) === Number(entry?.id));
        if (!currentEntry || !currentRun) return;
        activateTab('map-tab');
        setTimeout(() => {
            mapMod.map.invalidateSize();
            mapMod.focusEntry(currentEntry, () => mapMod.focusDetailAction('edit'));
        }, 200);
    }

    function activateTab(tabId, { preserveDetail = false } = {}) {
        if (tabId !== 'map-tab' && !preserveDetail && mapMod.isDetailOpen()) {
            mapMod.closeDetail();
        }
        document.querySelectorAll('.tab-btn').forEach(button => button.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.querySelector(`[data-tab="${tabId}"]`)?.classList.add('active');
        document.getElementById(tabId)?.classList.add('active');
    }

    async function focusEntryOnMap(entry) {
        const entryRunId = currentRun?.id;
        ui.clearUserModal();
        activateTab('map-tab');
        const userFilter = document.getElementById('user-filter');
        if (userFilter.value) {
            userFilter.value = '';
            await refreshData(false);
        }
        setTimeout(() => {
            if (Number(currentRun?.id) !== Number(entryRunId)) return;
            mapMod.map.invalidateSize();
            if (!mapMod.focusEntry(entry)) {
                refreshData(false).then(() => {
                    if (Number(currentRun?.id) === Number(entryRunId)) mapMod.focusEntry(entry);
                });
            }
        }, 200);
    }

    function closeInstructionsModal() {
        const modal = document.getElementById('instructions-modal');
        if (document.getElementById('hide-instructions').checked) localStorage.setItem(INSTRUCTIONS_STORAGE_KEY, 'true');
        modal.style.display = 'none';
        showWrappedEndedModal();
    }

    function initInstructionsModal() {
        document.getElementById('close-instructions').addEventListener('click', closeInstructionsModal);
        document.getElementById('instructions-done').addEventListener('click', closeInstructionsModal);
    }

    function closeWrappedEndedModal() {
        const modal = document.getElementById('wrapped-ended-modal');
        const storageKey = wrappedNoticeStorageKey();
        if (storageKey && document.getElementById('hide-wrapped-ended').checked) localStorage.setItem(storageKey, 'true');
        modal.style.display = 'none';
    }

    function showWrappedEndedModal() {
        if (!currentRun?.has_wrapped) return;
        const storageKey = wrappedNoticeStorageKey();
        if (storageKey && localStorage.getItem(storageKey) === 'true') return;
        if (document.getElementById('instructions-modal').style.display === 'flex') return;
        document.getElementById('wrapped-ended-modal').style.display = 'flex';
    }

    function initWrappedEndedModal() {
        document.getElementById('close-wrapped-ended').addEventListener('click', closeWrappedEndedModal);
        document.getElementById('wrapped-ended-done').addEventListener('click', closeWrappedEndedModal);
        document.getElementById('wrapped-ended-open').addEventListener('click', () => {
            const storageKey = wrappedNoticeStorageKey();
            if (storageKey && document.getElementById('hide-wrapped-ended').checked) localStorage.setItem(storageKey, 'true');
        });
    }

    function showStartupModals() {
        if (!authValidationComplete || !startupModalsPending) return;
        if (inviteFlow?.isActive()) return;
        startupModalsPending = false;
        if (localStorage.getItem(INSTRUCTIONS_STORAGE_KEY) !== 'true') {
            document.getElementById('instructions-modal').style.display = 'flex';
        } else {
            showWrappedEndedModal();
        }
    }

    function resetIdentity() {
        contextGeneration += 1;
        cancelRefresh();
        inviteFlow?.invalidate();
        accountSettings?.dismiss({ restoreFocus: false });
        currentUser = null;
        currentRun = null;
        picker.setIdentity(null);
        picker.setMemberships([]);
        picker.setCurrentRun(null);
        clearTripState();
        updateAuthForContext();
    }

    function handleRejectedSession() {
        auth.removeToken();
        resetIdentity();
        auth.showLoginPrompt('Your session is no longer valid. Please log in again.');
        void initializeRunContext();
    }

    async function ensureLegalMetadata({ refresh = false } = {}) {
        if (legalMetadata && !refresh) return legalMetadata;
        try {
            const response = await api.fetchLegalMetadata();
            if (!response.ok) return null;
            const data = await response.json();
            if (!data?.terms_version || !data?.terms_url || !data?.privacy_url) return null;
            legalMetadata = data;
            document.getElementById('signup-terms-link').href = data.terms_url;
            document.getElementById('signup-privacy-link').href = data.privacy_url;
            return data;
        } catch (error) {
            console.error('Legal metadata request failed');
            return null;
        }
    }

    async function establishAuthenticatedContext() {
        const token = auth.getToken();
        if (!token) return false;
        auth.updateAuthUI(auth.AUTH_STATES.VALIDATING);
        try {
            const response = await api.fetchCurrentUser(token);
            if (response.ok) {
                currentUser = await response.json();
                updateAuthForContext();
                await initializeRunContext();
                return true;
            }
            if (response.status === 401) handleRejectedSession();
            else {
                auth.updateAuthUI(auth.AUTH_STATES.VALIDATION_FAILED);
                auth.showLoginPrompt('Could not verify your session. Check your connection and try again.');
            }
        } catch (error) {
            console.error('Session validation error:', error);
            auth.updateAuthUI(auth.AUTH_STATES.VALIDATION_FAILED);
            auth.showLoginPrompt('Could not verify your session. Check your connection and try again.');
        }
        return false;
    }

    async function validateStoredSession() {
        try {
            if (!auth.getToken()) {
                resetIdentity();
                await initializeRunContext();
                return false;
            }
            return !(await establishAuthenticatedContext());
        } finally {
            authValidationComplete = true;
        }
    }

    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            if (!tabId) return;
            activateTab(tabId);
            if (tabId === 'map-tab') {
                setTimeout(() => {
                    mapMod.map.invalidateSize();
                    refreshData(true);
                    ui.showMapHint();
                }, 200);
            } else if (tabId === 'log-tab') {
                void entryManager.requestInitialLocation();
            }
        });
    });

    document.getElementById('login-btn').addEventListener('click', () => {
        inviteFlow?.suspendForAuth();
        auth.openLoginModal();
    });
    document.getElementById('logout-btn').addEventListener('click', () => {
        auth.removeToken();
        resetIdentity();
        void initializeRunContext();
    });
    document.getElementById('account-settings-btn').addEventListener('click', () => accountSettings.open());
    document.getElementById('close-login').addEventListener('click', () => {
        auth.closeLoginModal();
        if (!inviteFlow?.authClosed()) showStartupModals();
    });
    document.getElementById('close-user-modal').addEventListener('click', ui.clearUserModal);

    window.addEventListener('click', event => {
        const loginModal = document.getElementById('login-modal');
        if (event.target === loginModal) {
            auth.closeLoginModal();
            if (!inviteFlow?.authClosed()) showStartupModals();
        }
        if (event.target === document.getElementById('user-modal')) ui.clearUserModal();
        if (event.target === document.getElementById('instructions-modal')) closeInstructionsModal();
        if (event.target === document.getElementById('wrapped-ended-modal')) closeWrappedEndedModal();
    });

    async function handleAuthenticated(data) {
        auth.setToken(data.access_token);
        auth.closeLoginModal();
        document.getElementById('login-form').reset();
        resetIdentity();
        const established = await establishAuthenticatedContext();
        const resumedInvite = inviteFlow?.resumeAfterAuth();
        if (!resumedInvite && inviteFlow?.authClosed()) {
            // Restore an invite preview suspended for ordinary header auth.
        } else if (!resumedInvite && !inviteFlow?.isActive()) {
            showStartupModals();
        } else if (!established && inviteFlow?.isActive()) {
            inviteFlow.authClosed();
        }
    }

    document.getElementById('login-form').addEventListener('submit', async event => {
        event.preventDefault();
        const loginError = document.getElementById('login-error');
        try {
            const response = await api.login(
                document.getElementById('login-username').value,
                document.getElementById('login-password').value,
            );
            if (response.ok) await handleAuthenticated(await response.json());
            else {
                loginError.innerText = 'Invalid credentials';
                loginError.style.display = 'block';
            }
        } catch (error) {
            console.error('Login error:', error);
            loginError.innerText = 'Connection error';
            loginError.style.display = 'block';
        }
    });

    document.getElementById('auth-mode-login').addEventListener('click', () => auth.setAuthMode('login'));
    document.getElementById('auth-mode-signup').addEventListener('click', () => auth.setAuthMode('signup'));
    document.getElementById('signup-form').addEventListener('submit', async event => {
        event.preventDefault();
        const fields = {
            username: document.getElementById('signup-username').value,
            password: document.getElementById('signup-password').value,
            confirmPassword: document.getElementById('signup-confirm').value,
            signupCode: document.getElementById('signup-code').value,
            termsAccepted: document.getElementById('signup-terms-agreement').checked,
        };
        const validation = signup.validateSignupFields(fields);
        if (!validation.valid) {
            auth.showSignupError(signup.formatValidationErrors(validation.errors));
            return;
        }
        const submitButton = document.getElementById('signup-submit');
        submitButton.disabled = true;
        try {
            const metadata = await ensureLegalMetadata();
            if (!metadata) {
                auth.showSignupError('Could not load the current Terms. Check your connection and try again.');
                submitButton.disabled = false;
                return;
            }
            const response = await api.signup(
                validation.username,
                fields.password,
                fields.signupCode,
                metadata.terms_version,
            );
            if (response.status === 201) {
                await handleAuthenticated(await response.json());
                return;
            }
            auth.showSignupError(await signup.getSignupFailureMessage(response));
            submitButton.disabled = false;
        } catch (error) {
            console.error('Signup request failed');
            auth.showSignupError('Connection error. Please check your connection and try again.');
            submitButton.disabled = false;
        }
    });

    document.addEventListener('mouseover', event => {
        const trigger = event.target.closest('.tooltip-trigger');
        if (trigger) ui.createTooltip(trigger, trigger.dataset.tooltip);
    });
    document.addEventListener('mouseout', event => {
        if (event.target.closest('.tooltip-trigger')) ui.removeTooltip();
    });
    document.addEventListener('click', event => {
        const trigger = event.target.closest('.tooltip-trigger');
        if (trigger) ui.createTooltip(trigger, trigger.dataset.tooltip);
        else ui.removeTooltip();
    });
    document.addEventListener('click', event => {
        const card = event.target.closest('.rank-card');
        const username = card?.getAttribute('data-username');
        if (username) ui.showUserModal(username, currentLeaderboard, currentEntries, focusEntryOnMap);
    });

    document.getElementById('close-sheet').addEventListener('click', mapMod.closeDetail);
    mapMod.map.on('click', () => {
        mapMod.closeDetail();
        const hint = document.querySelector('.map-hint');
        if (hint) {
            hint.classList.remove('visible');
            setTimeout(() => hint.remove(), 400);
        }
    });
    document.getElementById('user-filter').addEventListener('change', () => refreshData(true));

    initInstructionsModal();
    initWrappedEndedModal();
    document.getElementById('sync-bar').addEventListener('click', () => refreshData(true));
    setInterval(() => refreshData(false), 30000);

    (async () => {
        await ensureLegalMetadata();
        const authPromptShown = await validateStoredSession();
        const inviteShown = inviteFlow.initialize();
        if (inviteShown) auth.closeLoginModal();
        if (!authPromptShown && !inviteShown) showStartupModals();
        const config = await api.fetchConfig();
        entryManager.setConfig(config);
        void entryManager.requestInitialLocation();
    })();
});

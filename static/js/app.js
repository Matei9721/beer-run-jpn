import * as api from './modules/api.js?v=15';
import * as auth from './modules/auth.js?v=12';
import * as signup from './modules/signup.js?v=1';
import * as beerRuns from './modules/beer-runs.js?v=6';
import { isCreatedBeerRunResponse } from './modules/beer-run-create.js?v=2';
import * as mapMod from './modules/map.js?v=11';
import * as ui from './modules/ui.js?v=11';

document.addEventListener('DOMContentLoaded', () => {
    const INSTRUCTIONS_STORAGE_KEY = 'beerRunJpn.hideInstructions';
    const WRAPPED_ENDED_STORAGE_KEY = 'beerRunJpn.hideWrappedEndedNotice';
    const DEFAULT_RUN_NAME = 'BeerRunJPN';

    let lastRefreshTime = new Date();
    let currentLeaderboard = [];
    let currentEntries = [];
    let currentRun = null;
    let currentUser = null;
    let startupModalsPending = true;
    let authValidationComplete = false;
    let contextGeneration = 0;
    let refreshGeneration = 0;
    let refreshController = null;

    const picker = beerRuns.createBeerRunPicker({
        onSelectRun: run => selectRun(run, { persist: Boolean(currentUser) }),
        onSearchPublicRuns: (query, signal) => api.searchPublicBeerRuns(query, auth.getToken(), signal),
        onShareRun: shareRun,
        onCreateRun: handleCreateBeerRun,
        onFetchMembers: (beerRunId, signal) => api.fetchBeerRunMembers(beerRunId, auth.getToken(), signal),
    });

    function canWriteCurrentRun() {
        return currentRun?.current_user_role === 'owner' || currentRun?.current_user_role === 'member';
    }

    function updateAuthForContext() {
        auth.updateAuthUI(
            currentUser ? auth.AUTH_STATES.AUTHENTICATED : auth.AUTH_STATES.UNAUTHENTICATED,
            canWriteCurrentRun(),
        );
    }

    function clearTripState(message = 'Loading run data...') {
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

    function setCurrentRun(run, { persist = false, message = '' } = {}) {
        const changed = Number(currentRun?.id) !== Number(run?.id);
        if (changed) {
            cancelRefresh();
            clearTripState();
        }
        currentRun = run || null;
        picker.setCurrentRun(currentRun);
        if (persist && currentUser && currentRun) {
            beerRuns.saveSelectedRunId(currentUser.id, currentRun.id);
        }
        updateAuthForContext();
        if (message) picker.announce(message);
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
        url.searchParams.set('run', String(run.id));
        return url.toString();
    }

    async function shareRun(run) {
        const url = shareUrlForRun(run);
        const shareData = {
            title: `${run.name} · BeerRunJPN`,
            text: `Open ${run.name} in BeerRunJPN`,
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

    async function resolveDefaultRun(signal = null) {
        const result = await api.findPublicBeerRunByName(DEFAULT_RUN_NAME, auth.getToken(), signal);
        if (!result.ok) return { run: null, reason: result.network ? 'network' : 'missing' };
        return { run: result.data[0] || null, reason: result.data.length ? 'ready' : 'missing' };
    }

    async function initializeRunContext({ notice = '' } = {}) {
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

    async function recoverFromAccessLoss(run) {
        if (!currentRun || Number(currentRun.id) !== Number(run.id)) return;
        if (currentUser) beerRuns.removeSelectedRunId(currentUser.id);
        currentRun = null;
        picker.setCurrentRun(null);
        clearTripState('This beer run is no longer available.');
        updateAuthForContext();
        await initializeRunContext({ notice: 'Your selected run is no longer available. Choosing your default run instead.' });
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

        lastRefreshTime = new Date();
        setSyncStatus(`Synced ${lastRefreshTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    }

    function activateTab(tabId) {
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
        if (document.getElementById('hide-wrapped-ended').checked) localStorage.setItem(WRAPPED_ENDED_STORAGE_KEY, 'true');
        modal.style.display = 'none';
    }

    function showWrappedEndedModal() {
        if (localStorage.getItem(WRAPPED_ENDED_STORAGE_KEY) === 'true') return;
        if (document.getElementById('instructions-modal').style.display === 'flex') return;
        document.getElementById('wrapped-ended-modal').style.display = 'flex';
    }

    function initWrappedEndedModal() {
        document.getElementById('close-wrapped-ended').addEventListener('click', closeWrappedEndedModal);
        document.getElementById('wrapped-ended-done').addEventListener('click', closeWrappedEndedModal);
        document.getElementById('wrapped-ended-open').addEventListener('click', () => {
            if (document.getElementById('hide-wrapped-ended').checked) localStorage.setItem(WRAPPED_ENDED_STORAGE_KEY, 'true');
        });
    }

    function showStartupModals() {
        if (!authValidationComplete || !startupModalsPending) return;
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
            }
        });
    });

    document.getElementById('login-btn').addEventListener('click', auth.openLoginModal);
    document.getElementById('logout-btn').addEventListener('click', () => {
        auth.removeToken();
        resetIdentity();
        void initializeRunContext();
    });
    document.getElementById('close-login').addEventListener('click', () => {
        auth.closeLoginModal();
        showStartupModals();
    });
    document.getElementById('close-user-modal').addEventListener('click', ui.clearUserModal);

    window.addEventListener('click', event => {
        const loginModal = document.getElementById('login-modal');
        if (event.target === loginModal) {
            auth.closeLoginModal();
            showStartupModals();
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
        await establishAuthenticatedContext();
        showStartupModals();
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
        };
        const validation = signup.validateSignupFields(fields);
        if (!validation.valid) {
            auth.showSignupError(signup.formatValidationErrors(validation.errors));
            return;
        }
        const submitButton = document.getElementById('signup-submit');
        submitButton.disabled = true;
        try {
            const response = await api.signup(validation.username, fields.password, fields.signupCode);
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

    document.getElementById('drink_type_select').addEventListener('change', ui.updateFormToggles);
    document.getElementById('quantity_select').addEventListener('change', ui.updateFormToggles);
    const locationStatus = document.getElementById('location-status');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    document.getElementById('get-location-btn').addEventListener('click', () => ui.requestLocation(latInput, lngInput, locationStatus));

    document.getElementById('entry-form').addEventListener('submit', async event => {
        event.preventDefault();
        const token = auth.getToken();
        if (!token) {
            alert('You must be logged in.');
            updateAuthForContext();
            return;
        }
        if (!latInput.value) {
            alert('Pin location first.');
            return;
        }
        if (!currentRun) {
            alert('Choose an available beer run first.');
            return;
        }
        if (!canWriteCurrentRun()) {
            alert(`You are not a member of ${currentRun.name}.`);
            return;
        }

        const targetRun = currentRun;
        const entryForm = document.getElementById('entry-form');
        const formData = new FormData(entryForm);
        const finalType = document.getElementById('drink_type_select').value === 'Other'
            ? document.getElementById('custom_drink_type').value
            : document.getElementById('drink_type_select').value;
        const finalQuantity = document.getElementById('quantity_select').value === 'custom'
            ? document.getElementById('custom_quantity').value
            : document.getElementById('quantity_select').value;
        if (!finalType || !finalQuantity) {
            alert('Complete all fields.');
            return;
        }
        formData.set('drink_type', finalType);
        formData.set('quantity', finalQuantity);
        formData.set('client_timestamp', ui.getLocalTimestamp());
        formData.set('client_timezone', Intl.DateTimeFormat().resolvedOptions().timeZone || '');
        formData.set('client_timezone_code', ui.getLocalTimeZoneCode());
        if (formData.has('username')) formData.delete('username');

        const submitButton = document.getElementById('submit-btn');
        submitButton.disabled = true;
        submitButton.innerText = 'SENDING...';
        try {
            const response = await api.submitEntry(targetRun.id, formData, token);
            if (response.ok) {
                entryForm.innerHTML = `<div class="card" style="text-align:center; padding: 40px;"><h2 style="justify-content:center; color: var(--success-color);">ENTRY SENT</h2><p style="color: var(--text-secondary);">Your drink has been logged.</p><button onclick="window.location.reload()" style="background: var(--accent-primary); color: #000; margin-top: 20px;">LOG ANOTHER</button></div>`;
                if (Number(currentRun?.id) === Number(targetRun.id)) refreshData(true);
                return;
            }
            if (response.status === 401) handleRejectedSession();
            else if (response.status === 404 && Number(currentRun?.id) === Number(targetRun.id)) await recoverFromAccessLoss(targetRun);
            else alert(`Upload failed: ${(await response.text()) || response.statusText}`);
        } catch (error) {
            console.error('Submission error:', error);
            alert('Upload failed. Check console.');
        } finally {
            const activeSubmitButton = document.getElementById('submit-btn');
            if (activeSubmitButton) {
                activeSubmitButton.disabled = false;
                activeSubmitButton.innerText = 'SEND ENTRY';
            }
        }
    });

    initInstructionsModal();
    initWrappedEndedModal();
    document.getElementById('sync-bar').addEventListener('click', () => refreshData(true));
    setInterval(() => refreshData(false), 30000);

    (async () => {
        const authPromptShown = await validateStoredSession();
        if (!authPromptShown) showStartupModals();
        const config = await api.fetchConfig();
        ui.renderDrinkOptions(config);
        ui.requestLocation(latInput, lngInput, locationStatus);
    })();
});

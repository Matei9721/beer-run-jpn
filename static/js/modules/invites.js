import * as api from './api.js?v=16';

function validPreview(data) {
    return Boolean(
        data
        && Number.isInteger(Number(data.beer_run_id))
        && Number(data.beer_run_id) > 0
        && typeof data.beer_run_name === 'string'
        && data.beer_run_name.length > 0
    );
}

function validAcceptedRun(data, previewId) {
    return Boolean(
        data
        && Number(data.id) === Number(previewId)
        && typeof data.name === 'string'
        && typeof data.is_public === 'boolean'
        && typeof data.created_at === 'string'
        && data.created_at.length > 0
        && Number.isInteger(data.member_count)
        && data.member_count > 0
        && (data.current_user_role === 'member' || data.current_user_role === 'owner')
    );
}

export function validateOwnerInviteResponse(data, runId) {
    if (!data || Number(data.beer_run_id) !== Number(runId)
        || !/^[A-Za-z0-9_-]{43}$/.test(data.code)
        || typeof data.invite_url !== 'string' || !data.invite_url.startsWith('/?')
        || typeof data.beer_run_name !== 'string' || !data.beer_run_name
        || typeof data.created_at !== 'string' || !data.created_at) return null;
    try {
        const url = new URL(data.invite_url, window.location.origin);
        const values = url.searchParams.getAll('invite');
        if (url.origin !== window.location.origin || url.pathname !== '/' || url.hash
            || values.length !== 1 || values[0] !== data.code
            || [...url.searchParams.keys()].some(key => key !== 'invite')) return null;
        return { data, url: url.toString() };
    } catch (error) {
        return null;
    }
}

export function createInviteFlow({
    getCurrentUser,
    getToken,
    getContextGeneration,
    onOpenAuth,
    isMemberOfRun,
    onAccepted,
    onRejectedSession,
    onReconcile,
    onAllowStartup,
}) {
    const modal = document.getElementById('invite-modal');
    const dialog = document.getElementById('invite-dialog');
    const copy = document.getElementById('invite-dialog-copy');
    const status = document.getElementById('invite-dialog-status');
    const error = document.getElementById('invite-dialog-error');
    const actions = document.getElementById('invite-dialog-actions');
    const accept = document.getElementById('accept-invite');
    const login = document.getElementById('login-to-join');
    const signup = document.getElementById('signup-to-join');
    const retry = document.getElementById('retry-invite');
    const close = document.getElementById('close-invite');

    let code = null;
    let preview = null;
    let pendingIntent = false;
    let acceptPending = false;
    let generation = 0;
    let previewController = null;
    let acceptController = null;
    let lastFocused = null;
    let active = false;
    let authSuspended = false;

    function setFeedback(message = '', isError = false) {
        error.textContent = isError ? message : '';
        status.textContent = isError ? '' : message;
    }

    function showModal() {
        active = true;
        modal.hidden = false;
        document.body.classList.add('invite-dialog-open');
        close.focus();
    }

    function hideModal() {
        modal.hidden = true;
        document.body.classList.remove('invite-dialog-open');
    }

    function clearState() {
        generation += 1;
        pendingIntent = false;
        acceptPending = false;
        preview = null;
        code = null;
        if (previewController) previewController.abort();
        if (acceptController) acceptController.abort();
        previewController = null;
        acceptController = null;
        authSuspended = false;
    }

    function scrubInvite(acceptedId = null) {
        const url = new URL(window.location.href);
        url.searchParams.delete('invite');
        if (acceptedId !== null) url.searchParams.set('run', String(acceptedId));
        window.history.replaceState({}, '', url.toString());
    }

    function focusableElements() {
        return [...dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), [href]')]
            .filter(element => !element.hidden && element.offsetParent !== null);
    }

    function onKeyDown(event) {
        if (modal.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            dismiss();
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

    function renderUnavailable(message = 'Invite not found or no longer available.', canRetry = false) {
        preview = null;
        copy.textContent = message;
        setFeedback();
        actions.hidden = false;
        accept.hidden = true;
        login.hidden = true;
        signup.hidden = true;
        retry.hidden = !canRetry;
    }

    function renderPreview() {
        const authenticated = Boolean(getCurrentUser() && getToken());
        const alreadyMember = authenticated && Boolean(isMemberOfRun?.(preview.beer_run_id));
        copy.textContent = alreadyMember
            ? `You're already a member of ${preview.beer_run_name}.`
            : `Join ${preview.beer_run_name}? Joining adds your account as a member of this run.`;
        setFeedback();
        actions.hidden = false;
        retry.hidden = true;
        accept.hidden = !authenticated || alreadyMember;
        login.hidden = authenticated;
        signup.hidden = authenticated;
    }

    async function loadPreview() {
        const currentGeneration = ++generation;
        if (previewController) previewController.abort();
        previewController = null;
        copy.textContent = 'Checking this invite...';
        actions.hidden = true;
        setFeedback();
        showModal();
        previewController = new AbortController();
        const result = await api.previewInvite(code, previewController.signal);
        if (currentGeneration !== generation || result?.aborted) return;
        previewController = null;
        if (result?.ok && result.status === 200 && validPreview(result.data)) {
            preview = result.data;
            renderPreview();
        } else if (result?.status === 404 || !result?.ok && !result?.network) {
            renderUnavailable();
        } else {
            renderUnavailable('Invite preview is temporarily unavailable. Try again.', true);
        }
    }

    function beginAuth(mode) {
        if (!preview || acceptPending) return;
        pendingIntent = true;
        authSuspended = false;
        hideModal();
        onOpenAuth(mode);
    }

    async function acceptInvite() {
        if (!preview || acceptPending || !getCurrentUser() || !getToken()) return;
        const acceptedPreview = preview;
        const acceptedCode = code;
        const acceptedGeneration = generation;
        const acceptedUser = getCurrentUser();
        const acceptedToken = getToken();
        const context = getContextGeneration();
        acceptPending = true;
        pendingIntent = false;
        accept.disabled = true;
        login.disabled = true;
        signup.disabled = true;
        setFeedback('Joining run...');
        acceptController = new AbortController();
        const result = await api.acceptInvite(acceptedCode, acceptedToken, acceptController.signal);
        if (acceptedGeneration !== generation || acceptedUser?.id !== getCurrentUser()?.id
            || acceptedToken !== getToken() || context !== getContextGeneration()) return;
        acceptController = null;
        if (result?.status === 401) {
            acceptPending = false;
            pendingIntent = true;
            accept.disabled = false;
            login.disabled = false;
            signup.disabled = false;
            onRejectedSession?.();
            return;
        }
        if (result?.ok && result.status === 200 && validAcceptedRun(result.data, acceptedPreview.beer_run_id)) {
            const handled = await onAccepted(result.data, { code: acceptedCode, preview: acceptedPreview });
            if (handled !== false) {
                scrubInvite(result.data.id);
                clearState();
                hideModal();
                active = false;
                onAllowStartup?.();
            } else {
                acceptPending = false;
                accept.disabled = false;
                login.disabled = false;
                signup.disabled = false;
                renderPreview();
            }
            return;
        }
        acceptPending = false;
        accept.disabled = false;
        login.disabled = false;
        signup.disabled = false;
        if (result?.status === 404) {
            renderUnavailable();
            return;
        }
        if (result?.network || result?.ok) {
            const reconciled = await onReconcile?.(acceptedPreview.beer_run_id, acceptedUser, acceptedToken, context);
            if (acceptedGeneration !== generation || acceptedUser?.id !== getCurrentUser()?.id || acceptedToken !== getToken()) return;
            if (validAcceptedRun(reconciled, acceptedPreview.beer_run_id)) {
                const handled = await onAccepted(reconciled, { code: acceptedCode, preview: acceptedPreview });
                if (handled !== false) {
                    scrubInvite(reconciled.id);
                    clearState();
                    hideModal();
                    active = false;
                    onAllowStartup?.();
                } else {
                    acceptPending = false;
                    accept.disabled = false;
                    login.disabled = false;
                    signup.disabled = false;
                    renderPreview();
                }
                return;
            }
        }
        renderPreview();
        setFeedback('We could not confirm the join. Try again.', true);
    }

    function dismiss() {
        if (acceptPending) return;
        scrubInvite();
        clearState();
        hideModal();
        active = false;
        (lastFocused || document.getElementById('beer-run-trigger'))?.focus?.();
        onAllowStartup?.();
    }

    modal.addEventListener('click', event => {
        if (event.target === modal) dismiss();
    });
    close.addEventListener('click', dismiss);
    accept.addEventListener('click', acceptInvite);
    login.addEventListener('click', () => beginAuth('login'));
    signup.addEventListener('click', () => beginAuth('signup'));
    retry.addEventListener('click', loadPreview);
    document.addEventListener('keydown', onKeyDown);

    return {
        initialize() {
            const params = new URL(window.location.href).searchParams;
            const values = params.getAll('invite');
            if (values.length !== 1 || !values[0]) {
                if (values.length) {
                    code = null;
                    showModal();
                    renderUnavailable();
                    return true;
                }
                return false;
            }
            code = values[0];
            lastFocused = document.activeElement;
            void loadPreview();
            return true;
        },
        isActive() {
            return active;
        },
        resumeAfterAuth() {
            if (!pendingIntent || !preview || !getCurrentUser() || !getToken()) return false;
            pendingIntent = false;
            showModal();
            void acceptInvite();
            return true;
        },
        authClosed() {
            if (!pendingIntent && !authSuspended) return false;
            pendingIntent = false;
            authSuspended = false;
            showModal();
            if (preview) renderPreview();
            else renderUnavailable();
            return true;
        },
        suspendForAuth() {
            if (!active || modal.hidden || acceptPending) return false;
            authSuspended = true;
            hideModal();
            return true;
        },
        cancelContinuation() {
            pendingIntent = false;
        },
        invalidate() {
            generation += 1;
            if (acceptController) acceptController.abort();
            if (previewController) previewController.abort();
            acceptController = null;
            previewController = null;
            acceptPending = false;
            if (preview && !modal.hidden) renderPreview();
        },
        dismiss,
    };
}

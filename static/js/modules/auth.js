export function getToken() {
    return localStorage.getItem('access_token');
}

export function setToken(token) {
    localStorage.setItem('access_token', token);
}

export function removeToken() {
    localStorage.removeItem('access_token');
}

export const AUTH_STATES = Object.freeze({
    UNAUTHENTICATED: 'unauthenticated',
    VALIDATING: 'validating',
    AUTHENTICATED: 'authenticated',
    VALIDATION_FAILED: 'validation-failed'
});

const DEFAULT_LOGIN_ERROR = 'Invalid credentials';

export function updateAuthUI(state = AUTH_STATES.UNAUTHENTICATED, canWrite = false) {
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const authRestrictedElements = document.querySelectorAll('.auth-restricted');

    const isAuthenticated = state === AUTH_STATES.AUTHENTICATED;
    const isValidating = state === AUTH_STATES.VALIDATING;

    if (isAuthenticated) {
        loginBtn.style.display = 'none';
        logoutBtn.style.display = '';
        authRestrictedElements.forEach(el => el.style.display = canWrite ? '' : 'none');
        if (!canWrite) {
            const activeTab = document.querySelector('.tab-btn.active');
            if (activeTab && activeTab.classList.contains('auth-restricted')) {
                document.querySelector('[data-tab="leaderboard-tab"]').click();
            }
        }
    } else {
        loginBtn.style.display = isValidating ? 'none' : '';
        logoutBtn.style.display = 'none';
        authRestrictedElements.forEach(el => el.style.display = 'none');

        // If on a restricted tab, switch to leaderboard
        const activeTab = document.querySelector('.tab-btn.active');
        if (activeTab && activeTab.classList.contains('auth-restricted')) {
            document.querySelector('[data-tab="leaderboard-tab"]').click();
        }
    }
}

export function openLoginModal() {
    document.getElementById('login-modal').style.display = 'flex';
    setAuthMode('login');
}

export function showLoginPrompt(message) {
    openLoginModal();
    const loginError = document.getElementById('login-error');
    loginError.innerText = message;
    loginError.style.display = 'block';
}

export function resetLoginError() {
    const loginError = document.getElementById('login-error');
    loginError.innerText = DEFAULT_LOGIN_ERROR;
    loginError.style.display = 'none';
}

export function closeLoginModal() {
    document.getElementById('login-modal').style.display = 'none';
    resetLoginError();
    resetSignupForm();
}

/**
 * Show the Login or Sign Up panel of the auth modal. Switching modes clears
 * the previous mode's error message and never copies password or signup-code
 * values between the two forms.
 */
export function setAuthMode(mode) {
    const isLogin = mode === 'login';
    document.getElementById('login-form').classList.toggle('active', isLogin);
    document.getElementById('signup-form').classList.toggle('active', !isLogin);
    document.getElementById('auth-mode-login').classList.toggle('active', isLogin);
    document.getElementById('auth-mode-signup').classList.toggle('active', !isLogin);
    document.getElementById('auth-mode-login').setAttribute('aria-pressed', String(isLogin));
    document.getElementById('auth-mode-signup').setAttribute('aria-pressed', String(!isLogin));
    document.getElementById('auth-modal-title').innerText = isLogin ? 'Login' : 'Sign Up';

    resetLoginError();
    clearSignupError();

    const firstField = isLogin ? 'login-username' : 'signup-username';
    document.getElementById(firstField).focus();
}

export function showSignupError(message) {
    const errorEl = document.getElementById('signup-error');
    errorEl.innerText = message;
    errorEl.style.display = 'block';
}

export function clearSignupError() {
    const errorEl = document.getElementById('signup-error');
    errorEl.innerText = '';
    errorEl.style.display = 'none';
}

export function resetSignupForm() {
    const form = document.getElementById('signup-form');
    form.reset();
    // A successful signup leaves the submit button disabled from the in-flight
    // request; form.reset() does not clear it, so re-enable it here.
    document.getElementById('signup-submit').disabled = false;
    clearSignupError();
}

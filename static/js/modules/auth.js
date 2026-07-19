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

export function updateAuthUI(state = AUTH_STATES.UNAUTHENTICATED) {
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const authRestrictedElements = document.querySelectorAll('.auth-restricted');

    const isAuthenticated = state === AUTH_STATES.AUTHENTICATED;
    const isValidating = state === AUTH_STATES.VALIDATING;

    if (isAuthenticated) {
        loginBtn.style.display = 'none';
        logoutBtn.style.display = '';
        authRestrictedElements.forEach(el => el.style.display = '');
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
    const loginModal = document.getElementById('login-modal');
    resetLoginError();
    loginModal.style.display = 'flex';
    document.getElementById('login-username').focus();
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
    const loginModal = document.getElementById('login-modal');
    loginModal.style.display = 'none';
    resetLoginError();
}

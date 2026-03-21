export function getToken() {
    return localStorage.getItem('access_token');
}

export function setToken(token) {
    localStorage.setItem('access_token', token);
}

export function removeToken() {
    localStorage.removeItem('access_token');
}

export function updateAuthUI() {
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const authRestrictedElements = document.querySelectorAll('.auth-restricted');
    
    const token = getToken();
    if (token) {
        loginBtn.style.display = 'none';
        logoutBtn.style.display = '';
        authRestrictedElements.forEach(el => el.style.display = '');
    } else {
        loginBtn.style.display = '';
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
    loginModal.style.display = 'flex';
    document.getElementById('login-username').focus();
}

export function closeLoginModal() {
    const loginModal = document.getElementById('login-modal');
    const loginError = document.getElementById('login-error');
    loginModal.style.display = 'none';
    loginError.style.display = 'none';
}

import * as api from './modules/api.js?v=9';
import * as auth from './modules/auth.js?v=9';
import * as mapMod from './modules/map.js?v=9';
import * as ui from './modules/ui.js?v=9';

document.addEventListener('DOMContentLoaded', () => {
    const INSTRUCTIONS_STORAGE_KEY = 'beerRunJpn.hideInstructions';

    // --- Global State ---
    let lastRefreshTime = new Date();
    let currentLeaderboard = [];
    let currentEntries = [];

    // --- Core Refresh Logic ---
    async function refreshData(isManual = false) {
        const syncStatus = document.getElementById('sync-status');
        const syncDot = document.getElementById('sync-dot');
        const userFilter = document.getElementById('user-filter');
        const leaderboardData = document.getElementById('leaderboard-data');

        syncStatus.innerText = 'Syncing...';
        syncDot.classList.add('syncing');
        
        const [leaderboard, entries] = await Promise.all([
            api.fetchLeaderboard(),
            api.fetchEntries(userFilter.value)
        ]);
        
        currentLeaderboard = leaderboard;
        currentEntries = entries;
        
        // Update Leaderboard UI
        ui.renderLeaderboard(leaderboard, leaderboardData);
        
        // Update Map Filter Dropdown
        const currentFilter = userFilter.value;
        const options = ['<option value="">All Users</option>'];
        leaderboard.forEach(user => {
            options.push(`<option value="${user.username}">${user.username}</option>`);
        });
        userFilter.innerHTML = options.join('');
        userFilter.value = currentFilter;

        // Update Map Markers
        mapMod.updateMarkers(entries, isManual);
        
        lastRefreshTime = new Date();
        syncStatus.innerText = `Synced ${lastRefreshTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
        syncDot.classList.remove('syncing');
    }

    function activateTab(tabId) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
        document.getElementById(tabId).classList.add('active');
    }

    async function focusEntryOnMap(entry) {
        document.getElementById('user-modal').style.display = 'none';
        activateTab('map-tab');

        const userFilter = document.getElementById('user-filter');
        if (userFilter.value) {
            userFilter.value = '';
            await refreshData(false);
        }

        setTimeout(() => {
            mapMod.map.invalidateSize();
            if (!mapMod.focusEntry(entry)) {
                refreshData(false).then(() => mapMod.focusEntry(entry));
            }
        }, 200);
    }

    function closeInstructionsModal() {
        const instructionsModal = document.getElementById('instructions-modal');
        const hideInstructions = document.getElementById('hide-instructions');

        if (hideInstructions.checked) {
            localStorage.setItem(INSTRUCTIONS_STORAGE_KEY, 'true');
        }

        instructionsModal.style.display = 'none';
    }

    function initInstructionsModal() {
        const instructionsModal = document.getElementById('instructions-modal');
        const closeInstructions = document.getElementById('close-instructions');
        const instructionsDone = document.getElementById('instructions-done');

        closeInstructions.addEventListener('click', closeInstructionsModal);
        instructionsDone.addEventListener('click', closeInstructionsModal);

        if (localStorage.getItem(INSTRUCTIONS_STORAGE_KEY) !== 'true') {
            instructionsModal.style.display = 'flex';
        }
    }

    // --- Tab Switching ---
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            
            activateTab(tabId);

            if (tabId === 'map-tab') {
                setTimeout(() => {
                    mapMod.map.invalidateSize();
                    refreshData(true); // Ensure markers are fitted to bounds when switching to map
                    ui.showMapHint();
                }, 200);
            }
        });
    });

    // --- Auth Event Listeners ---
    document.getElementById('login-btn').addEventListener('click', auth.openLoginModal);
    document.getElementById('logout-btn').addEventListener('click', () => {
        auth.removeToken();
        auth.updateAuthUI();
    });
    document.getElementById('close-login').addEventListener('click', auth.closeLoginModal);
    document.getElementById('close-user-modal').addEventListener('click', () => {
        document.getElementById('user-modal').style.display = 'none';
    });
    
    window.addEventListener('click', (event) => {
        const loginModal = document.getElementById('login-modal');
        const userModal = document.getElementById('user-modal');
        const instructionsModal = document.getElementById('instructions-modal');
        if (event.target == loginModal) auth.closeLoginModal();
        if (event.target == userModal) userModal.style.display = 'none';
        if (event.target == instructionsModal) closeInstructionsModal();
    });

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const loginError = document.getElementById('login-error');
        
        try {
            const response = await api.login(username, password);
            if (response.ok) {
                const data = await response.json();
                auth.setToken(data.access_token);
                auth.closeLoginModal();
                document.getElementById('login-form').reset();
                auth.updateAuthUI();
                refreshData(true);
            } else {
                loginError.style.display = 'block';
            }
        } catch (error) {
            console.error("Login error:", error);
            loginError.innerText = "Connection error";
            loginError.style.display = 'block';
        }
    });

    // --- Tooltip Event Delegation ---
    document.addEventListener('mouseover', (e) => {
        const trigger = e.target.closest('.tooltip-trigger');
        if (trigger) ui.createTooltip(trigger, trigger.dataset.tooltip);
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.closest('.tooltip-trigger')) ui.removeTooltip();
    });
    
    document.addEventListener('click', (e) => {
         const trigger = e.target.closest('.tooltip-trigger');
         if (trigger) {
            ui.createTooltip(trigger, trigger.dataset.tooltip);
         } else {
            ui.removeTooltip();
         }
    });

    // --- Leaderboard Card Clicks ---
    document.addEventListener('click', (e) => {
        const card = e.target.closest('.rank-card');
        if (card) {
            const username = card.getAttribute('data-username');
            if (username) {
                ui.showUserModal(username, currentLeaderboard, currentEntries, focusEntryOnMap);
            }
        }
    });

    // --- Map Actions ---
    document.getElementById('close-sheet').addEventListener('click', mapMod.closeDetail);
    mapMod.map.on('click', () => {
        mapMod.closeDetail();
        const hint = document.querySelector('.map-hint');
        if(hint) {
            hint.classList.remove('visible');
            setTimeout(() => hint.remove(), 400);
        }
    });

    document.getElementById('user-filter').addEventListener('change', () => refreshData(true));

    // --- Form Actions ---
    document.getElementById('drink_type_select').addEventListener('change', ui.updateFormToggles);
    document.getElementById('quantity_select').addEventListener('change', ui.updateFormToggles);
    
    const locationStatus = document.getElementById('location-status');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    
    document.getElementById('get-location-btn').addEventListener('click', () => ui.requestLocation(latInput, lngInput, locationStatus));

    document.getElementById('entry-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const token = auth.getToken();
        if (!token) {
            alert("You must be logged in.");
            auth.updateAuthUI();
            return;
        }

        if (!latInput.value) { alert("Pin location first."); return; }

        const entryForm = document.getElementById('entry-form');
        const formData = new FormData(entryForm);
        
        // Finalize drink type and quantity
        const finalType = document.getElementById('drink_type_select').value === 'Other' ? 
                          document.getElementById('custom_drink_type').value : 
                          document.getElementById('drink_type_select').value;
        const finalQuantity = document.getElementById('quantity_select').value === 'custom' ? 
                             document.getElementById('custom_quantity').value : 
                             document.getElementById('quantity_select').value;

        if (!finalType || !finalQuantity) { alert("Complete all fields."); return; }

        formData.set('drink_type', finalType);
        formData.set('quantity', finalQuantity);
        formData.set('client_timestamp', ui.getLocalTimestamp());
        formData.set('client_timezone', Intl.DateTimeFormat().resolvedOptions().timeZone || '');
        formData.set('client_timezone_code', ui.getLocalTimeZoneCode());
        if(formData.has('username')) formData.delete('username');

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerText = "SENDING...";

        try {
            const response = await api.submitEntry(formData, token);
            if (response.ok) {
                entryForm.innerHTML = `<div class="card" style="text-align:center; padding: 40px;">
                    <h2 style="justify-content:center; color: var(--success-color);">ENTRY SENT</h2>
                    <p style="color: var(--text-secondary);">Your drink has been logged.</p>
                    <button onclick="window.location.reload()" style="background: var(--accent-primary); color: #000; margin-top: 20px;">LOG ANOTHER</button>
                </div>`;
                refreshData(true);
            } else {
                if (response.status === 401) {
                    alert("Session expired. Please login again.");
                    auth.removeToken();
                    auth.updateAuthUI();
                } else {
                    const errorText = await response.text();
                    alert(`Upload failed: ${errorText || response.statusText}`);
                }
                submitBtn.disabled = false;
                submitBtn.innerText = "SEND ENTRY";
            }
        } catch (err) {
            console.error("Submission error:", err);
            alert("Upload failed. Check console.");
            submitBtn.disabled = false;
            submitBtn.innerText = "SEND ENTRY";
        }
    });

    // --- Init & Refresh Loop ---
    initInstructionsModal();

    document.getElementById('sync-bar').addEventListener('click', () => refreshData(true));
    setInterval(() => refreshData(false), 30000);
    
    // Initial Data Load
    (async () => {
        const config = await api.fetchConfig();
        ui.renderDrinkOptions(config);
        
        ui.requestLocation(latInput, lngInput, locationStatus);
        auth.updateAuthUI();
        refreshData(true);
    })();
});

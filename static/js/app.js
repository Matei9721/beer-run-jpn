document.addEventListener('DOMContentLoaded', () => {
    // --- Global State ---
    let lastRefreshTime = new Date();

    // --- Auth Logic ---
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const loginModal = document.getElementById('login-modal');
    const closeLogin = document.getElementById('close-login');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const authRestrictedElements = document.querySelectorAll('.auth-restricted');

    function updateAuthUI() {
        const token = localStorage.getItem('access_token');
        if (token) {
            loginBtn.style.display = 'none';
            logoutBtn.style.display = 'block';
            authRestrictedElements.forEach(el => el.style.display = 'block');
        } else {
            loginBtn.style.display = 'block';
            logoutBtn.style.display = 'none';
            authRestrictedElements.forEach(el => el.style.display = 'none');
            
            // If on a restricted tab, switch to leaderboard
            const activeTab = document.querySelector('.tab-btn.active');
            if (activeTab && activeTab.classList.contains('auth-restricted')) {
                document.querySelector('[data-tab="leaderboard-tab"]').click();
            }
        }
    }

    loginBtn.addEventListener('click', () => {
        loginModal.style.display = 'flex';
        document.getElementById('login-username').focus();
    });

    closeLogin.addEventListener('click', () => {
        loginModal.style.display = 'none';
        loginError.style.display = 'none';
    });

    window.onclick = (event) => {
        if (event.target == loginModal) {
            loginModal.style.display = 'none';
        }
    };

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        
        try {
            const response = await fetch('/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: params
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                loginModal.style.display = 'none';
                loginForm.reset();
                updateAuthUI();
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

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('access_token');
        updateAuthUI();
    });

    // --- Tabs Logic ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');

            if (tabId === 'map-tab') {
                setTimeout(() => {
                    map.invalidateSize();
                    updateMapMarkers(document.getElementById('user-filter').value);
                }, 200);
            }
        });
    });

    // --- Leaderboard Logic ---
    const leaderboardData = document.getElementById('leaderboard-data');
    
    async function fetchLeaderboard() {
        try {
            const response = await fetch('/api/leaderboard');
            const data = await response.json();
            
            // Populate Map filter dropdown
            const userFilter = document.getElementById('user-filter');
            const currentFilter = userFilter.value;
            // Keep "All Users"
            const options = ['<option value="">All Users</option>'];
            data.forEach(user => {
                options.push(`<option value="${user.username}">${user.username}</option>`);
            });
            userFilter.innerHTML = options.join('');
            userFilter.value = currentFilter;

            if (data.length === 0) {
                leaderboardData.innerHTML = "<p style='color: #888; text-align: center; padding: 20px;'>No entries found.</p>";
                return;
            }

            let html = `
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Total (L)</th>
                            <th>Alc (L)</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach(user => {
                html += `
                    <tr>
                        <td>${user.username}</td>
                        <td>${user.total_liters.toFixed(2)}</td>
                        <td>${user.total_alcohol.toFixed(3)}</td>
                    </tr>
                `;
            });

            html += `</tbody></table>`;
            leaderboardData.innerHTML = html;
        } catch (error) {
            console.error("Error fetching leaderboard:", error);
        }
    }

    // --- Map Logic ---
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    });

    const map = L.map('map').setView([35.6895, 139.6917], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OSM'
    }).addTo(map);

    const markerGroup = L.markerClusterGroup({
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true
    }).addTo(map);

    const detailSheet = document.getElementById('detail-sheet');
    const detailTitle = document.getElementById('detail-title');
    const detailMeta = document.getElementById('detail-meta');
    const detailImg = document.getElementById('detail-img');
    const closeSheet = document.getElementById('close-sheet');

    // Make openDetail globally accessible for popup onclick events
    window.openDetail = function(entryJson) {
        const entry = JSON.parse(decodeURIComponent(entryJson));
        detailTitle.innerText = `${entry.username}`;
        detailMeta.innerHTML = `
            <strong>${entry.drink_type}</strong> ${entry.brand ? `(${entry.brand})` : ''}<br>
            ${entry.abv}% ABV | ${entry.quantity}L<br>
            <span style="font-size: 12px; opacity: 0.7;">Logged at ${new Date(entry.timestamp).toLocaleTimeString()}</span>
        `;
        
        if (entry.image_path) {
            detailImg.src = `/${entry.image_path.replace(/\\/g, '/')}`;
            detailImg.style.display = 'block';
        } else {
            detailImg.style.display = 'none';
        }
        
        detailSheet.classList.add('active');
    };

    function closeDetail() {
        detailSheet.classList.remove('active');
    }

    closeSheet.addEventListener('click', closeDetail);
    map.on('click', closeDetail);

    async function updateMapMarkers(username = "", shouldZoom = true) {
        markerGroup.clearLayers();
        try {
            const url = username ? `/api/entries?username=${encodeURIComponent(username)}` : '/api/entries';
            const response = await fetch(url);
            const entries = await response.json();

            entries.forEach(entry => {
                const entryJson = encodeURIComponent(JSON.stringify(entry));
                const popupContent = `
                    <div class="mini-popup">
                        ${entry.image_path ? `<img src="/${entry.image_path.replace(/\\/g, '/')}" class="popup-thumb">` : ''}
                        <div class="popup-info">
                            <span class="popup-user">${entry.username}</span>
                            <span class="popup-drink">${entry.drink_type}</span>
                            <a class="popup-link" onclick="openDetail('${entryJson}')">View Details</a>
                        </div>
                    </div>
                `;
                
                L.marker([entry.latitude, entry.longitude])
                    .bindPopup(popupContent)
                    .addTo(markerGroup);
            });

            if (shouldZoom && entries.length > 0) {
                const group = new L.featureGroup(markerGroup.getLayers());
                const bounds = group.getBounds();
                if (bounds.isValid()) map.fitBounds(bounds.pad(0.2));
            }
        } catch (error) {
            console.error("Error updating map:", error);
        }
    }

    // --- Global Refresh Logic ---
    const syncStatus = document.getElementById('sync-status');
    const syncDot = document.getElementById('sync-dot');
    const syncBar = document.getElementById('sync-bar');

    async function refreshData(isManual = false) {
        syncStatus.innerText = 'Syncing...';
        syncDot.classList.add('syncing');
        
        await Promise.all([fetchLeaderboard(), updateMapMarkers(document.getElementById('user-filter').value, isManual)]);
        
        lastRefreshTime = new Date();
        syncStatus.innerText = `Synced ${lastRefreshTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
        syncDot.classList.remove('syncing');
    }

    syncBar.addEventListener('click', () => refreshData(true));
    setInterval(() => refreshData(false), 30000);

    document.getElementById('user-filter').addEventListener('change', (e) => {
        updateMapMarkers(e.target.value, true);
    });

    // --- Log Form Logic ---
    const entryForm = document.getElementById('entry-form');
    const locationStatus = document.getElementById('location-status');
    const getLocationBtn = document.getElementById('get-location-btn');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    const usernameInput = document.getElementById('username'); // Might be null if removed from HTML, but we keep it for now

    // Custom Toggles
    const drinkTypeSelect = document.getElementById('drink_type_select');
    const customDrinkType = document.getElementById('custom_drink_type');
    const quantitySelect = document.getElementById('quantity_select');
    const customQuantity = document.getElementById('custom_quantity');

    drinkTypeSelect.addEventListener('change', () => {
        customDrinkType.style.display = drinkTypeSelect.value === 'Other' ? 'block' : 'none';
        if (drinkTypeSelect.value === 'Other') customDrinkType.focus();
    });

    quantitySelect.addEventListener('change', () => {
        customQuantity.style.display = quantitySelect.value === 'custom' ? 'block' : 'none';
        if (quantitySelect.value === 'custom') customQuantity.focus();
    });

    function requestLocation() {
        if (!navigator.geolocation) {
            locationStatus.innerText = "GPS Not Supported";
            locationStatus.style.color = "red";
            return;
        }

        locationStatus.innerText = "Requesting GPS...";
        locationStatus.style.color = "var(--text-primary)";

        navigator.geolocation.getCurrentPosition(
            (position) => {
                latInput.value = position.coords.latitude;
                lngInput.value = position.coords.longitude;
                locationStatus.innerText = `Ready: ${position.coords.latitude.toFixed(3)}, ${position.coords.longitude.toFixed(3)}`;
                locationStatus.style.color = 'var(--success-color)';
            },
            (err) => {
                locationStatus.innerText = "GPS Error - try again";
                locationStatus.style.color = "red";
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    // Only init location if we are logged in? No, can init anyway.
    requestLocation();
    getLocationBtn.addEventListener('click', requestLocation);

    entryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const token = localStorage.getItem('access_token');
        if (!token) {
            alert("You must be logged in.");
            updateAuthUI(); // Will show login button
            return;
        }

        if (!latInput.value) { alert("Pin location first."); return; }

        const formData = new FormData(entryForm);
        const finalType = drinkTypeSelect.value === 'Other' ? customDrinkType.value : drinkTypeSelect.value;
        const finalQuantity = quantitySelect.value === 'custom' ? customQuantity.value : quantitySelect.value;

        if (!finalType || !finalQuantity) { alert("Complete all fields."); return; }

        formData.set('drink_type', finalType);
        formData.set('quantity', finalQuantity);
        
        // Remove username if it exists in form data (it's ignored by backend anyway but clean up)
        if(formData.has('username')) formData.delete('username');

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerText = "SENDING...";

        try {
            const response = await fetch('/api/entries', { 
                method: 'POST', 
                body: formData,
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                entryForm.innerHTML = `<div class="card" style="text-align:center; padding: 40px;">
                    <h2 style="justify-content:center; color: var(--success-color);">ENTRY SENT</h2>
                    <p style="color: var(--text-secondary);">Your drink has been logged.</p>
                    <button onclick="window.location.reload()" style="background: var(--accent-primary); color: #000; margin-top: 20px;">LOG ANOTHER</button>
                </div>`;
                refreshData(true);
            } else {
                const errorText = await response.text();
                console.error("Server error:", errorText);
                if (response.status === 401) {
                    alert("Session expired. Please login again.");
                    localStorage.removeItem('access_token');
                    updateAuthUI();
                } else {
                    alert(`Upload failed: ${errorText || response.statusText}`);
                }
                submitBtn.disabled = false;
                submitBtn.innerText = "SEND ENTRY";
            }
        } catch (err) {
            console.error("Fetch error:", err);
            alert("Upload failed. Check console for details.");
            submitBtn.disabled = false;
            submitBtn.innerText = "SEND ENTRY";
        }
    });

    // Initial load
    updateAuthUI();
    refreshData(true);
});

document.addEventListener('DOMContentLoaded', () => {
    // --- Global State ---
    let lastRefreshTime = new Date();

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
            userFilter.innerHTML = '<option value="">All Users</option>';
            data.forEach(user => {
                const opt = document.createElement('option');
                opt.value = user.username;
                opt.innerText = user.username;
                userFilter.appendChild(opt);
            });
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

    async function updateMapMarkers(username = "", shouldZoom = true) {
        markerGroup.clearLayers();
        try {
            const url = username ? `/api/entries?username=${encodeURIComponent(username)}` : '/api/entries';
            const response = await fetch(url);
            const entries = await response.json();

            entries.forEach(entry => {
                const popupContent = `
                    <div class="popup-content">
                        <strong>${entry.username}</strong> drank a <strong>${entry.drink_type}</strong><br>
                        ${entry.brand ? `<em>${entry.brand}</em><br>` : ''}
                        ABV: ${entry.abv}% | Vol: ${entry.quantity}L<br>
                        <small style="color:#888">${new Date(entry.timestamp).toLocaleTimeString()}</small>
                        ${entry.image_path ? `<img src="/${entry.image_path.replace(/\\/g, '/')}" class="popup-img">` : ''}
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
    const usernameInput = document.getElementById('username');

    // Persistence
    const savedUsername = localStorage.getItem('boozerun_username');
    if (savedUsername && usernameInput) usernameInput.value = savedUsername;

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

    requestLocation();
    getLocationBtn.addEventListener('click', requestLocation);

    entryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!latInput.value) { alert("Pin location first."); return; }

        const formData = new FormData(entryForm);
        const finalType = drinkTypeSelect.value === 'Other' ? customDrinkType.value : drinkTypeSelect.value;
        const finalQuantity = quantitySelect.value === 'custom' ? customQuantity.value : quantitySelect.value;

        if (!finalType || !finalQuantity) { alert("Complete all fields."); return; }

        formData.set('drink_type', finalType);
        formData.set('quantity', finalQuantity);

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerText = "SENDING...";

        try {
            const response = await fetch('/api/entries', { method: 'POST', body: formData });
            if (response.ok) {
                localStorage.setItem('boozerun_username', usernameInput.value);
                entryForm.innerHTML = `<div class="card" style="text-align:center; padding: 40px;">
                    <h2 style="justify-content:center; color: var(--success-color);">ENTRY SENT</h2>
                    <p style="color: var(--text-secondary);">Your drink has been logged.</p>
                    <button onclick="window.location.reload()" style="background: var(--accent-primary); color: #000; margin-top: 20px;">LOG ANOTHER</button>
                </div>`;
                refreshData(true);
            }
        } catch (err) {
            alert("Upload failed.");
            submitBtn.disabled = false;
            submitBtn.innerText = "SEND ENTRY";
        }
    });

    // Initial load
    refreshData(true);
});

document.addEventListener('DOMContentLoaded', () => {
    // --- Tabs Logic ---
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            console.log('Switching to tab:', tabId);
            
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');

            if (tabId === 'map-tab') {
                // Leaflet needs to be notified when the container size changes (hidden to shown)
                setTimeout(() => {
                    console.log('Invalidating map size...');
                    map.invalidateSize();
                    updateMapMarkers(document.getElementById('user-filter').value);
                }, 200);
            }
        });
    });

    // --- Leaderboard Logic ---
    const leaderboardData = document.getElementById('leaderboard-data');
    fetchLeaderboard();

    async function fetchLeaderboard() {
        try {
            console.log('Fetching leaderboard...');
            const response = await fetch('/api/leaderboard');
            const data = await response.json();
            console.log('Leaderboard data:', data);
            
            // Populate Map filter dropdown while we're at it
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
                leaderboardData.innerHTML = "<p>No drinks logged yet. Be the first!</p>";
                return;
            }

            let html = `
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Total (L)</th>
                            <th>Pure Alc (L)</th>
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
            leaderboardData.innerHTML = "<p>Error loading data.</p>";
        }
    }

    // --- Map Logic ---
    // Fix for Leaflet default icon issues with some build setups/CDNs
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    });

    console.log('Initializing map...');
    const map = L.map('map').setView([35.6895, 139.6917], 5); // Default to Japan
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Initialize MarkerCluster group
    const markerGroup = L.markerClusterGroup({
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true
    }).addTo(map);

    async function updateMapMarkers(username = "") {
        console.log(`Updating markers for: ${username || 'All Users'}`);
        markerGroup.clearLayers();
        try {
            const url = username ? `/api/entries?username=${encodeURIComponent(username)}` : '/api/entries';
            const response = await fetch(url);
            const entries = await response.json();
            console.log(`Fetched ${entries.length} entries:`, entries);

            if (entries.length === 0) {
                console.log('No entries to show on map.');
                return;
            }

            entries.forEach(entry => {
                console.log(`Adding marker at: ${entry.latitude}, ${entry.longitude}`);
                const popupContent = `
                    <div class="popup-content">
                        <strong>${entry.username}</strong> drank a <strong>${entry.drink_type}</strong><br>
                        ${entry.brand ? `<em>${entry.brand}</em><br>` : ''}
                        ABV: ${entry.abv}% | Vol: ${entry.quantity}L<br>
                        <small>${new Date(entry.timestamp).toLocaleString()}</small>
                        ${entry.image_path ? `<img src="/${entry.image_path.replace(/\\/g, '/')}" class="popup-img">` : ''}
                    </div>
                `;
                L.marker([entry.latitude, entry.longitude])
                    .bindPopup(popupContent)
                    .addTo(markerGroup);
            });

            // Zoom to markers
            const group = new L.featureGroup(markerGroup.getLayers());
            const bounds = group.getBounds();
            if (bounds.isValid()) {
                console.log('Fitting map to bounds:', bounds);
                map.fitBounds(bounds.pad(0.2));
            } else {
                console.warn('Invalid bounds for marker group.');
            }
        } catch (error) {
            console.error("Error updating map:", error);
        }
    }

    document.getElementById('user-filter').addEventListener('change', (e) => {
        updateMapMarkers(e.target.value);
    });

    // Don't update markers until we switch to the tab or after a slight delay
    // to ensure the map container exists and has dimensions
    setTimeout(() => updateMapMarkers(), 500);

    // --- Log Form Logic ---
    const entryForm = document.getElementById('entry-form');
    const locationStatus = document.getElementById('location-status');
    const getLocationBtn = document.getElementById('get-location-btn');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    const usernameInput = document.getElementById('username');

    // Load persisted username
    const savedUsername = localStorage.getItem('boozerun_username');
    if (savedUsername && usernameInput) {
        usernameInput.value = savedUsername;
    }

    // Custom field toggles
    const drinkTypeSelect = document.getElementById('drink_type_select');
    const customDrinkType = document.getElementById('custom_drink_type');
    const quantitySelect = document.getElementById('quantity_select');
    const customQuantity = document.getElementById('custom_quantity');

    if (drinkTypeSelect && customDrinkType) {
        drinkTypeSelect.addEventListener('change', () => {
            console.log('Drink type changed to:', drinkTypeSelect.value);
            if (drinkTypeSelect.value === 'Other') {
                customDrinkType.style.display = 'block';
                customDrinkType.focus();
            } else {
                customDrinkType.style.display = 'none';
            }
        });
    }

    if (quantitySelect && customQuantity) {
        quantitySelect.addEventListener('change', () => {
            console.log('Quantity changed to:', quantitySelect.value);
            if (quantitySelect.value === 'custom') {
                customQuantity.style.display = 'block';
                customQuantity.focus();
            } else {
                customQuantity.style.display = 'none';
            }
        });
    }

    function requestLocation() {
        if (!navigator.geolocation) {
            locationStatus.innerText = "Error: Geolocation not supported.";
            locationStatus.style.color = "red";
            return;
        }

        // Check for secure context (HTTPS)
        if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
            locationStatus.innerText = "Error: HTTPS required for location on mobile.";
            locationStatus.style.color = "orange";
        } else {
            locationStatus.innerText = "Requesting location permission...";
            locationStatus.style.color = "var(--text-primary)";
        }

        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };

        navigator.geolocation.getCurrentPosition(
            (position) => {
                latInput.value = position.coords.latitude;
                lngInput.value = position.coords.longitude;
                locationStatus.innerText = `Location captured: ${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`;
                locationStatus.style.color = 'var(--success-color)';
                console.log('Location success:', position.coords);
            },
            (error) => {
                console.error('Location error:', error);
                let msg = "Error: Location access denied.";
                if (error.code === error.TIMEOUT) msg = "Error: Location request timed out.";
                if (error.code === error.POSITION_UNAVAILABLE) msg = "Error: Position unavailable.";
                
                locationStatus.innerText = msg;
                locationStatus.style.color = "red";
            },
            options
        );
    }

    // Attempt on load
    requestLocation();

    // Re-request on button click (User Gesture)
    getLocationBtn.addEventListener('click', () => {
        requestLocation();
    });

    entryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!latInput.value) {
            alert("Please capture your location first using the button.");
            return;
        }

        const usernameValue = usernameInput.value;
        const formData = new FormData(entryForm);

        // Handle custom values
        const finalType = drinkTypeSelect.value === 'Other' ? customDrinkType.value : drinkTypeSelect.value;
        const finalQuantity = quantitySelect.value === 'custom' ? customQuantity.value : quantitySelect.value;

        if (!finalType) {
            alert("Please specify the drink type.");
            return;
        }
        if (!finalQuantity || isNaN(parseFloat(finalQuantity))) {
            alert("Please specify a valid quantity.");
            return;
        }

        formData.set('drink_type', finalType);
        formData.set('quantity', finalQuantity);

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerText = "Logging...";

        try {
            const response = await fetch('/api/entries', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                // Save username for next time
                localStorage.setItem('boozerun_username', usernameValue);
                
                entryForm.innerHTML = `<div class="success-msg">🔥 Logged! 🔥</div>
                                      <button onclick="window.location.reload()">Log Another</button>`;
                fetchLeaderboard();
                updateMapMarkers();
            } else {
                throw new Error("Failed");
            }
        } catch (error) {
            alert("Error logging drink.");
            submitBtn.disabled = false;
            submitBtn.innerText = "Log It!";
        }
    });
});

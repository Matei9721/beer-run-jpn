// --- Tooltip & Hint System ---
let tooltipElem = null;
let mapHintShown = false;

export function createTooltip(target, text) {
    if (tooltipElem) tooltipElem.remove();

    tooltipElem = document.createElement('div');
    tooltipElem.className = 'custom-tooltip';
    tooltipElem.innerText = text;
    document.body.appendChild(tooltipElem);

    const rect = target.getBoundingClientRect();
    let top = rect.top - tooltipElem.offsetHeight - 10;
    let left = rect.left + (rect.width / 2) - (tooltipElem.offsetWidth / 2);

    if (left < 10) left = 10;
    if (left + tooltipElem.offsetWidth > window.innerWidth) left = window.innerWidth - tooltipElem.offsetWidth - 10;
    if (top < 10) top = rect.bottom + 10;

    tooltipElem.style.top = `${top + window.scrollY}px`;
    tooltipElem.style.left = `${left + window.scrollX}px`;

    void tooltipElem.offsetWidth;
    tooltipElem.classList.add('visible');
}

export function removeTooltip() {
    if (tooltipElem) {
        tooltipElem.classList.remove('visible');
        const el = tooltipElem;
        setTimeout(() => { if (el && !el.classList.contains('visible')) el.remove(); }, 200);
        tooltipElem = null;
    }
}

export function showMapHint() {
    if (mapHintShown) return;
    const mapContainer = document.querySelector('#map-tab .card');
    if (!mapContainer || document.querySelector('.map-hint')) return;

    const hint = document.createElement('div');
    hint.className = 'map-hint';
    hint.innerHTML = '<span class="map-hint-icon">💡</span> Tap markers to see details <span class="map-hint-close">&times;</span>';

    hint.addEventListener('click', () => {
        hint.classList.remove('visible');
        setTimeout(() => hint.remove(), 400);
        mapHintShown = true;
    });

    mapContainer.style.position = 'relative';
    mapContainer.appendChild(hint);
    setTimeout(() => hint.classList.add('visible'), 500);
}

// --- Log Form Logic ---
export function renderDrinkOptions(config) {
    const drinkTypeSelect = document.getElementById('drink_type_select');
    const quantitySelect = document.getElementById('quantity_select');

    // Clear and populate Drink Types
    if (config.types && config.types.length > 0) {
        let typeHtml = '';
        config.types.forEach(type => {
            typeHtml += `<option value="${type}">${type}</option>`;
        });
        typeHtml += `<option value="Other">Other...</option>`;
        drinkTypeSelect.innerHTML = typeHtml;
    }

    // Clear and populate Quantities
    if (config.quantities && config.quantities.length > 0) {
        let qtyHtml = '';
        config.quantities.forEach(qty => {
            qtyHtml += `<option value="${qty.value}">${qty.label}</option>`;
        });
        qtyHtml += `<option value="custom">Custom...</option>`;
        quantitySelect.innerHTML = qtyHtml;
    }
}

export function updateFormToggles() {

    const drinkTypeSelect = document.getElementById('drink_type_select');
    const customDrinkType = document.getElementById('custom_drink_type');
    const quantitySelect = document.getElementById('quantity_select');
    const customQuantity = document.getElementById('custom_quantity');

    customDrinkType.style.display = drinkTypeSelect.value === 'Other' ? 'block' : 'none';
    if (drinkTypeSelect.value === 'Other') customDrinkType.focus();

    customQuantity.style.display = quantitySelect.value === 'custom' ? 'block' : 'none';
    if (quantitySelect.value === 'custom') customQuantity.focus();
}

export function requestLocation(latInput, lngInput, locationStatus) {
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

// --- Leaderboard Render ---
export function renderLeaderboard(data, leaderboardContainer) {
    if (data.length === 0) {
        leaderboardContainer.innerHTML = "<div class='card'><p style='color: var(--text-secondary); text-align: center; margin: 0;'>No entries found.</p></div>";
        return;
    }

    let html = `<div class="leaderboard-list">`;

    data.forEach((user, index) => {
        const rank = index + 1;
        let rankClass = '';
        let rankLabel = rank;

        if (rank === 1) { rankClass = 'rank-1'; rankLabel = '👑 1st'; }
        else if (rank === 2) { rankClass = 'rank-2'; rankLabel = '🥈 2nd'; }
        else if (rank === 3) { rankClass = 'rank-3'; rankLabel = '🥉 3rd'; }

        html += `
            <div class="card rank-card ${rankClass}" data-username="${user.username}" style="cursor: pointer;">
                <div class="rank-user-info">
                    <span class="rank-number">${rankLabel}</span>
                    <span class="rank-name">${user.username}</span>
                </div>
                <div class="rank-stats">
                    <div class="stat-item tooltip-trigger" data-tooltip="Total volume (Liters)">
                        <span class="stat-value">${user.total_liters.toFixed(2)}</span>
                        <span class="stat-label">Liters</span>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-item tooltip-trigger" data-tooltip="Pure alcohol (Volume × ABV)">
                        <span class="stat-value highlight">${user.total_alcohol.toFixed(3)}</span>
                        <span class="stat-label">Alc L</span>
                    </div>
                </div>
            </div>
        `;
    });

    html += `</div>`;
    leaderboardContainer.innerHTML = html;
}

// --- User Profile Modal ---
export function showUserModal(username, leaderboard, entries) {
    const modal = document.getElementById('user-modal');
    const content = document.getElementById('user-modal-content');

    const userStats = leaderboard.find(u => u.username === username);
    const userEntries = entries.filter(e => e.username === username)
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    if (!userStats) return;

    let recentDrinksHtml = '';
    if (userEntries.length > 0) {
        recentDrinksHtml = '<h4 style="margin-top: 20px; margin-bottom: 10px; color: var(--accent-primary);">Recent Drinks</h4><div class="recent-drinks-list" style="max-height: 250px; overflow-y: auto; text-align: left; padding-right: 5px;">';
        userEntries.slice(0, 15).forEach(entry => {
            const date = new Date(entry.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            recentDrinksHtml += `
                <div style="padding: 12px; margin-bottom: 8px; background: rgba(255, 255, 255, 0.03); border-radius: 8px; border: 1px solid var(--glass-border);">
                    <div style="font-weight: bold; color: white; display: flex; justify-content: space-between;">
                        <span>${entry.drink_type} ${entry.brand ? `<span style="color: var(--text-secondary); font-weight: normal;">(${entry.brand})</span>` : ''}</span>
                        <span style="color: var(--success-color);">${entry.quantity}L</span>
                    </div>
                    <div style="font-size: 11px; color: var(--text-secondary); display: flex; justify-content: space-between; margin-top: 5px;">
                        <span>ABV: ${entry.abv}%</span>
                        <span>${date}</span>
                    </div>
                </div>
            `;
        });
        recentDrinksHtml += '</div>';
    } else {
        recentDrinksHtml = '<p style="color: var(--text-secondary); margin-top: 20px;">No drinks logged yet.</p>';
    }

    content.innerHTML = `
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="width: 64px; height: 64px; background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)); border-radius: 50%; padding: 2px; display: inline-block; margin-bottom: 15px; box-shadow: 0 0 15px rgba(0, 242, 255, 0.4);">
                <div style="width: 100%; height: 100%; background: var(--bg-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 800; color: white;">
                    ${username.charAt(0).toUpperCase()}
                </div>
            </div>
            <h2 style="margin: 0; justify-content: center;">${username}</h2>
        </div>
        
        <div style="display: flex; justify-content: space-around; background: rgba(0, 0, 0, 0.3); padding: 15px; border-radius: 12px; border: 1px solid var(--glass-border);">
            <div style="text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: var(--text-primary);">${userStats.total_liters.toFixed(2)}</div>
                <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-top: 4px;">Vol (L)</div>
            </div>
            <div style="width: 1px; background: var(--glass-border);"></div>
            <div style="text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: var(--accent-primary);">${userStats.total_alcohol.toFixed(3)}</div>
                <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-top: 4px;">Alc (L)</div>
            </div>
            <div style="width: 1px; background: var(--glass-border);"></div>
            <div style="text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: var(--success-color);">${userEntries.length}</div>
                <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-top: 4px;">Drinks</div>
            </div>
        </div>
        
        ${recentDrinksHtml}
    `;

    modal.style.display = 'block';
}

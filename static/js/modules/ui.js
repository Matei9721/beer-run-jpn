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
        setTimeout(() => { if(el && !el.classList.contains('visible')) el.remove(); }, 200);
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
        leaderboardContainer.innerHTML = "<p style='color: #888; text-align: center; padding: 20px;'>No entries found.</p>";
        return;
    }

    let html = `
        <table class="leaderboard-table">
            <thead>
                <tr>
                    <th>User</th>
                    <th class="tooltip-trigger" data-tooltip="Total volume of drinks (Liters)">Total (L) <span class="info-icon">ⓘ</span></th>
                    <th class="tooltip-trigger" data-tooltip="Pure alcohol consumed (Volume × ABV)">Alc (L) <span class="info-icon">ⓘ</span></th>
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
    leaderboardContainer.innerHTML = html;
}

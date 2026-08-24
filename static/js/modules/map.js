// Initialize Leaflet Map
export const map = L.map('map').setView([35.6895, 139.6917], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OSM'
}).addTo(map);

export const markerGroup = L.markerClusterGroup({
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true
}).addTo(map);

const markersByEntryId = new Map();
let highlightLayer = null;
let highlightTimeout = null;
let visualGeneration = 0;

// Leaflet icon setup
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const detailSheet = document.getElementById('detail-sheet');
const detailTitle = document.getElementById('detail-title');
const detailMeta = document.getElementById('detail-meta');
const detailImg = document.getElementById('detail-img');
const detailCloseButton = document.getElementById('close-sheet');
const detailActionsElement = document.getElementById('detail-actions');
const detailEditButton = document.getElementById('detail-edit-entry');
const detailDeleteButton = document.getElementById('detail-delete-entry');

let activeDetailEntry = null;
let detailActions = {
    canManageEntry: () => false,
    onEntrySelected: null,
    onDetailClosed: null,
    onEdit: null,
    onDelete: null,
};

function formatEntryTime(entry) {
    const timeCode = entry.timezone_code ? ` (${entry.timezone_code})` : '';
    return `${new Date(entry.timestamp).toLocaleTimeString()}${timeCode}`;
}

export function openDetail(entry) {
    activeDetailEntry = entry;
    detailSheet.removeAttribute('inert');
    detailSheet.setAttribute('aria-hidden', 'false');
    detailCloseButton.disabled = false;
    detailTitle.innerText = `${entry.username}`;
    detailMeta.replaceChildren();
    const drinkType = document.createElement('strong');
    drinkType.textContent = entry.drink_type;
    detailMeta.append(drinkType);
    if (entry.brand) detailMeta.append(` (${entry.brand})`);
    detailMeta.append(document.createElement('br'));
    detailMeta.append(`${entry.abv}% ABV | ${entry.quantity}L`);
    detailMeta.append(document.createElement('br'));
    const timestamp = document.createElement('span');
    timestamp.className = 'detail-time';
    timestamp.textContent = `Logged at ${formatEntryTime(entry)}`;
    detailMeta.append(timestamp);
    
    if (entry.image_path) {
        detailImg.src = `/${entry.image_path.replace(/\\/g, '/')}`;
        detailImg.style.display = 'block';
    } else {
        detailImg.removeAttribute('src');
        detailImg.style.display = 'none';
    }

    const canManage = Boolean(detailActions.canManageEntry?.(entry));
    detailActionsElement.hidden = !canManage;
    detailEditButton.disabled = false;
    detailDeleteButton.disabled = false;
    detailActions.onEntrySelected?.(entry, canManage);
    detailSheet.classList.add('active');
}

export function closeDetail({ notify = true } = {}) {
    detailSheet.classList.remove('active');
    detailSheet.setAttribute('inert', '');
    detailSheet.setAttribute('aria-hidden', 'true');
    detailCloseButton.disabled = true;
    detailActionsElement.hidden = true;
    if (!notify) return;
    const closedEntry = activeDetailEntry;
    activeDetailEntry = null;
    detailActions.onDetailClosed?.(closedEntry);
}

export function isDetailOpen() {
    return detailSheet.classList.contains('active');
}

export function configureEntryActions(actions = {}) {
    detailActions = { ...detailActions, ...actions };
}

export function focusDetailAction(action = 'edit') {
    const button = action === 'delete' ? detailDeleteButton : detailEditButton;
    if (!detailSheet.classList.contains('active') || button.hidden || button.disabled) return false;
    button.focus();
    return true;
}

export function clearRunState() {
    visualGeneration += 1;
    markerGroup.clearLayers();
    markersByEntryId.clear();
    map.closePopup();
    closeDetail();
    detailTitle.innerText = 'Drink Detail';
    detailMeta.replaceChildren();
    detailImg.removeAttribute('src');
    detailImg.style.display = 'none';
    if (highlightTimeout) {
        clearTimeout(highlightTimeout);
        highlightTimeout = null;
    }
    if (highlightLayer) {
        map.removeLayer(highlightLayer);
        highlightLayer = null;
    }
}

export function focusEntry(entry, onShown = null) {
    const marker = markersByEntryId.get(Number(entry.id));
    if (!marker) return false;
    const requestGeneration = visualGeneration;

    markerGroup.zoomToShowLayer(marker, () => {
        if (requestGeneration !== visualGeneration) return;
        const latLng = marker.getLatLng();
        const targetZoom = Math.max(map.getZoom(), 16);

        map.setView(latLng, targetZoom, { animate: true });
        marker.openPopup();
        openDetail(entry);

        if (highlightLayer) {
            map.removeLayer(highlightLayer);
        }

        highlightLayer = L.circleMarker(latLng, {
            radius: 22,
            color: '#00f2ff',
            weight: 3,
            opacity: 0.95,
            fillColor: '#ff2a6d',
            fillOpacity: 0.18,
            interactive: false
        }).addTo(map);

        if (highlightTimeout) clearTimeout(highlightTimeout);
        highlightTimeout = setTimeout(() => {
            if (highlightLayer) {
                map.removeLayer(highlightLayer);
                highlightLayer = null;
            }
            highlightTimeout = null;
        }, 3500);
        onShown?.();
    });

    return true;
}

export function updateMarkers(entries, shouldZoom = true) {
    visualGeneration += 1;
    if (highlightTimeout) {
        clearTimeout(highlightTimeout);
        highlightTimeout = null;
    }
    if (highlightLayer) {
        map.removeLayer(highlightLayer);
        highlightLayer = null;
    }
    markerGroup.clearLayers();
    markersByEntryId.clear();
    entries.forEach(entry => {
        const popupContent = document.createElement('div');
        popupContent.className = 'mini-popup';
        if (entry.image_path) {
            const thumbnail = document.createElement('img');
            thumbnail.src = `/${entry.image_path.replace(/\\/g, '/')}`;
            thumbnail.className = 'popup-thumb';
            thumbnail.alt = '';
            popupContent.append(thumbnail);
        }
        const popupInfo = document.createElement('div');
        popupInfo.className = 'popup-info';
        const popupUser = document.createElement('span');
        popupUser.className = 'popup-user';
        popupUser.textContent = entry.username;
        const popupDrink = document.createElement('span');
        popupDrink.className = 'popup-drink';
        popupDrink.textContent = entry.drink_type;
        const popupLink = document.createElement('button');
        popupLink.type = 'button';
        popupLink.className = 'popup-link';
        popupLink.textContent = 'View Details';
        popupLink.addEventListener('click', () => openDetail(entry));
        popupInfo.append(popupUser, popupDrink, popupLink);
        popupContent.append(popupInfo);

        const marker = L.marker([entry.latitude, entry.longitude])
            .bindPopup(popupContent);

        markersByEntryId.set(Number(entry.id), marker);
        marker.addTo(markerGroup);
    });

    if (shouldZoom && entries.length > 0) {
        const group = new L.featureGroup(markerGroup.getLayers());
        const bounds = group.getBounds();
        if (bounds.isValid()) map.fitBounds(bounds.pad(0.2));
    }
}

detailEditButton.addEventListener('click', () => {
    if (!activeDetailEntry || detailEditButton.disabled || !detailActions.canManageEntry?.(activeDetailEntry)) return;
    const entry = activeDetailEntry;
    const started = detailActions.onEdit?.(entry);
    if (started !== false) closeDetail({ notify: false });
});

detailDeleteButton.addEventListener('click', () => {
    if (!activeDetailEntry || detailDeleteButton.disabled || !detailActions.canManageEntry?.(activeDetailEntry)) return;
    detailActions.onDelete?.(activeDetailEntry);
});

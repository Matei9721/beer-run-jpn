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

function formatEntryTime(entry) {
    const timeCode = entry.timezone_code ? ` (${entry.timezone_code})` : '';
    return `${new Date(entry.timestamp).toLocaleTimeString()}${timeCode}`;
}

export function openDetail(entry) {
    detailTitle.innerText = `${entry.username}`;
    detailMeta.innerHTML = `
        <strong>${entry.drink_type}</strong> ${entry.brand ? `(${entry.brand})` : ''}<br>
        ${entry.abv}% ABV | ${entry.quantity}L<br>
        <span style="font-size: 12px; opacity: 0.7;">Logged at ${formatEntryTime(entry)}</span>
    `;
    
    if (entry.image_path) {
        detailImg.src = `/${entry.image_path.replace(/\\/g, '/')}`;
        detailImg.style.display = 'block';
    } else {
        detailImg.style.display = 'none';
    }
    
    detailSheet.classList.add('active');
}

export function closeDetail() {
    detailSheet.classList.remove('active');
}

export function focusEntry(entry) {
    const marker = markersByEntryId.get(Number(entry.id));
    if (!marker) return false;

    markerGroup.zoomToShowLayer(marker, () => {
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

        setTimeout(() => {
            if (highlightLayer) {
                map.removeLayer(highlightLayer);
                highlightLayer = null;
            }
        }, 3500);
    });

    return true;
}

// Global exposure for onclick handlers in Leaflet popups
window.openDetail = function(entryJson) {
    const entry = JSON.parse(decodeURIComponent(entryJson));
    openDetail(entry);
};

export function updateMarkers(entries, shouldZoom = true) {
    markerGroup.clearLayers();
    markersByEntryId.clear();
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

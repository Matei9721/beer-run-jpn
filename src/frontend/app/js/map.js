import { showConfirmation } from "./confirmation.js?v=beerrun-105-tour-end";

const SELECTED_ENTRY_KEY = "beerRun.revamp.selectedEntry";
const SELECTED_ENTRY_ZOOM = 16;
const el = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const valid = (value, min, max) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) && Number(value) >= min && Number(value) <= max;
const isMapped = (entry) => valid(entry.latitude, -90, 90) && valid(entry.longitude, -180, 180);
const titleFor = (entry) => [entry.drink_type || "Drink", entry.brand].filter(Boolean).join(" · ");
const quantityFor = (value) => Number.isFinite(Number(value))
  ? (Number(value) < 1 ? `${Math.round(Number(value) * 1000)} ml` : `${Number(value).toFixed(2)} L`)
  : "Quantity unavailable";
const abvFor = (value) => Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}% ABV` : "ABV unavailable";

// Entries carry the calendar date at the place they were logged. Keep that date
// when someone browses the trip from a different time zone.
export function mapDayKey(entry) {
  const value = typeof entry.timestamp === "string" ? entry.timestamp : "";
  const key = value.match(/^(\d{4}-\d{2}-\d{2})T/)?.[1];
  if (!key) return "";
  const date = new Date(`${key}T12:00:00Z`);
  return Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== key ? "" : key;
}

export function mapVisibleEntries(entries, { username = "", day = "" } = {}) {
  return entries.filter((entry) => (!username || entry.username === username) && (!day || mapDayKey(entry) === day))
    .sort((a, b) => {
      const left = Date.parse(a.timestamp);
      const right = Date.parse(b.timestamp);
      return (Number.isFinite(left) ? left : Infinity) - (Number.isFinite(right) ? right : Infinity)
        || Number(a.id) - Number(b.id);
    });
}

const dayLabel = (key, long = false) => key
  ? new Date(`${key}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", ...(long ? { weekday: "short" } : {}) })
  : "All days";
const runnerColour = (name = "") => [...name].reduce((hash, char) => (hash * 31 + char.codePointAt(0)) >>> 0, 0) % 5;
const timeFor = (entry) => {
  const match = typeof entry.timestamp === "string" && entry.timestamp.match(/T(\d{2}:\d{2})/);
  return match ? `${dayLabel(mapDayKey(entry))} · ${match[1]}` : "Time unavailable";
};

export function buildMapStops(entries) {
  const stops = [];
  const radians = (value) => Number(value) * Math.PI / 180;
  const distance = (a, b) => {
    const dLat = radians(b.latitude) - radians(a.latitude);
    const dLng = radians(b.longitude) - radians(a.longitude);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(radians(a.latitude)) * Math.cos(radians(b.latitude)) * Math.sin(dLng / 2) ** 2;
    return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
  };
  for (const entry of mapVisibleEntries(entries).filter(isMapped)) {
    const previous = stops.at(-1);
    const first = previous?.entries[0];
    const elapsed = first ? Date.parse(entry.timestamp) - Date.parse(first.timestamp) : Infinity;
    if (first && mapDayKey(entry) && mapDayKey(entry) === mapDayKey(first)
      && elapsed >= 0 && elapsed <= 90 * 60_000 && distance(first, entry) <= 60) {
      previous.entries.push(entry);
    } else stops.push({ id: entry.id, entries: [entry] });
  }
  return stops;
}

// A drink is represented by its pin or its visible cluster, never both.
// Re-resolve the parent after zooming because Leaflet replaces cluster icons.
export function updateMapSelection(markerGroup, markers, selectedEntryId, previousLayer = null) {
  const visibleParent = (marker) => markerGroup?.getVisibleParent ? markerGroup.getVisibleParent(marker) : marker;
  const marker = markers.get(selectedEntryId);
  const selectedLayer = marker ? visibleParent(marker) : null;
  const layers = new Set([previousLayer, ...markers.values()]);
  markers.forEach((item) => layers.add(visibleParent(item)));
  layers.forEach((layer) => {
    const icon = layer?.getElement();
    if (!icon) return;
    const selected = layer === selectedLayer;
    if (icon.classList.contains("is-selected") !== selected) icon.classList.toggle("is-selected", selected);
    if (icon.getAttribute("aria-pressed") !== String(selected)) icon.setAttribute("aria-pressed", String(selected));
    if (layer.getChildCount) {
      const label = `${layer.getChildCount()} drinks`;
      if (icon.getAttribute("aria-label") !== label) icon.setAttribute("aria-label", label);
    }
  });
  return selectedLayer;
}

export function expandMapCluster(map, cluster, getPadding, beforeExpand = () => {}) {
  const bounds = cluster.getBounds();
  const local = map.distance(bounds.getNorthWest(), bounds.getSouthEast()) <= 120;
  if (!local && map.getZoom() < map.getMaxZoom()) {
    cluster.zoomToBounds(getPadding());
    return false;
  }
  // Finish the photo sheet's DOM and layout work before Leaflet starts moving pins.
  beforeExpand();
  const { paddingTopLeft: left, paddingBottomRight: right } = getPadding();
  const point = map.project(cluster.getLatLng()).add([(right[0] - left[0]) / 2, (right[1] - left[1]) / 2]);
  map.panTo(map.unproject(point), { animate: false });
  cluster.spiderfy();
  return true;
}
const fullscreenIcon = (className, pathData) => {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.classList.add("map-fullscreen-control__icon", className);
  icon.setAttribute("viewBox", "0 0 256 256");
  icon.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathData);
  icon.append(path);
  return icon;
};

function photoFor(entry) {
  const media = el("div", "map-detail__photo");
  const path = typeof entry.image_path === "string" ? entry.image_path.replaceAll("\\", "/") : "";
  if (!path) {
    media.classList.add("is-fallback");
    media.append(el("span", "", "No photo"));
    return media;
  }
  const image = el("img");
  image.src = path.startsWith("/") ? path : `/${path}`;
  image.alt = `${titleFor(entry)} logged by ${entry.username || "a runner"}`;
  image.addEventListener("error", () => {
    media.classList.add("is-fallback");
    media.replaceChildren(el("span", "", "Photo unavailable"));
  }, { once: true });
  media.append(image);
  return media;
}

function detailFor(entry, { canManage, onClose, onEdit, onDelete, expanded, onExpand, onPrevious, onNext, position, total, stop, onSelect }) {
  const detail = el("article", "map-detail");
  detail.dataset.mapDetail = "";
  detail.setAttribute("aria-labelledby", "map-detail-title");
  const handle = el("button", "map-detail__handle");
  handle.type = "button";
  handle.dataset.focusKey = "expand";
  handle.setAttribute("aria-label", expanded ? "Collapse drink details" : "Expand drink details");
  handle.setAttribute("aria-expanded", String(expanded));
  handle.setAttribute("aria-controls", "map-detail-body");
  handle.append(el("span"));
  handle.addEventListener("click", onExpand);
  let startY = null;
  let dragged = false;
  handle.addEventListener("pointerdown", (event) => { startY = event.clientY; dragged = false; handle.setPointerCapture?.(event.pointerId); });
  handle.addEventListener("pointerup", (event) => {
    if (startY !== null && Math.abs(event.clientY - startY) > 24) {
      dragged = true;
      onExpand(event.clientY < startY);
    }
    startY = null;
  });
  handle.addEventListener("pointercancel", () => { startY = null; });
  handle.addEventListener("click", (event) => { if (dragged) { event.stopImmediatePropagation(); dragged = false; } }, { capture: true });
  const header = el("div", "map-detail__header");
  const identity = el("div", "map-detail__identity");
  const title = el("h2", "", titleFor(entry));
  title.id = "map-detail-title";
  identity.append(el("p", "map-detail__runner", `${entry.username || "Unknown runner"} · ${timeFor(entry)}`), title);
  const close = el("button", "map-detail__close", "×");
  close.type = "button";
  close.dataset.focusKey = "close";
  close.setAttribute("aria-label", "Close drink details and return to the map");
  close.addEventListener("click", onClose);
  const thumbnail = photoFor(entry);
  thumbnail.className = "map-detail__thumbnail";
  header.append(thumbnail, identity, close);
  const navigation = el("div", "map-detail__navigation");
  const previous = el("button", "map-journal-button", "←");
  previous.type = "button";
  previous.dataset.focusKey = "previous";
  previous.setAttribute("aria-label", "Previous drink");
  previous.disabled = position === 0;
  previous.addEventListener("click", onPrevious);
  const next = el("button", "map-journal-button", "→");
  next.type = "button";
  next.dataset.focusKey = "next";
  next.setAttribute("aria-label", "Next drink");
  next.disabled = position >= total - 1;
  next.addEventListener("click", onNext);
  const expand = el("button", "map-detail__expand", expanded ? "Less detail" : "Photo & details");
  expand.type = "button";
  expand.dataset.focusKey = "expand-link";
  expand.setAttribute("aria-expanded", String(expanded));
  expand.setAttribute("aria-controls", "map-detail-body");
  expand.addEventListener("click", onExpand);
  navigation.append(previous, el("span", "map-detail__position", `${position + 1} / ${total}`), next, expand);
  const body = el("div", "map-detail__body");
  body.id = "map-detail-body";
  body.hidden = !expanded;
  const facts = el("dl", "map-detail__facts");
  [["Amount", quantityFor(entry.quantity)], ["Strength", abvFor(entry.abv)], ["Logged", timeFor(entry)]].forEach(([label, value]) => {
    const fact = el("div");
    fact.append(el("dt", "", label), el("dd", "", value));
    facts.append(fact);
  });
  const location = el("details", "map-detail__location");
  location.append(el("summary", "", isMapped(entry) ? "Saved location" : "Location unavailable"));
  if (isMapped(entry)) location.append(el("p", "", `${Number(entry.latitude).toFixed(4)}, ${Number(entry.longitude).toFixed(4)}`));
  body.append(photoFor(entry), facts, location);
  if (stop?.entries.length > 1) {
    const nearby = el("section", "map-detail__stop");
    nearby.append(el("h3", "", "Around the same stop"), el("p", "", "Logged within 60 m and 90 minutes. Places may differ."));
    stop.entries.filter((other) => other.id !== entry.id).forEach((other) => {
      const button = el("button", "button button--quiet", `${other.username} · ${titleFor(other)}`);
      button.type = "button";
      button.addEventListener("click", () => onSelect(other));
      nearby.append(button);
    });
    body.append(nearby);
  }
  detail.append(handle, header, navigation, body);
  let touchStart = null;
  header.addEventListener("touchstart", (event) => { touchStart = event.touches.length === 1 ? [event.touches[0].clientX, event.touches[0].clientY] : null; }, { passive: true });
  header.addEventListener("touchend", (event) => {
    if (!touchStart || !event.changedTouches.length) return;
    const dx = event.changedTouches[0].clientX - touchStart[0];
    const dy = event.changedTouches[0].clientY - touchStart[1];
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0 && position < total - 1) onNext();
      if (dx > 0 && position > 0) onPrevious();
    }
    touchStart = null;
  }, { passive: true });
  if (canManage(entry)) {
    const actions = el("div", "map-detail__actions");
    const edit = el("button", "button button--secondary", "Edit drink");
    edit.type = "button";
    edit.addEventListener("click", () => onEdit(entry));
    const remove = el("button", "button button--danger", "Delete drink");
    remove.type = "button";
    remove.addEventListener("click", (event) => onDelete(entry, event.currentTarget));
    actions.append(edit, remove);
    body.append(actions);
  }
  return detail;
}

export function createMapController({ root = document, api, auth, getSnapshot, refresh, navigate }) {
  let active = false;
  let renderedRunId = null;
  let selectedUsername = "";
  let selectedEntryId = null;
  let map = null;
  let markerGroup = null;
  let markers = new Map();
  let tileWarning = false;
  let fullscreenButton = null;
  let selectedDay = "";
  let sheetExpanded = false;
  let visibleEntries = [];
  let stops = [];
  let selectedLayer = null;
  let selectionFrame = null;
  let expandedCluster = null;
  let expandedEntryIds = new Set();
  let clusterEntryIds = null;
  let savedView = null;
  let lastSignature = "";
  let replayTimer = null;
  let replaying = false;
  const data = () => getSnapshot().data || { run: null, identity: null, entries: [] };
  const journalEntries = () => clusterEntryIds ? visibleEntries.filter((entry) => clusterEntryIds.has(Number(entry.id))) : visibleEntries;

  function resizeMap(reposition = false) {
    if (!map) return;
    const requestedMap = map;
    const applySize = () => {
      if (map !== requestedMap) return;
      map.invalidateSize({ animate: false, pan: false });
      syncSelection();
      if (reposition) {
        const entry = visibleEntries.find((item) => Number(item.id) === selectedEntryId);
        if (entry) positionEntry(entry);
      }
    };
    window.requestAnimationFrame(() => window.requestAnimationFrame(applySize));
    window.setTimeout(applySize, 250);
  }
  function isFallbackFullscreen() {
    return root.querySelector("[data-map-workspace]")?.classList.contains("is-fullscreen-fallback");
  }
  function nativeFullscreenElement() {
    return document.fullscreenElement || null;
  }
  async function exitNativeFullscreen() {
    if (typeof document.exitFullscreen !== "function") return false;
    await document.exitFullscreen();
    return true;
  }
  async function requestNativeFullscreen(workspace) {
    if (typeof workspace.requestFullscreen !== "function" || typeof document.exitFullscreen !== "function") return false;
    await workspace.requestFullscreen();
    return true;
  }
  function syncFullscreenControl() {
    const workspace = root.querySelector("[data-map-workspace]");
    const expanded = nativeFullscreenElement() === workspace || workspace?.classList.contains("is-fullscreen-fallback");
    if (fullscreenButton) {
      const label = expanded ? "Exit full screen map" : "Enter full screen map";
      fullscreenButton.setAttribute("aria-label", label);
      fullscreenButton.setAttribute("aria-pressed", String(Boolean(expanded)));
      fullscreenButton.title = label;
    }
    document.body.classList.toggle("map-fallback-fullscreen", Boolean(workspace?.classList.contains("is-fullscreen-fallback")));
    resizeMap(true);
  }
  function enterFallbackFullscreen(workspace) {
    workspace.classList.add("is-fullscreen-fallback");
    syncFullscreenControl();
  }
  async function toggleFullscreen() {
    const workspace = root.querySelector("[data-map-workspace]");
    if (!workspace) return;
    if (nativeFullscreenElement() === workspace) {
      try {
        await exitNativeFullscreen();
      } catch {
        syncFullscreenControl();
      }
    } else if (workspace.classList.contains("is-fullscreen-fallback")) {
      workspace.classList.remove("is-fullscreen-fallback");
      syncFullscreenControl();
    } else {
      try {
        if (!await requestNativeFullscreen(workspace)) enterFallbackFullscreen(workspace);
      } catch {
        enterFallbackFullscreen(workspace);
      }
    }
  }
  function addFullscreenControl() {
    const control = window.L.control({ position: "topright" });
    control.onAdd = () => {
      const wrap = window.L.DomUtil.create("div", "leaflet-bar map-fullscreen-control");
      fullscreenButton = el("button", "map-fullscreen-control__button");
      fullscreenButton.type = "button";
      fullscreenButton.setAttribute("aria-label", "Enter full screen map");
      fullscreenButton.setAttribute("aria-pressed", "false");
      fullscreenButton.title = "Enter full screen map";
      fullscreenButton.append(
        fullscreenIcon("map-fullscreen-control__icon--expand", "M88 48H48v40M168 48h40v40M208 168v40h-40M88 208H48v-40"),
        fullscreenIcon("map-fullscreen-control__icon--collapse", "M88 48v40H48M168 48v40h40M208 168h-40v40M48 168h40v40"),
      );
      window.L.DomEvent.disableClickPropagation(wrap);
      fullscreenButton.addEventListener("click", () => { void toggleFullscreen(); });
      wrap.append(fullscreenButton);
      return wrap;
    };
    control.addTo(map);
  }

  function memoryIcon() {
    const pin = el("span", "map-pin");
    pin.setAttribute("aria-hidden", "true");
    const shape = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    shape.setAttribute("viewBox", "0 0 32 40");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M16 38S2 24 2 16a14 14 0 0 1 28 0c0 8-14 22-14 22Z");
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", "16");
    dot.setAttribute("cy", "16");
    dot.setAttribute("r", "4");
    shape.append(path, dot);
    pin.append(shape);
    return window.L.divIcon({ html: pin, className: "map-memory-marker", iconSize: [44, 44], iconAnchor: [22, 40] });
  }

  function syncSelection() {
    selectedLayer = updateMapSelection(markerGroup, markers, selectedEntryId, selectedLayer);
  }

  function queueSelection() {
    if (selectionFrame !== null) return;
    selectionFrame = window.requestAnimationFrame(() => {
      selectionFrame = null;
      if (map) syncSelection();
    });
  }

  function stopReplay() {
    if (replaying) map?.stop?.();
    window.clearTimeout(replayTimer);
    replayTimer = null;
    replaying = false;
    const button = root.querySelector("[data-map-replay]");
    if (button) {
      button.textContent = "▶ Replay";
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", clusterEntryIds ? "Replay these drinks" : selectedDay ? "Replay this day" : "Replay the trip");
    }
  }

  function replayStep() {
    if (!active || !replaying || root.querySelector("dialog[open]")) { stopReplay(); return; }
    const sequence = journalEntries().filter(isMapped);
    const index = sequence.findIndex((entry) => Number(entry.id) === selectedEntryId);
    const entry = sequence[index + 1];
    if (!entry) { stopReplay(); return; }
    focusEntry(entry, { focus: false, animate: true });
    replayTimer = window.setTimeout(replayStep, 2800);
  }

  function toggleReplay() {
    if (replaying) { stopReplay(); return; }
    const sequence = journalEntries().filter(isMapped);
    if (sequence.length < 2) return;
    sheetExpanded = false;
    replaying = true;
    const index = sequence.findIndex((entry) => Number(entry.id) === selectedEntryId);
    if (index < 0 || index === sequence.length - 1) focusEntry(sequence[0], { focus: false, animate: true });
    else renderJournal();
    replayTimer = window.setTimeout(replayStep, 2800);
  }

  function selectAdjacent(delta) {
    stopReplay();
    const entries = journalEntries();
    const index = entries.findIndex((entry) => Number(entry.id) === selectedEntryId);
    const entry = entries[index + delta];
    if (entry) focusEntry(entry, { focus: false });
  }

  function renderJournal(detail = null) {
    const journal = root.querySelector("[data-map-journal]");
    if (!journal) return;
    const entries = journalEntries();
    const entry = entries.find((candidate) => Number(candidate.id) === selectedEntryId);
    if (entry && !detail) { showDetail(entry, { focus: false }); return; }
    const focusKey = root.activeElement?.dataset?.focusKey;
    const oldRail = journal.querySelector(".map-photo-rail");
    const scrollLeft = oldRail?.scrollLeft || 0;
    journal.replaceChildren();
    journal.hidden = entries.length === 0;
    journal.classList.toggle("is-expanded", sheetExpanded && Boolean(entry));
    journal.classList.toggle("has-selection", Boolean(entry));
    root.querySelector("[data-map-workspace]")?.classList.toggle("has-expanded-detail", sheetExpanded && Boolean(entry));
    if (detail) journal.append(detail);
    const heading = el("div", "map-journal__heading");
    const copy = el("div");
    copy.append(el("strong", "", clusterEntryIds ? `${entries.length} nearby drinks` : selectedDay ? dayLabel(selectedDay, true) : "The trip, in moments"));
    if (!entry) copy.append(el("span", "map-journal__meta", `${entries.length} drinks · ${new Set(entries.map((item) => item.username)).size} friends`));
    if (clusterEntryIds) {
      const all = el("button", "map-journal-button map-journal__back", "All drinks");
      all.type = "button";
      all.dataset.focusKey = "all-drinks";
      all.setAttribute("aria-label", "Browse all drinks in the current filters");
      all.addEventListener("click", () => { clusterEntryIds = null; closeDetail(); });
      heading.append(all);
    }
    const replay = el("button", "map-journal-button map-journal__replay", replaying ? "Ⅱ Pause" : "▶ Replay");
    replay.type = "button";
    replay.dataset.mapReplay = "";
    replay.dataset.focusKey = "replay";
    replay.setAttribute("aria-label", replaying ? "Pause replay" : clusterEntryIds ? "Replay these drinks" : selectedDay ? "Replay this day" : "Replay the trip");
    replay.setAttribute("aria-pressed", String(replaying));
    replay.disabled = entries.filter(isMapped).length < 2;
    replay.addEventListener("click", toggleReplay);
    heading.prepend(copy);
    heading.append(replay);
    const rail = el("div", "map-photo-rail");
    rail.setAttribute("role", "group");
    rail.setAttribute("aria-label", "Browse trip photos and drinks");
    entries.forEach((item) => {
      const button = el("button", "map-photo");
      button.type = "button";
      button.dataset.focusKey = `entry-${item.id}`;
      button.setAttribute("aria-label", `${titleFor(item)}, ${item.username || "Unknown runner"}, ${timeFor(item)}${isMapped(item) ? "" : ", no saved location"}`);
      button.setAttribute("aria-pressed", String(Number(item.id) === selectedEntryId));
      const photo = photoFor(item);
      photo.className = "map-photo__image";
      const image = photo.querySelector("img");
      if (image) { image.loading = "lazy"; image.alt = ""; }
      else photo.replaceChildren(el("span", "map-photo__placeholder", "No photo"));
      const label = el("span", "map-photo__person", item.username || "Unknown");
      label.dataset.runnerColour = String(runnerColour(item.username));
      button.append(photo, label);
      button.addEventListener("click", () => { stopReplay(); focusEntry(item, { focus: false }); });
      rail.append(button);
    });
    journal.append(heading, rail);
    rail.scrollLeft = scrollLeft;
    const selected = [...rail.children].find((button) => button.getAttribute("aria-pressed") === "true");
    if (selected) rail.scrollLeft = selected.offsetLeft - rail.offsetLeft - (rail.clientWidth - selected.offsetWidth) / 2;
    if (focusKey) {
      const target = [...journal.querySelectorAll("[data-focus-key]")].find((node) => node.dataset.focusKey === focusKey);
      (target && !target.disabled ? target : selected)?.focus({ preventScroll: true });
    }
    updateDockSpace();
  }

  function updateDockSpace() {
    const journal = root.querySelector("[data-map-journal]");
    root.querySelector("[data-map-workspace]")?.style.setProperty("--map-journal-height", `${journal && !journal.hidden ? journal.offsetHeight + 34 : 34}px`);
  }

  function mapPadding() {
    const panel = root.querySelector(".map-explorer-controls");
    const journal = root.querySelector("[data-map-journal]");
    const phone = window.matchMedia("(max-width: 767px)").matches;
    const dockHeight = journal && !journal.hidden ? journal.getBoundingClientRect().height : 0;
    const dockWidth = journal && !journal.hidden ? journal.getBoundingClientRect().width : 0;
    return {
      paddingTopLeft: [20, (panel?.offsetHeight || 0) + 58],
      paddingBottomRight: [phone ? 20 : dockWidth + 32, phone ? dockHeight + 28 : 40],
    };
  }

  function positionEntry(entry, animate = false, minimumZoom = SELECTED_ENTRY_ZOOM) {
    if (!map || !isMapped(entry)) return;
    // Keep the spiral open and use the displayed pin's position. Its original
    // coordinates point to the centre of the cluster, not the expanded pin.
    if (expandedEntryIds.has(Number(entry.id))) {
      const marker = markers.get(Number(entry.id));
      if (marker) map.panInside(marker.getLatLng(), {
        ...mapPadding(), animate: animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches, duration: 0.2,
      });
      return;
    }
    const zoom = Math.max(map.getZoom(), minimumZoom);
    const { paddingTopLeft: left, paddingBottomRight: right } = mapPadding();
    const point = map.project([Number(entry.latitude), Number(entry.longitude)], zoom).add([(right[0] - left[0]) / 2, (right[1] - left[1]) / 2]);
    const center = map.unproject(point, zoom);
    if (animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) map.flyTo(center, zoom, { duration: 0.8 });
    else map.setView(center, zoom, { animate: false });
  }

  function clearSelection() {
    selectedEntryId = null;
    sessionStorage.removeItem(SELECTED_ENTRY_KEY);
    syncSelection();
    root.querySelector("[data-tour='map-pin']")?.removeAttribute("data-tour");
    map?.closePopup();
  }
  function destroyMap() {
    stopReplay();
    if (map) savedView = { center: map.getCenter(), zoom: map.getZoom() };
    const workspace = root.querySelector("[data-map-workspace]");
    workspace?.classList.remove("is-fullscreen-fallback");
    document.body.classList.remove("map-fallback-fullscreen");
    if (workspace && nativeFullscreenElement() === workspace) void exitNativeFullscreen().catch(() => {});
    map?.remove();
    window.cancelAnimationFrame(selectionFrame);
    selectionFrame = null;
    map = null;
    markerGroup = null;
    markers = new Map();
    fullscreenButton = null;
    selectedLayer = null;
    expandedCluster = null;
    expandedEntryIds = new Set();
  }
  function canManage(entry) {
    const snapshot = data();
    const role = snapshot.run?.current_user_role;
    return Boolean(snapshot.identity && (role === "owner" || role === "member")
      && entry.username === snapshot.identity.username
      && snapshot.entries.some((candidate) => Number(candidate.id) === Number(entry.id)));
  }
  function closeDetail() {
    stopReplay();
    clearSelection();
    sheetExpanded = false;
    renderJournal();
    root.querySelector("[data-map-workspace]")?.classList.remove("has-detail");
    root.querySelector("[data-map-canvas]")?.focus({ preventScroll: true });
  }
  function showDetail(entry, { focus = true } = {}) {
    selectedEntryId = Number(entry.id);
    sessionStorage.setItem(SELECTED_ENTRY_KEY, String(entry.id));
    const workspace = root.querySelector("[data-map-workspace]");
    if (!workspace) return;
    workspace.classList.add("has-detail");
    const detail = detailFor(entry, {
      canManage,
      expanded: sheetExpanded,
      position: Math.max(0, journalEntries().findIndex((item) => Number(item.id) === selectedEntryId)),
      total: journalEntries().length,
      stop: stops.find((stop) => stop.entries.some((item) => Number(item.id) === selectedEntryId)),
      onExpand: (value) => {
        stopReplay();
        sheetExpanded = typeof value === "boolean" ? value : !sheetExpanded;
        renderJournal();
      },
      onPrevious: () => selectAdjacent(-1),
      onNext: () => selectAdjacent(1),
      onSelect: (other) => { stopReplay(); focusEntry(other, { focus: false }); },
      onClose: closeDetail,
      onEdit: (selected) => {
        document.dispatchEvent(new CustomEvent("beer-run:edit-entry", { detail: selected }));
        navigate("log");
      },
      onDelete: (selected, trigger) => {
        const opened = data();
        const target = {
          userId: opened.identity?.id,
          token: auth.getAccessToken(),
          runId: opened.run?.id,
          entryId: selected.id,
        };
        const targetIsCurrent = () => {
          const current = data();
          return current.identity?.id === target.userId
            && auth.getAccessToken() === target.token
            && Number(current.run?.id) === Number(target.runId);
        };
        void (async () => {
          const outcome = await showConfirmation({
          root,
          trigger,
          focusFallback: () => root.querySelector("[data-map-canvas]"),
          title: "Delete this drink?",
          message: selected.image_path
            ? "This action cannot be undone. The uploaded photo will also be deleted."
            : "This action cannot be undone.",
          subjectRows: [
            ["Drink", titleFor(selected)],
            ["Amount", quantityFor(selected.quantity)],
            ["Run", data().run?.name],
          ],
          safeLabel: "Keep drink",
          confirmLabel: "Delete permanently",
          pendingLabel: "Deleting drink...",
          onConfirm: async () => {
            if (!targetIsCurrent()) return { ok: false, dismiss: true, reason: "identity-changed" };
            const snapshot = data();
            const current = snapshot.entries.find((entry) => Number(entry.id) === Number(selected.id));
            if (!current || !canManage(current)) {
              return { ok: false, dismiss: true, reason: "stale-target" };
            }
            const result = await api.deleteEntry(target.runId, target.entryId, target.token);
            if (!result.ok) return {
              ...result,
              dismiss: [401, 403, 404].includes(result.status),
              reason: result.status === 401 ? "session-rejected" : [403, 404].includes(result.status) ? "stale-target" : undefined,
              message: [401, 403, 404].includes(result.status)
                ? "This drink or your access changed before deletion completed. Refresh the run and review it again."
                : result.network
                  ? "Connection unavailable. Nothing was deleted. Check your connection and try again."
                  : "This drink could not be deleted. Nothing was changed.",
            };
            return { ...result, ok: true, committed: true };
          },
          });
          if (!targetIsCurrent()) return;
          if (outcome?.result?.reason === "session-rejected") {
            document.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
            return;
          }
          if (outcome?.result?.reason === "stale-target") {
            clearSelection();
            await refresh?.();
            return;
          }
          if (!outcome?.confirmed) return;
          clearSelection();
          let refreshed = null;
          try {
            refreshed = await refresh?.();
          } catch {
            // The deletion is already authoritative; manual refresh remains available.
          }
          const status = root.querySelector("[data-map-status]");
          if (status) status.textContent = refreshed?.ok === false
            ? `${titleFor(selected)} was deleted. Refresh to update the map.`
            : `${titleFor(selected)} was deleted.`;
        })();
      },
    });
    renderJournal(detail);
    syncSelection();
    if (focus) detail.querySelector(".map-detail__handle")?.focus({ preventScroll: true });
    root.dispatchEvent(new CustomEvent("beer-run:map-detail-opened", { detail: { entryId: entry.id } }));
  }
  function focusEntry(entry, { focus = true, animate = false, recenter = true } = {}) {
    if (clusterEntryIds && !clusterEntryIds.has(Number(entry.id))) clusterEntryIds = null;
    map?.stop?.();
    if (!expandedEntryIds.has(Number(entry.id))) expandedCluster?.unspiderfy();
    showDetail(entry, { focus });
    if (recenter) positionEntry(entry, animate);
  }
  function markerFor(entry) {
    const accessibleTitle = `${titleFor(entry)} logged by ${entry.username || "a runner"}`;
    const marker = window.L.marker([Number(entry.latitude), Number(entry.longitude)], {
      icon: memoryIcon(),
      alt: accessibleTitle,
      keyboard: true,
      autoPanOnFocus: false,
      title: accessibleTitle,
      entryId: Number(entry.id),
    });
    marker.on("add", queueSelection);
    marker.on("click", () => { stopReplay(); focusEntry(entry, { recenter: false }); });
    markers.set(Number(entry.id), marker);
    return marker;
  }
  function initializeMap(entries) {
    if (!window.L) {
      root.querySelector("[data-map-status]").textContent = "The map could not load. Drink details remain available below.";
      return;
    }
    tileWarning = false;
    map = window.L.map(root.querySelector("[data-map-canvas]"), { zoomControl: false }).setView([35.6895, 139.6917], 3);
    window.L.control.zoom({ position: "bottomright" }).addTo(map);
    map.on("dragstart zoomstart", (event) => { if (event.originalEvent) stopReplay(); });
    map.on("zoomend moveend", queueSelection);
    const tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19 });
    tiles.on("tileerror", () => {
      if (tileWarning) return;
      tileWarning = true;
      root.querySelector("[data-map-status]").textContent = "Map tiles are offline. Pins and drink details are still available.";
    });
    tiles.addTo(map);
    addFullscreenControl();
    markerGroup = typeof window.L.markerClusterGroup === "function"
      ? window.L.markerClusterGroup({
        // Handle cluster clicks below so zooming respects the overlaid controls.
        showCoverageOnHover: false, spiderfyOnMaxZoom: false, zoomToBoundsOnClick: false,
        spiderfyDistanceMultiplier: 1.2,
        spiderLegPolylineOptions: { weight: 1, color: "#52685f", opacity: 0.45 },
        animate: !document.body.classList.contains("tour-running") && !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        iconCreateFunction: (cluster) => {
          const icon = el("span", "map-cluster");
          icon.textContent = String(cluster.getChildCount());
          icon.setAttribute("aria-hidden", "true");
          return window.L.divIcon({ html: icon, className: "map-memory-cluster", iconSize: [44, 44] });
        },
      }) : window.L.featureGroup();
    markerGroup.addTo(map);
    markerGroup.on("animationend", syncSelection);
    markerGroup.on("spiderfied", ({ cluster, markers: children }) => {
      expandedCluster = cluster;
      expandedEntryIds = new Set(children.map((marker) => marker.options.entryId));
      const icon = cluster.getElement();
      if (icon) {
        icon.classList.add("is-expanded");
        icon.setAttribute("aria-hidden", "true");
        icon.tabIndex = -1;
      }
      syncSelection();
    });
    markerGroup.on("unspiderfied", ({ cluster }) => {
      const icon = cluster.getElement();
      if (icon) {
        icon.classList.remove("is-expanded");
        icon.removeAttribute("aria-hidden");
        icon.tabIndex = 0;
      }
      if (expandedCluster === cluster) {
        expandedCluster = null;
        expandedEntryIds = new Set();
      }
      syncSelection();
    });
    markerGroup.on("clusterclick", ({ layer }) => {
      stopReplay();
      expandMapCluster(map, layer, mapPadding, () => {
        clusterEntryIds = new Set(layer.getAllChildMarkers().map((marker) => marker.options.entryId));
        sheetExpanded = false;
        if (!clusterEntryIds.has(selectedEntryId)) closeDetail();
        else renderJournal();
      });
    });
    entries.forEach((entry) => markerFor(entry).addTo(markerGroup));
  }
  function fitPins() {
    if (!map || !markerGroup || !markers.size) return;
    const bounds = markerGroup.getBounds?.();
    if (bounds?.isValid()) map.fitBounds(bounds.pad(0.1), { maxZoom: 15, animate: false, ...mapPadding() });
  }

  function renderLoading() {
    const main = root.querySelector("main");
    document.body.classList.add("map-view");
    main.classList.add("main-content--map");
    main.replaceChildren();
    const content = el("div", "map-content map-content--loading");
    const heading = el("header", "page-heading");
    heading.append(el("p", "eyebrow", "Explore the route"), el("h1", "", "Drink map"));
    const toolbar = el("div", "map-toolbar map-toolbar--skeleton home-skeleton");
    toolbar.setAttribute("aria-hidden", "true");
    toolbar.append(el("span", "skeleton-block"), el("span", "skeleton-block"));
    const workspace = el("section", "map-workspace map-workspace--loading home-skeleton");
    workspace.setAttribute("aria-label", "Loading drink map");
    workspace.append(el("span", "map-skeleton-route"), el("span", "map-skeleton-pin map-skeleton-pin--one"), el("span", "map-skeleton-pin map-skeleton-pin--two"));
    content.append(heading, toolbar, workspace);
    main.append(content);
  }

  function render({ fit = false } = {}) {
    if (!active) return;
    if (!getSnapshot().data) {
      destroyMap();
      renderLoading();
      return;
    }
    const snapshot = data();
    const runId = snapshot.run?.id ?? null;
    if (renderedRunId !== null && Number(runId) !== Number(renderedRunId)) {
      destroyMap();
      root.querySelector(".map-content")?.remove();
      selectedUsername = "";
      selectedDay = "";
      clusterEntryIds = null;
      sheetExpanded = false;
      savedView = null;
      clearSelection();
    }
    renderedRunId = runId;
    const entries = Array.isArray(snapshot.entries) ? snapshot.entries : [];
    const runners = [...new Set(entries.map((entry) => entry.username).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    if (selectedUsername && !runners.includes(selectedUsername)) selectedUsername = "";
    const runnerEntries = entries.filter((entry) => !selectedUsername || entry.username === selectedUsername);
    const days = [...new Set(runnerEntries.map(mapDayKey).filter(Boolean))].sort();
    if (selectedDay && !days.includes(selectedDay)) selectedDay = "";
    const signature = JSON.stringify([runId, selectedUsername, selectedDay, snapshot.identity?.id, snapshot.run?.current_user_role, entries]);
    const existing = root.querySelector(".map-content:not(.map-content--loading)");
    if (existing && map && lastSignature === signature) return;
    lastSignature = signature;
    visibleEntries = mapVisibleEntries(entries, { username: selectedUsername, day: selectedDay });
    if (clusterEntryIds) {
      clusterEntryIds = new Set(visibleEntries.filter((entry) => clusterEntryIds.has(Number(entry.id))).map((entry) => Number(entry.id)));
      if (!clusterEntryIds.size) clusterEntryIds = null;
    }
    stops = buildMapStops(visibleEntries);
    const mapped = visibleEntries.filter(isMapped);
    const unmapped = visibleEntries.filter((entry) => !isMapped(entry));
    const main = root.querySelector("main");
    document.body.classList.add("map-view");
    main.classList.add("main-content--map");
    let workspace = root.querySelector("[data-map-workspace]");
    const needsMap = !map || !existing;
    if (!existing) {
      destroyMap();
      main.replaceChildren();
      const content = el("div", "map-content");
      workspace = el("section", "map-workspace");
      workspace.dataset.mapWorkspace = "";
      workspace.setAttribute("aria-label", "Drink locations and selected drink details");
      const canvas = el("div", "map-canvas");
      canvas.dataset.mapCanvas = "";
      canvas.tabIndex = 0;
      canvas.setAttribute("aria-label", "Interactive map of logged drinks");
      canvas.addEventListener("pointerdown", stopReplay, { passive: true });
      canvas.addEventListener("wheel", stopReplay, { passive: true });
      const journal = el("section", "map-journal");
      journal.dataset.mapJournal = "";
      journal.setAttribute("aria-label", "Trip memories");
      workspace.append(canvas, journal);
      content.append(workspace);
      main.append(content);
    }
    workspace.querySelector(".map-explorer-controls")?.remove();
    workspace.querySelector(".map-empty")?.remove();
    const controls = el("div", "map-explorer-controls");
    const heading = el("header", "page-heading map-explorer-heading");
    const headingCopy = el("div");
    headingCopy.append(el("h1", "", "Trip map"));
    const status = el("p", "map-status", `${mapped.length} mapped ${mapped.length === 1 ? "drink" : "drinks"}${unmapped.length ? ` · ${unmapped.length} without a pin` : ""}`);
    status.dataset.mapStatus = "";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    headingCopy.append(status);
    const select = el("select");
    select.className = "map-runner-select";
    select.setAttribute("aria-label", "Filter map by runner");
    const all = el("option", "", "Everyone");
    all.value = "";
    select.append(all);
    runners.forEach((runner) => {
      const option = el("option", "", runner);
      option.value = runner;
      select.append(option);
    });
    select.value = selectedUsername;
    select.addEventListener("change", () => {
      stopReplay(); selectedUsername = select.value; clusterEntryIds = null; clearSelection(); render({ fit: true });
      root.querySelector(".map-runner-select")?.focus({ preventScroll: true });
    });
    heading.append(headingCopy, select);
    const dates = el("div", "map-day-strip");
    dates.setAttribute("role", "group");
    dates.setAttribute("aria-label", "Filter map by day");
    ["", ...days].forEach((day) => {
      const button = el("button", "map-day", dayLabel(day));
      button.type = "button";
      button.dataset.day = day;
      button.setAttribute("aria-label", day ? `Show ${dayLabel(day, true)}, ${day.slice(0, 4)}` : "Show all days");
      button.setAttribute("aria-pressed", String(day === selectedDay));
      button.addEventListener("click", () => {
        if (selectedDay === day) return;
        stopReplay(); selectedDay = day; clusterEntryIds = null; clearSelection(); sheetExpanded = false;
        render({ fit: true });
        [...root.querySelectorAll(".map-day")].find((node) => node.dataset.day === day)?.focus({ preventScroll: true });
      });
      dates.append(button);
    });
    controls.append(heading, dates);
    workspace.append(controls);
    const selectedDate = [...dates.children].find((button) => button.getAttribute("aria-pressed") === "true");
    if (selectedDate) dates.scrollLeft = selectedDate.offsetLeft - dates.offsetLeft - (dates.clientWidth - selectedDate.offsetWidth) / 2;
    let fitButton = workspace.querySelector("[data-map-fit]");
    if (!fitButton) {
      fitButton = el("button", "map-fit-button", "Fit");
      fitButton.type = "button";
      fitButton.setAttribute("aria-label", "Show all pins");
      fitButton.title = "Show all pins";
      fitButton.dataset.mapFit = "";
      fitButton.addEventListener("click", () => { stopReplay(); clusterEntryIds = null; closeDetail(); fitPins(); });
      workspace.append(fitButton);
    }
    fitButton.disabled = !mapped.length;
    if (!mapped.length) {
      const empty = el("section", "state-surface map-empty");
      const mark = el("span", "state-surface__mark", "0");
      mark.setAttribute("aria-hidden", "true");
      const title = selectedUsername ? `No pins for ${selectedUsername}` : "No mapped drinks yet";
      const copy = selectedUsername
        ? "This runner has no drinks with a saved location in the current view."
        : unmapped.length
          ? "The logged pours without a location are still available below."
          : "Capture a location when logging the first pour for this map.";
      empty.append(mark, el("strong", "", title), el("p", "", copy));
      if (selectedUsername) {
        const showEveryone = el("button", "button button--secondary", "Show every runner");
        showEveryone.type = "button";
        showEveryone.addEventListener("click", () => { selectedUsername = ""; selectedDay = ""; render({ fit: true }); });
        empty.append(showEveryone);
      } else if (snapshot.identity && ["owner", "member"].includes(snapshot.run?.current_user_role)) {
        const log = el("a", "button button--primary", "Log a drink");
        log.href = "#log";
        log.dataset.destination = "log";
        empty.append(log);
      }
      workspace.append(empty);
    }
    if (needsMap) {
      initializeMap(mapped);
    } else {
      selectedLayer = null;
      markerGroup?.clearLayers();
      markers = new Map();
      mapped.forEach((entry) => markerFor(entry).addTo(markerGroup));
    }
    const storedId = Number(sessionStorage.getItem(SELECTED_ENTRY_KEY));
    const requested = visibleEntries.find((entry) => Number(entry.id) === Number(selectedEntryId || storedId));
    if (!requested) { clearSelection(); workspace.classList.remove("has-detail"); }
    else selectedEntryId = Number(requested.id);
    renderJournal();
    if (needsMap && savedView && !fit) map?.setView(savedView.center, savedView.zoom, { animate: false });
    else if (fit || needsMap) {
      if (requested) positionEntry(requested);
      else fitPins();
    }
  }
  root.addEventListener("keydown", (event) => {
    if (root.querySelector("dialog[open]")) return;
    if (active && event.target.closest?.("[data-map-canvas]")) stopReplay();
    if (active && event.key === "Escape" && isFallbackFullscreen()) {
      event.preventDefault();
      root.querySelector("[data-map-workspace]")?.classList.remove("is-fullscreen-fallback");
      syncFullscreenControl();
    } else if (active && event.key === "Escape" && selectedEntryId) {
      event.preventDefault();
      closeDetail();
    }
  });
  document.addEventListener("fullscreenchange", syncFullscreenControl);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopReplay(); });
  window.addEventListener("resize", () => {
    if (!active || !map) return;
    updateDockSpace();
    map.invalidateSize({ animate: false, pan: false });
    const entry = visibleEntries.find((item) => Number(item.id) === selectedEntryId);
    if (entry) positionEntry(entry);
  });
  return {
    async prepareTourPin(entryId) {
      if (!map) return false;
      const requestedMap = map;
      if (root.querySelector("[data-map-detail]")) {
        closeDetail();
      } else clearSelection();
      const entry = visibleEntries.find((item) => Number(item.id) === Number(entryId));
      if (!entry || !isMapped(entry) || map !== requestedMap) return false;
      positionEntry(entry, false, map.getMaxZoom());
      const marker = markers.get(Number(entry.id));
      const pin = (markerGroup.getVisibleParent?.(marker) || marker)?.getElement();
      if (!pin) return false;
      pin.dataset.tour = "map-pin";
      return true;
    },
    show(entryId = null) {
      active = true;
      const requestedEntryId = entryId ?? sessionStorage.getItem(SELECTED_ENTRY_KEY);
      selectedEntryId = requestedEntryId === null ? null : Number(requestedEntryId);
      if (entryId !== null) {
        selectedUsername = "";
        selectedDay = "";
        clusterEntryIds = null;
        lastSignature = "";
        sessionStorage.setItem(SELECTED_ENTRY_KEY, String(entryId));
      }
      render();
      if (entryId !== null) {
        const requested = visibleEntries.find((entry) => Number(entry.id) === Number(entryId));
        if (requested) focusEntry(requested);
      }
      root.querySelector("main")?.focus({ preventScroll: true });
    },
    hide() {
      active = false;
      destroyMap();
      document.body.classList.remove("map-view");
      root.querySelector("main")?.classList.remove("main-content--map");
    },
    reset() {
      active = false;
      selectedUsername = "";
      clearSelection();
      renderedRunId = null;
      destroyMap();
      savedView = null;
      selectedDay = "";
      clusterEntryIds = null;
      sheetExpanded = false;
      lastSignature = "";
      visibleEntries = [];
      stops = [];
      document.body.classList.remove("map-view");
      root.querySelector("main")?.classList.remove("main-content--map");
    },
    refresh() { if (active) render(); },
  };
}

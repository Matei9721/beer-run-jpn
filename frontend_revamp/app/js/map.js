import { showConfirmation } from "./confirmation.js?v=revamp-047-10";

const SELECTED_ENTRY_KEY = "beerRun.revamp.selectedEntry";
const SELECTED_ENTRY_ZOOM = 16;
const el = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const valid = (value, min, max) => Number.isFinite(Number(value)) && Number(value) >= min && Number(value) <= max;
const isMapped = (entry) => valid(entry.latitude, -90, 90) && valid(entry.longitude, -180, 180);
const titleFor = (entry) => [entry.drink_type || "Drink", entry.brand].filter(Boolean).join(" · ");
const quantityFor = (value) => Number.isFinite(Number(value))
  ? (Number(value) < 1 ? `${Math.round(Number(value) * 1000)} ml` : `${Number(value).toFixed(2)} L`)
  : "Quantity unavailable";
const abvFor = (value) => Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}% ABV` : "ABV unavailable";
const dateFor = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
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

function detailFor(entry, { canManage, onClose, onEdit, onDelete }) {
  const detail = el("article", "map-detail ticket-surface");
  detail.dataset.mapDetail = "";
  detail.setAttribute("aria-labelledby", "map-detail-title");
  const back = el("button", "button button--quiet map-detail__back", "← Back to map");
  back.type = "button";
  back.addEventListener("click", onClose);
  const header = el("div", "map-detail__header");
  const identity = el("div", "map-detail__identity");
  identity.append(el("p", "eyebrow", "Selected drink"));
  const title = el("h2", "", titleFor(entry));
  title.id = "map-detail-title";
  identity.append(title, el("p", "map-detail__runner", entry.username || "Unknown runner"));
  const close = el("button", "map-detail__close", "Close");
  close.type = "button";
  close.setAttribute("aria-label", "Close drink details and return to the map");
  close.addEventListener("click", onClose);
  header.append(identity, close);
  const facts = el("dl", "map-detail__facts");
  [["Amount", quantityFor(entry.quantity)], ["Strength", abvFor(entry.abv)], ["Logged", dateFor(entry.timestamp)]].forEach(([label, value]) => {
    const fact = el("div");
    fact.append(el("dt", "", label), el("dd", "", value));
    facts.append(fact);
  });
  const location = el("p", "map-detail__location");
  location.append(el("strong", "", "Location"), document.createTextNode(isMapped(entry)
    ? ` ${Number(entry.latitude).toFixed(4)}, ${Number(entry.longitude).toFixed(4)}` : " unavailable"));
  detail.append(back, header, photoFor(entry), facts, location);
  if (canManage(entry)) {
    const actions = el("div", "map-detail__actions");
    const edit = el("button", "button button--secondary", "Edit drink");
    edit.type = "button";
    edit.addEventListener("click", () => onEdit(entry));
    const remove = el("button", "button button--danger", "Delete drink");
    remove.type = "button";
    remove.addEventListener("click", (event) => onDelete(entry, event.currentTarget));
    actions.append(edit, remove);
    detail.append(actions);
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
  const data = () => getSnapshot().data || { run: null, identity: null, entries: [] };

  function resizeMap() {
    if (!map) return;
    const center = map.getCenter();
    const zoom = map.getZoom();
    const applySize = () => {
      if (!map) return;
      map.invalidateSize({ animate: false, pan: false });
      map.setView(center, zoom, { animate: false });
      markerGroup?.refreshClusters?.();
    };
    window.requestAnimationFrame(() => window.requestAnimationFrame(applySize));
    window.setTimeout(applySize, 250);
  }
  function isFallbackFullscreen() {
    return root.querySelector("[data-map-workspace]")?.classList.contains("is-fullscreen-fallback");
  }
  function syncFullscreenControl() {
    const workspace = root.querySelector("[data-map-workspace]");
    const expanded = document.fullscreenElement === workspace || workspace?.classList.contains("is-fullscreen-fallback");
    if (fullscreenButton) {
      const label = expanded ? "Exit full screen map" : "Enter full screen map";
      fullscreenButton.setAttribute("aria-label", label);
      fullscreenButton.setAttribute("aria-pressed", String(Boolean(expanded)));
      fullscreenButton.title = label;
    }
    document.body.classList.toggle("map-fallback-fullscreen", Boolean(workspace?.classList.contains("is-fullscreen-fallback")));
    resizeMap();
  }
  function enterFallbackFullscreen(workspace) {
    workspace.classList.add("is-fullscreen-fallback");
    syncFullscreenControl();
  }
  async function toggleFullscreen() {
    const workspace = root.querySelector("[data-map-workspace]");
    if (!workspace) return;
    if (document.fullscreenElement === workspace) {
      await document.exitFullscreen();
    } else if (workspace.classList.contains("is-fullscreen-fallback")) {
      workspace.classList.remove("is-fullscreen-fallback");
      syncFullscreenControl();
    } else if (workspace.requestFullscreen) {
      try {
        await workspace.requestFullscreen();
      } catch {
        enterFallbackFullscreen(workspace);
      }
    } else enterFallbackFullscreen(workspace);
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

  function clearSelection() {
    selectedEntryId = null;
    sessionStorage.removeItem(SELECTED_ENTRY_KEY);
    markers.forEach((marker) => {
      marker.getElement()?.classList.remove("is-selected");
      marker.setZIndexOffset?.(0);
    });
    map?.closePopup();
  }
  function destroyMap() {
    const workspace = root.querySelector("[data-map-workspace]");
    workspace?.classList.remove("is-fullscreen-fallback");
    document.body.classList.remove("map-fallback-fullscreen");
    if (document.fullscreenElement === workspace) void document.exitFullscreen().catch(() => {});
    map?.remove();
    map = null;
    markerGroup = null;
    markers = new Map();
    fullscreenButton = null;
  }
  function canManage(entry) {
    const snapshot = data();
    const role = snapshot.run?.current_user_role;
    return Boolean(snapshot.identity && (role === "owner" || role === "member")
      && entry.username === snapshot.identity.username
      && snapshot.entries.some((candidate) => Number(candidate.id) === Number(entry.id)));
  }
  function closeDetail() {
    clearSelection();
    root.querySelector("[data-map-detail]")?.remove();
    root.querySelector("[data-map-workspace]")?.classList.remove("has-detail");
    resizeMap();
    root.querySelector("[data-map-canvas]")?.focus({ preventScroll: true });
  }
  function showDetail(entry) {
    selectedEntryId = Number(entry.id);
    sessionStorage.setItem(SELECTED_ENTRY_KEY, String(entry.id));
    const workspace = root.querySelector("[data-map-workspace]");
    if (!workspace) return;
    workspace.querySelector("[data-map-detail]")?.remove();
    workspace.classList.add("has-detail");
    workspace.append(detailFor(entry, {
      canManage,
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
    }));
    markers.forEach((marker, id) => {
      const selected = id === selectedEntryId;
      marker.getElement()?.classList.toggle("is-selected", selected);
      marker.setZIndexOffset?.(selected ? 1000 : 0);
    });
    const focusTarget = window.matchMedia("(max-width: 767px)").matches
      ? workspace.querySelector(".map-detail__back")
      : workspace.querySelector(".map-detail__close");
    focusTarget?.focus({ preventScroll: true });
    resizeMap();
  }
  function focusEntry(entry) {
    const marker = markers.get(Number(entry.id));
    if (!marker || !map) {
      showDetail(entry);
      return;
    }
    const requestedMap = map;
    const revealMarker = () => {
      if (map !== requestedMap || markers.get(Number(entry.id)) !== marker) return;
      map.stop?.();
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), SELECTED_ENTRY_ZOOM), { animate: false });
      showDetail(entry);
    };
    if (markerGroup?.zoomToShowLayer && markerGroup.hasLayer?.(marker)) {
      markerGroup.zoomToShowLayer(marker, revealMarker);
    } else revealMarker();
  }
  function markerFor(entry) {
    const accessibleTitle = `${titleFor(entry)} logged by ${entry.username || "a runner"}`;
    const marker = window.L.marker([Number(entry.latitude), Number(entry.longitude)], {
      alt: accessibleTitle,
      keyboard: true,
      title: accessibleTitle,
    });
    marker.on("click", () => focusEntry(entry));
    markers.set(Number(entry.id), marker);
    return marker;
  }
  function initializeMap(entries) {
    if (!window.L) {
      root.querySelector("[data-map-status]").textContent = "The map could not load. Drink details remain available below.";
      return;
    }
    map = window.L.map(root.querySelector("[data-map-canvas]"), { zoomControl: true }).setView([35.6895, 139.6917], 3);
    const tiles = window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 });
    tiles.on("tileerror", () => {
      if (tileWarning) return;
      tileWarning = true;
      root.querySelector("[data-map-status]").textContent = "Map tiles are offline. Pins and drink details are still available.";
    });
    tiles.addTo(map);
    addFullscreenControl();
    markerGroup = typeof window.L.markerClusterGroup === "function"
      ? window.L.markerClusterGroup({ showCoverageOnHover: false, spiderfyOnMaxZoom: true }) : window.L.layerGroup();
    markerGroup.addTo(map);
    entries.forEach((entry) => markerFor(entry).addTo(markerGroup));
  }
  function fitPins() {
    if (!map || !markerGroup || !markers.size) return;
    const bounds = markerGroup.getBounds?.();
    if (bounds?.isValid()) map.fitBounds(bounds.pad(0.16), { maxZoom: 15, animate: false });
  }

  function renderLoading() {
    const main = root.querySelector("main");
    document.body.classList.add("map-view");
    main.classList.add("main-content--map");
    main.replaceChildren();
    const content = el("div", "map-content map-content--loading");
    const heading = el("header", "page-heading");
    heading.append(el("p", "eyebrow", "Explore the route"), el("h1", "", "Drink map"), el("p", "page-heading__copy", "Loading mapped pours for the selected run."));
    const toolbar = el("div", "map-toolbar map-toolbar--skeleton home-skeleton");
    toolbar.setAttribute("aria-hidden", "true");
    toolbar.append(el("span", "skeleton-block"), el("span", "skeleton-block"));
    const workspace = el("section", "map-workspace map-workspace--loading home-skeleton");
    workspace.setAttribute("aria-label", "Loading drink map");
    workspace.append(el("span", "map-skeleton-route"), el("span", "map-skeleton-pin map-skeleton-pin--one"), el("span", "map-skeleton-pin map-skeleton-pin--two"));
    content.append(heading, toolbar, workspace);
    main.append(content);
  }

  function render() {
    if (!active) return;
    if (!getSnapshot().data) {
      destroyMap();
      renderLoading();
      return;
    }
    const snapshot = data();
    const runId = snapshot.run?.id ?? null;
    if (renderedRunId !== null && Number(runId) !== Number(renderedRunId)) {
      selectedUsername = "";
      clearSelection();
    }
    renderedRunId = runId;
    destroyMap();
    const main = root.querySelector("main");
    document.body.classList.add("map-view");
    main.classList.add("main-content--map");
    main.replaceChildren();
    const content = el("div", "map-content");
    const heading = el("header", "page-heading");
    heading.append(el("p", "eyebrow", "Explore the route"), el("h1", "", "Drink map"), el("p", "page-heading__copy", "Filter by runner and open a drink without leaving the map."));
    const entries = Array.isArray(snapshot.entries) ? snapshot.entries : [];
    const runners = [...new Set(entries.map((entry) => entry.username).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const filtered = selectedUsername ? entries.filter((entry) => entry.username === selectedUsername) : entries;
    const mapped = filtered.filter(isMapped);
    const unmapped = filtered.filter((entry) => !isMapped(entry));
    const toolbar = el("div", "map-toolbar");
    const label = el("label", "map-filter");
    label.append(el("span", "", "Runner"));
    const select = el("select");
    select.setAttribute("aria-label", "Filter map by runner");
    const all = el("option", "", "All runners");
    all.value = "";
    select.append(all);
    runners.forEach((runner) => {
      const option = el("option", "", runner);
      option.value = runner;
      select.append(option);
    });
    select.value = selectedUsername;
    select.addEventListener("change", () => { selectedUsername = select.value; clearSelection(); render(); });
    label.append(select);
    const fit = el("button", "button button--secondary", "Show all pins");
    fit.type = "button";
    fit.disabled = mapped.length === 0;
    fit.addEventListener("click", fitPins);
    toolbar.append(label, fit);
    const status = el("p", "map-status", mapped.length
      ? `${mapped.length} mapped ${mapped.length === 1 ? "drink" : "drinks"}${selectedUsername ? ` from ${selectedUsername}` : ""}`
      : selectedUsername ? `No mapped drinks from ${selectedUsername}.` : "No mapped drinks in this run yet.");
    status.dataset.mapStatus = "";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const workspace = el("section", "map-workspace");
    workspace.dataset.mapWorkspace = "";
    workspace.setAttribute("aria-label", "Drink locations and selected drink details");
    const canvas = el("div", "map-canvas");
    canvas.dataset.mapCanvas = "";
    canvas.tabIndex = 0;
    canvas.setAttribute("aria-label", "Interactive map of logged drinks");
    if (mapped.length) {
      workspace.append(canvas);
    } else {
      workspace.classList.add("map-workspace--empty");
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
        showEveryone.addEventListener("click", () => { selectedUsername = ""; render(); });
        empty.append(showEveryone);
      } else if (snapshot.identity && ["owner", "member"].includes(snapshot.run?.current_user_role)) {
        const log = el("a", "button button--primary", "Log a drink");
        log.href = "#log";
        log.dataset.destination = "log";
        empty.append(log);
      }
      workspace.append(empty);
    }
    content.append(heading, toolbar, status, workspace);
    if (unmapped.length) {
      const fallback = el("details", `map-unmapped${mapped.length ? "" : " map-unmapped--inline"}`);
      fallback.open = mapped.length === 0;
      fallback.append(el("summary", "", `${unmapped.length} ${unmapped.length === 1 ? "drink" : "drinks"} without a map pin`), el("p", "", "These entries have missing or invalid coordinates, but their details are still available."));
      const list = el("ul");
      unmapped.forEach((entry) => {
        const item = el("li");
        const button = el("button", "button button--quiet", `${titleFor(entry)} · ${entry.username || "Unknown runner"}`);
        button.type = "button";
        button.addEventListener("click", () => showDetail(entry));
        item.append(button);
        list.append(item);
      });
      fallback.append(list);
      workspace.append(fallback);
    }
    main.append(content);
    if (mapped.length) {
      initializeMap(mapped);
      fitPins();
    }
    const storedId = Number(sessionStorage.getItem(SELECTED_ENTRY_KEY));
    const requested = filtered.find((entry) => Number(entry.id) === Number(selectedEntryId || storedId));
    if (requested) focusEntry(requested);
    else if (selectedEntryId || storedId) clearSelection();
  }
  root.addEventListener("keydown", (event) => {
    if (root.querySelector("dialog[open]")) return;
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
  return {
    show(entryId = null) {
      active = true;
      const requestedEntryId = entryId ?? sessionStorage.getItem(SELECTED_ENTRY_KEY);
      selectedEntryId = requestedEntryId === null ? null : Number(requestedEntryId);
      if (entryId !== null) {
        selectedUsername = "";
        sessionStorage.setItem(SELECTED_ENTRY_KEY, String(entryId));
      }
      render();
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
      document.body.classList.remove("map-view");
      root.querySelector("main")?.classList.remove("main-content--map");
    },
    refresh() { if (active) render(); },
  };
}

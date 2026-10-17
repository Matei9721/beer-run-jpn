import { updateRunSwitcher, setRefreshPending, setSyncStatus } from "./ui.js?v=beerrun-105-tour-end";

const PAGE_SIZE = 6;
const el = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
};
const button = (text, primary = false) => {
  const node = el("button", `button button--${primary ? "primary" : "secondary"}`, text);
  node.type = "button";
  return node;
};

export function createRunDiscoveryController({ root, api, onSelectRun }) {
  let active = false;
  let target = null;
  let generation = 0;
  let controller = null;
  let featured = null;
  let latest = [];
  let query = "";
  let page = 0;
  let directory = false;
  let selecting = false;
  let directoryView = null;
  let directoryBusy = false;
  let syncedMessage = "Not synced yet";

  function syncPending() {
    setRefreshPending(root, true);
    setSyncStatus(root, "Syncing public runs");
  }
  function syncComplete(ok) {
    setRefreshPending(root, false);
    if (ok) syncedMessage = `Synced ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    setSyncStatus(root, ok ? syncedMessage : "Connection unavailable");
  }

  const isCurrent = (request) => active && request === generation && target?.isConnected;
  function hide() {
    const wasActive = active;
    active = false;
    generation += 1;
    controller?.abort();
    if (wasActive) {
      setRefreshPending(root, false);
      setSyncStatus(root, syncedMessage);
    }
  }
  async function choose(run, trigger) {
    if (selecting) return;
    selecting = true;
    trigger.disabled = true;
    trigger.setAttribute("aria-busy", "true");
    try {
      const result = await onSelectRun(run, { persist: true });
      if (result?.ok) root.dispatchEvent(new CustomEvent("beer-run:discovery-selected"));
      else root.dispatchEvent(new CustomEvent("beer-run:discovery-selection-failed"));
    } finally {
      selecting = false;
      if (trigger.isConnected) {
        trigger.disabled = false;
        trigger.removeAttribute("aria-busy");
      }
    }
  }
  function runCard(run, isFeatured = false) {
    const card = el("article", `discovery-run${isFeatured ? " discovery-run--featured" : ""}`);
    const copy = el("div");
    if (isFeatured) copy.append(el("p", "eyebrow", "Featured run"));
    copy.append(el(isFeatured ? "h2" : "h3", "", run.name), el("p", "discovery-run__meta", `${run.member_count} ${run.member_count === 1 ? "runner" : "runners"} · Public run`));
    if (isFeatured) copy.append(el("p", "", "A trip through Japan, one drink at a time."));
    const open = button(`Open ${run.name}`, isFeatured);
    if (isFeatured) open.dataset.tour = "featured";
    open.addEventListener("click", () => void choose(run, open));
    card.append(copy, open);
    return card;
  }
  function renderShell() {
    directoryView = null;
    target.replaceChildren();
    const header = el("header", "discovery-heading");
    header.append(el("p", "eyebrow", "Find your crew"), el("h1", "", "Choose a run"), el("p", "", "Follow a public trip, or log in to open your own."));
    const tour = button("Take a tour");
    tour.dataset.startTour = "";
    const library = button("My runs");
    library.addEventListener("click", () => root.dispatchEvent(new CustomEvent("beer-run:open-run-library")));
    const actions = el("div", "state-actions");
    actions.append(tour, library);
    header.append(actions);
    const search = el("form", "run-search discovery-search");
    const label = el("label", "run-search__field");
    label.append(el("span", "run-search__label", "Search public runs"));
    const controls = el("span", "run-search__controls");
    const input = el("input", "run-search__input");
    input.type = "search";
    input.name = "q";
    input.minLength = 2;
    input.maxLength = 64;
    input.placeholder = "Search by run name";
    input.value = query;
    const submit = button("Search", true);
    submit.type = "submit";
    controls.append(input, submit);
    label.append(controls);
    search.append(label);
    search.addEventListener("submit", (event) => {
      event.preventDefault();
      query = input.value.trim();
      directory = true;
      page = 0;
      void loadDirectory();
    });
    const status = el("p", "run-search__status");
    status.dataset.discoveryStatus = "";
    status.setAttribute("role", "status");
    const content = el("div", "discovery-content");
    content.dataset.discoveryContent = "";
    target.append(header, search, status, content);
  }
  function contentNode() { return target.querySelector("[data-discovery-content]"); }
  function status(message) { target.querySelector("[data-discovery-status]").textContent = message; }
  function failure(retry) {
    status("Public runs could not be loaded. Please try again.");
    const action = button("Retry");
    action.addEventListener("click", retry);
    contentNode().replaceChildren(action);
  }
  function ensureDirectory() {
    if (directoryView?.list.isConnected) return directoryView;
    const list = el("div", "discovery-list");
    const nav = el("nav", "discovery-pagination");
    nav.setAttribute("aria-label", "Public run pages");
    const previous = button("Previous");
    const next = button("Next");
    previous.disabled = true;
    next.disabled = true;
    const label = el("span");
    label.setAttribute("aria-live", "polite");
    previous.addEventListener("click", () => { if (!directoryBusy) void loadDirectory(page - 1); });
    next.addEventListener("click", () => { if (!directoryBusy) void loadDirectory(page + 1); });
    nav.append(previous, label, next);
    const retry = button("Retry");
    retry.hidden = true;
    retry.addEventListener("click", () => void loadDirectory(directoryView.failedPage));
    const back = button("Back to featured & latest");
    back.addEventListener("click", () => {
      directory = false;
      query = "";
      target.querySelector("input[name=q]").value = "";
      void loadOverview();
    });
    contentNode().replaceChildren(list, nav, retry, back);
    directoryView = { list, nav, previous, next, label, retry, hasNext: false, failedPage: 0 };
    return directoryView;
  }
  async function loadDirectory(requestedPage = page) {
    controller?.abort();
    controller = new AbortController();
    const request = ++generation;
    if (query && query.length < 2) {
      status("Enter at least 2 characters to search.");
      return;
    }
    const view = ensureDirectory();
    view.retry.hidden = true;
    directoryBusy = true;
    view.nav.setAttribute("aria-busy", "true");
    view.list.setAttribute("aria-busy", "true");
    view.list.style.minHeight = `${view.list.getBoundingClientRect().height}px`;
    syncPending();
    status("Loading public runs…");
    const result = await api.discoverPublicBeerRuns({ query, offset: requestedPage * PAGE_SIZE, limit: PAGE_SIZE + 1 }, controller.signal);
    if (!isCurrent(request)) return;
    directoryBusy = false;
    view.nav.removeAttribute("aria-busy");
    syncComplete(result.ok);
    view.list.removeAttribute("aria-busy");
    view.list.style.minHeight = "";
    if (!result.ok) {
      status("Public runs could not be updated. Try again.");
      view.failedPage = requestedPage;
      view.retry.hidden = false;
      view.previous.disabled = page === 0;
      view.next.disabled = !view.hasNext;
      return;
    }
    page = requestedPage;
    const rows = result.data;
    status(rows.length ? `${query ? "Search results" : "All public runs"} · Page ${page + 1}` : "No public runs found. Try another name.");
    view.list.replaceChildren(...rows.slice(0, PAGE_SIZE).map((run) => runCard(run)));
    view.previous.disabled = page === 0;
    view.hasNext = rows.length > PAGE_SIZE;
    view.next.disabled = !view.hasNext;
    view.label.textContent = `Page ${page + 1}`;
  }
  async function loadOverview() {
    controller?.abort();
    controller = new AbortController();
    const request = ++generation;
    status("Loading public runs…");
    syncPending();
    const [featureResult, latestResult] = await Promise.all([
      api.findPublicBeerRunByName("BeerRunJPN", null, controller.signal),
      api.discoverPublicBeerRuns({ limit: 3 }, controller.signal),
    ]);
    if (!isCurrent(request)) return;
    syncComplete(featureResult.ok && latestResult.ok);
    featured = featureResult.ok ? featureResult.data[0] || null : null;
    latest = latestResult.ok ? latestResult.data : [];
    if (!featureResult.ok || !latestResult.ok) return failure(() => void loadOverview());
    status("");
    const content = contentNode();
    directoryView = null;
    content.replaceChildren();
    if (featured) content.append(runCard(featured, true));
    const section = el("section", "discovery-latest");
    section.append(el("h2", "", "Just started"), el("p", "", "The three newest public runs."));
    const list = el("div", "discovery-list");
    latest.forEach((run) => list.append(runCard(run)));
    if (!latest.length) list.append(el("p", "", "No public runs yet. You can create one after logging in."));
    section.append(list);
    const all = button("Browse all public runs");
    all.addEventListener("click", () => { directory = true; page = 0; query = ""; void loadDirectory(); });
    content.append(section, all);
    root.dispatchEvent(new CustomEvent("beer-run:discovery-ready"));
  }
  function show() {
    active = true;
    target = root.querySelector("[data-run-home]");
    if (!target) return;
    updateRunSwitcher(root, null);
    renderShell();
    return directory ? loadDirectory() : loadOverview();
  }
  return {
    show, hide,
    refresh: ({ background = false } = {}) => {
      if (active && target?.isConnected && !selecting && !root.querySelector(".driver-popover, dialog[open]")
        && (!background || !contentNode().contains(document.activeElement))) return directory ? loadDirectory() : loadOverview();
    },
    showOverview: () => { directory = false; query = ""; page = 0; return show(); },
    isActive: () => active && Boolean(target?.isConnected),
  };
}

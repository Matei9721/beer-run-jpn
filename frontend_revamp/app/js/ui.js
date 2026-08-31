const element = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};

function homeRoot(root) {
  return root.querySelector("[data-run-home]");
}

function setText(root, selector, text) {
  const node = root.querySelector(selector);
  if (node) node.textContent = text;
}

function pluralize(value, singular, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function formatNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0";
  return number.toFixed(digits);
}

function formatLiters(value) {
  return `${formatNumber(value)} L`;
}

function formatAlcoholLiters(value) {
  return `${formatNumber(value)} ALC L`;
}

function formatQuantity(value) {
  const liters = Number(value);
  if (!Number.isFinite(liters)) return "Quantity unavailable";
  if (liters < 1) return `${Math.round(liters * 1000)} ml`;
  return formatLiters(liters);
}

function formatAbv(value) {
  const abv = Number(value);
  return Number.isFinite(abv) ? `${abv.toFixed(1)}% ABV` : "ABV unavailable";
}

function formatRelativeTime(timestamp, now = new Date()) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  const elapsed = Math.max(0, now.getTime() - date.getTime());
  const minutes = Math.floor(elapsed / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function isSafeImagePath(imagePath) {
  return typeof imagePath === "string" && /^\/?static\/uploads\//i.test(imagePath);
}

function updateRunSwitcher(root, run, identity = null) {
  setText(root, "[data-run-name]", run?.name || "No run selected");
  if (!run) {
    setText(root, "[data-run-meta]", "Choose a public run");
    return;
  }
  const visibility = run.is_public ? "Public run" : "Private run";
  const role = identity && run.current_user_role ? ` · ${run.current_user_role}` : "";
  setText(root, "[data-run-meta]", `${visibility}${role}`);
}

function appendMeta(container, values) {
  values.filter(Boolean).forEach((value, index) => {
    if (index) container.appendChild(element("span", "activity-meta__separator", "·"));
    container.appendChild(element("span", "", value));
  });
}

function createRunIdentity(run, identity, leaderboard, entries) {
  const section = element("section", "ticket-surface home-identity");
  section.setAttribute("aria-labelledby", "run-home-heading");
  const main = element("div", "home-identity__main");

  const top = element("div", "home-identity__top");
  const copy = element("div", "home-identity__copy");
  copy.append(element("p", "eyebrow", "Current run"), element("h1", "", run.name));
  copy.lastChild.id = "run-home-heading";
  top.append(copy, element("span", "status-tag", run.is_public ? "Public run" : "Private run"));
  main.append(top);

  if (identity && run.current_user_role) {
    main.append(element("p", "run-context", run.current_user_role));
  }

  const totalLiters = leaderboard.reduce(
    (total, runner) => total + (Number(runner.total_liters) || 0),
    0,
  );
  const memberCount = Number(run.member_count) || leaderboard.length;
  const metrics = element("dl", "home-identity__metrics");
  [
    [formatLiters(totalLiters), "logged"],
    [String(entries.length), entries.length === 1 ? "pour" : "pours"],
    [String(memberCount), memberCount === 1 ? "member" : "members"],
  ].forEach(([value, label]) => {
    const metric = element("div", "home-identity__metric");
    metric.append(element("dt", "", label), element("dd", "", value));
    metrics.append(metric);
  });
  main.append(metrics);

  if (!identity) {
    main.append(element("p", "home-view-only", "Sign in to add a pour."));
  }
  section.append(main);

  if (run.has_wrapped) {
    section.classList.add("home-identity--has-wrapped");
    const wrapped = element("div", "home-identity__wrapped");
    const wrappedCopy = element("div", "home-identity__wrapped-copy");
    const availability = element("span", "home-identity__wrapped-status");
    availability.append(element("span", "wrapped-spark", "✦"), document.createTextNode(" Wrapped available"));
    wrappedCopy.append(availability, element("strong", "", "Replay the run"));
    const action = element("a", "wrapped-pulltab", "Open Wrapped");
    action.href = `/wrapped?run=${encodeURIComponent(run.id)}`;
    action.setAttribute("aria-label", `Open Wrapped for ${run.name}`);
    wrapped.append(wrappedCopy, action);
    section.append(wrapped);
  }
  return section;
}

function createEmptyState(title, copy, actionLabel = "") {
  const wrapper = element("div", "home-empty");
  wrapper.append(element("strong", "", title), element("p", "", copy));
  if (actionLabel) {
    const action = element("a", "button button--secondary", actionLabel);
    action.href = "#you";
    action.dataset.destination = "you";
    wrapper.append(action);
  }
  return wrapper;
}

function createPlayerHistoryDialog(username, entries, now) {
  const dialog = element("dialog", "player-history");
  dialog.setAttribute("aria-labelledby", "player-history-heading");
  const surface = element("section", "player-history__surface");
  const header = element("header", "player-history__header");
  const headingCopy = element("div", "player-history__heading");
  headingCopy.append(element("p", "eyebrow", "Player log"));
  const heading = element("h2", "", `${username}'s pours`);
  heading.id = "player-history-heading";
  const playerEntries = entries.filter((entry) => entry.username === username);
  headingCopy.append(heading, element("p", "player-history__summary", `${pluralize(playerEntries.length, "pour")} in this run`));
  const close = element("button", "player-history__close", "Close");
  close.type = "button";
  close.addEventListener("click", () => dialog.close());
  header.append(headingCopy, close);
  surface.append(header);

  if (!playerEntries.length) {
    surface.append(createEmptyState("No pours in this view", "This runner has no entries in the currently loaded run history."));
  } else {
    const list = element("ul", "player-history__list");
    playerEntries.forEach((entry) => {
      const item = element("li", "player-history__item");
      const copy = element("span", "player-history__item-copy");
      const title = element("span", "activity-title");
      title.append(element("strong", "", entry.drink_type || "Drink"));
      if (entry.brand) title.append(element("span", "activity-brand", entry.brand));
      const meta = element("span", "activity-meta");
      appendMeta(meta, [formatQuantity(entry.quantity), formatAbv(entry.abv), formatRelativeTime(entry.timestamp, now)]);
      copy.append(title, meta);
      item.append(createActivityMark(entry), copy);
      list.append(item);
    });
    surface.append(list);
  }

  dialog.append(surface);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  return dialog;
}

function openPlayerHistory(username, entries, now) {
  const dialog = createPlayerHistoryDialog(username, entries, now);
  document.body.append(dialog);
  dialog.showModal();
}

function createStandings(leaderboard, entries, now) {
  const section = element("section", "home-section standings-card");
  const heading = element("div", "home-section__header");
  const headingCopy = element("div", "home-section__heading-copy");
  headingCopy.append(
    element("p", "eyebrow", "Top 3"),
    element("h2", "", "Current standings"),
  );
  heading.append(headingCopy);
  const all = element("a", "quiet-link", "See all");
  all.href = "#standings";
  all.dataset.destination = "standings";
  heading.append(all);
  section.append(heading);

  if (!leaderboard.length) {
    section.append(createEmptyState("No standings yet", "The first logged drink will start the table."));
    return section;
  }

  const list = element("ol", "standings-list");
  leaderboard.slice(0, 3).forEach((runner, index) => {
    const row = element("li", "standings-row");
    const username = runner.username || "Unnamed runner";
    const action = element("button", "standings-link");
    action.type = "button";
    action.dataset.playerHistory = username;
    action.setAttribute("aria-label", `Open ${username}'s pours`);
    const rank = element("span", "standings-rank", String(index + 1));
    rank.setAttribute("aria-label", `Rank ${index + 1}`);
    const measures = element("span", "standings-measures");
    const volume = element("span", "standings-measure standings-measure--volume");
    volume.append(element("small", "", "Volume"), element("strong", "", formatLiters(runner.total_liters)));
    const alcohol = element("span", "standings-measure standings-measure--alcohol");
    alcohol.append(element("small", "", "Alcohol"), element("strong", "", formatAlcoholLiters(runner.total_alcohol)));
    measures.append(volume, alcohol);
    action.append(
      rank,
      element("strong", "standings-name", username),
      measures,
      element("span", "standings-disclosure", "›"),
    );
    action.addEventListener("click", () => openPlayerHistory(username, entries, now));
    row.append(action);
    list.append(row);
  });
  section.append(list);
  return section;
}

function createActivityMark(entry) {
  const media = element("span", "activity-media");
  if (isSafeImagePath(entry.image_path)) {
    const image = element("img", "activity-photo");
    image.src = entry.image_path.startsWith("/") ? entry.image_path : `/${entry.image_path}`;
    image.alt = "";
    image.addEventListener("error", () => {
      image.remove();
      media.append(element("span", "activity-mark", (entry.drink_type || "?").slice(0, 1).toUpperCase()));
    }, { once: true });
    media.append(image);
    return media;
  }
  media.append(element("span", "activity-mark", (entry.drink_type || "?").slice(0, 1).toUpperCase()));
  return media;
}

function createActivityRow(entry, now) {
  const item = element("li", "activity-row");
  const link = element("a", "activity-link");
  link.href = "#map";
  link.dataset.destination = "map";
  link.dataset.entryId = String(entry.id);
  link.setAttribute("aria-label", `Open ${entry.drink_type || "drink"} logged by ${entry.username || "runner"}`);

  const copy = element("span", "activity-copy");
  const title = element("span", "activity-title");
  title.append(element("strong", "", entry.drink_type || "Drink"));
  if (entry.brand) title.append(element("span", "activity-brand", entry.brand));
  const meta = element("span", "activity-meta");
  appendMeta(meta, [formatQuantity(entry.quantity), formatAbv(entry.abv), entry.username || "Runner", formatRelativeTime(entry.timestamp, now)]);
  copy.append(title, meta);
  link.append(createActivityMark(entry), copy, element("span", "activity-disclosure", "Open"));
  item.append(link);
  return item;
}

function createRecentPours(entries, now) {
  const section = element("section", "home-section recent-card");
  section.id = "recent-pours";
  const heading = element("div", "home-section__header");
  heading.append(element("h2", "", "Recent pours"));
  section.append(heading);

  if (!entries.length) {
    section.append(createEmptyState("No recent pours", "Be the first person to log a drink for this run.", "Go to You"));
    return section;
  }

  const list = element("ul", "activity-list");
  entries.slice(0, 3).forEach((entry) => list.append(createActivityRow(entry, now)));
  section.append(list);
  return section;
}

function createErrorNotice(message) {
  const notice = element("div", "home-error");
  notice.setAttribute("role", "alert");
  notice.append(element("strong", "Refresh could not complete"), element("p", "", message));
  return notice;
}

function renderShellState(root, state) {
  const target = homeRoot(root);
  if (target) target.dataset.homeState = state;
}

export function setSyncStatus(root, message) {
  root.querySelectorAll("[data-sync-status]").forEach((region) => {
    region.textContent = message;
  });
}

export function setRefreshPending(root, pending) {
  root.querySelectorAll("[data-refresh]").forEach((button) => {
    button.disabled = pending;
    button.setAttribute("aria-busy", String(pending));
    button.classList.toggle("is-loading", pending);
  });
}

export function renderRunHomeLoading(root) {
  updateRunSwitcher(root, null);
  const target = homeRoot(root);
  if (!target) return;
  target.replaceChildren();
  const identity = element("section", "ticket-surface home-skeleton home-skeleton--identity");
  identity.append(element("span", "skeleton-line skeleton-line--eyebrow"), element("span", "skeleton-line skeleton-line--heading"), element("span", "skeleton-line skeleton-line--copy"));
  const list = element("section", "home-section standings-card home-skeleton");
  list.append(element("span", "skeleton-line skeleton-line--heading"), element("span", "skeleton-row"), element("span", "skeleton-row"), element("span", "skeleton-row"));
  target.append(identity, list);
  renderShellState(root, "loading");
}

export function renderRunHomeUnavailable(root, { title = "No run available", message = "Refresh to look for a public run again." } = {}) {
  updateRunSwitcher(root, null);
  const target = homeRoot(root);
  if (!target) return;
  const surface = element("section", "ticket-surface home-unavailable");
  surface.setAttribute("aria-labelledby", "run-home-unavailable-heading");
  const heading = element("h1", "", title);
  heading.id = "run-home-unavailable-heading";
  surface.append(element("p", "eyebrow", "Run unavailable"), heading, element("p", "", message));
  target.replaceChildren(surface);
  renderShellState(root, "unavailable");
}

export function renderRunHomeError(root, { run, identity, message }) {
  const target = homeRoot(root);
  if (!target) return;
  updateRunSwitcher(root, run, identity);
  const surface = element("section", "ticket-surface home-unavailable");
  surface.setAttribute("aria-labelledby", "run-home-error-heading");
  const heading = element("h1", "", run?.name || "Run data unavailable");
  heading.id = "run-home-error-heading";
  surface.append(element("p", "eyebrow", "Could not sync"), heading, element("p", "", message));
  target.replaceChildren(surface);
  renderShellState(root, "error");
}

export function renderRunHome(root, { run, identity = null, leaderboard = [], entries = [], errorMessage = "", now = new Date() }) {
  const target = homeRoot(root);
  if (!target || !run) return;
  updateRunSwitcher(root, run, identity);
  target.replaceChildren();
  const dashboard = element("div", "home-dashboard");
  dashboard.append(createStandings(leaderboard, entries, now), createRecentPours(entries, now));
  target.append(createRunIdentity(run, identity, leaderboard, entries), dashboard);
  if (errorMessage) target.insertBefore(createErrorNotice(errorMessage), target.firstChild);
  renderShellState(root, errorMessage ? "stale" : "ready");
}

export function bindPreviewFeedback(root = document, { onRefresh = null } = {}) {
  const statusRegions = [...root.querySelectorAll("[data-sync-status]")];
  const announce = (message) => statusRegions.forEach((region) => { region.textContent = message; });
  root.querySelectorAll("[data-refresh]").forEach((button) => {
    button.addEventListener("click", () => {
      if (typeof onRefresh === "function") {
        void onRefresh();
        return;
      }
      announce("Preview shell checked just now");
    });
  });
  root.querySelector("[data-run-switcher]")?.addEventListener("click", () => {
    announce("Run switching is available from the run library.");
  });
}

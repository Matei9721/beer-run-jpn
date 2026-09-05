const PAGE_SIZE = 8;
const el = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
const fixed = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : (0).toFixed(digits);
const liters = (value) => `${fixed(value)} L`;
const alcohol = (value) => `${fixed(value, 3)} alc. L`;
const safeImagePath = (value) => typeof value === "string" && /^\/?static\/uploads\//i.test(value);

function playerEntries(entries, username) {
  const key = String(username || "").toLocaleLowerCase();
  return entries.filter((entry) => String(entry.username || "").toLocaleLowerCase() === key);
}

function heading(eyebrow, title, copy) {
  const header = el("header", "page-heading");
  header.append(el("p", "eyebrow", eyebrow), el("h1", "", title));
  if (copy) header.append(el("p", "page-heading__copy", copy));
  return header;
}

function loggedAt(entry) {
  if (!entry) return "No pours yet";
  const date = new Date(entry.timestamp);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  const zone = entry.timezone_code || entry.timezone || "Timezone not recorded";
  return `${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}, ${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })} ${zone}`;
}

function scoreStrip(leaderboard, entries) {
  const strip = el("dl", "run-score-strip");
  const totals = [
    [String(entries.length), "pours"],
    [liters(leaderboard.reduce((sum, runner) => sum + (Number(runner.total_liters) || 0), 0)), "total volume"],
    [alcohol(leaderboard.reduce((sum, runner) => sum + (Number(runner.total_alcohol) || 0), 0)), "pure alcohol"],
    [loggedAt(entries[0]), "latest log"],
  ];
  totals.forEach(([value, label]) => {
    const item = el("div", "run-score-strip__item");
    item.append(el("dt", "", label), el("dd", "", value));
    strip.append(item);
  });
  return strip;
}

function avatar(username) {
  return el("span", "runner-mark", String(username || "?").trim().slice(0, 1) || "?");
}

function drinkPhoto(entry, className, fallbackText) {
  const media = el("span", className);
  const fallback = () => media.append(el("span", `${className}__fallback`, fallbackText));
  if (safeImagePath(entry?.image_path)) {
    const image = el("img", `${className}__image`);
    image.src = entry.image_path.startsWith("/") ? entry.image_path : `/${entry.image_path}`;
    image.alt = entry.brand ? `${entry.drink_type || "Drink"} by ${entry.brand}` : (entry.drink_type || "Drink");
    image.addEventListener("error", () => { image.remove(); fallback(); }, { once: true });
    media.append(image);
  } else fallback();
  return media;
}

function standingsRow(runner, index, entries, onOpen, metric, leader) {
  const username = runner.username || "Unnamed runner";
  const button = el("button", index === 0 ? "competition-row competition-row--leader" : "competition-row");
  button.type = "button";
  button.setAttribute("aria-label", `Open ${username}'s run history`);
  const identity = el("span", "competition-runner");
  const copy = el("span", "competition-runner__copy");
  const currentValue = Number(metric === "volume" ? runner.total_liters : runner.total_alcohol) || 0;
  const leaderValue = Number(metric === "volume" ? leader?.total_liters : leader?.total_alcohol) || currentValue;
  const gap = Math.max(0, leaderValue - currentValue);
  const gapLabel = index === 0
    ? "Leading"
    : `${metric === "volume" ? fixed(gap) + " L" : fixed(gap, 3) + " alc. L"} behind`;
  copy.append(el("strong", "", username), el("small", "", `${playerEntries(entries, username).length} drinks · ${gapLabel}`));
  identity.append(avatar(username), copy);
  const totals = el("span", "competition-figures");
  totals.append(el("strong", "", liters(runner.total_liters)), el("small", "", alcohol(runner.total_alcohol)));
  button.append(el("span", "competition-rank", String(index + 1)), identity, totals, el("span", "competition-open", "Open"));
  button.addEventListener("click", () => onOpen(username));
  return button;
}

export function renderStandings(root, snapshot, {
  metric = "alcohol",
  pending = false,
  errorMessage = "",
  onMetricChange,
  onRetryMetric,
  onOpenPlayer,
}) {
  const target = root.querySelector("[data-run-home]");
  if (!target) return;
  target.replaceChildren(heading("Current run", "Standings", ""));
  if (!snapshot?.data) {
    const score = el("section", "standings-score-skeleton home-skeleton");
    score.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 4; index += 1) score.append(el("span", "skeleton-block"));
    const loading = el("section", "competition-list home-skeleton");
    loading.setAttribute("aria-label", "Loading standings");
    for (let index = 0; index < 4; index += 1) loading.append(el("span", "skeleton-row standings-skeleton-row"));
    target.append(score, loading);
    return;
  }
  const { leaderboard = [], entries = [] } = snapshot.data;
  if (!leaderboard.length) {
    const empty = el("section", "home-empty state-surface competition-empty");
    const mark = el("span", "state-surface__mark", "0");
    mark.setAttribute("aria-hidden", "true");
    empty.append(mark, el("strong", "", "No drinks yet"), el("p", "", "The first logged drink will start this run’s standings."));
    const canLog = Boolean(snapshot.currentUser && ["owner", "member"].includes(snapshot.currentRun?.current_user_role));
    const action = el("a", "button button--primary", canLog ? "Log a drink" : "View your account");
    action.href = canLog ? "#log" : "#you";
    action.dataset.destination = canLog ? "log" : "you";
    empty.append(action);
    target.append(empty);
    return;
  }
  target.append(scoreStrip(leaderboard, entries));
  const toolbar = el("div", "standings-toolbar");
  const toolbarCopy = el("strong", "", "Rank by");
  const choices = el("div", "standings-toggle");
  choices.setAttribute("role", "group");
  choices.setAttribute("aria-label", "Rank standings by");
  [["alcohol", "Pure alcohol"], ["volume", "Volume"]].forEach(([value, label]) => {
    const choice = el("button", value === metric ? "standings-toggle__button is-selected" : "standings-toggle__button", label);
    choice.type = "button";
    choice.disabled = pending;
    choice.setAttribute("aria-pressed", String(value === metric));
    choice.addEventListener("click", () => onMetricChange(value));
    choices.append(choice);
  });
  toolbar.append(toolbarCopy, choices);
  if (errorMessage) {
    const notice = el("div", "recoverable-state");
    notice.setAttribute("role", "alert");
    const copy = el("span", "recoverable-state__copy");
    copy.append(el("strong", "", "Ranking update paused"), el("p", "", errorMessage));
    const retry = el("button", "button button--secondary", "Retry ranking");
    retry.type = "button";
    retry.addEventListener("click", onRetryMetric);
    notice.append(copy, retry);
    target.append(notice);
  }
  const legend = el("div", "standings-legend");
  legend.append(el("span", "", `Ranked by ${metric === "volume" ? "volume" : "pure alcohol"}`), el("span", "", "Volume / alcohol"));
  const list = el("ol", "competition-list competition-list--full");
  leaderboard.forEach((runner, index) => {
    const classes = ["competition-item"];
    if (index === 0) classes.push("competition-item--leader");
    else if (index < 3) classes.push("competition-item--top");
    const item = el("li", classes.join(" "));
    item.append(standingsRow(runner, index, entries, onOpenPlayer, metric, leaderboard[0]));
    list.append(item);
  });
  target.append(toolbar, legend, list);
}

function metric(value, label) {
  const item = el("div", "runner-metric");
  item.append(el("dd", "", value), el("dt", "", label));
  return item;
}

function historyRow(entry, onOpenEntry) {
  const item = el("li", "history-item");
  const button = el("button", "history-row");
  button.type = "button";
  button.setAttribute("aria-label", `Open ${entry.drink_type || "drink"} on the map`);
  const copy = el("span", "history-copy");
  const title = entry.brand ? `${entry.drink_type || "Drink"} · ${entry.brand}` : (entry.drink_type || "Drink");
  const date = new Date(entry.timestamp);
  const recordedZone = entry.timezone_code || entry.timezone || "Zone unknown";
  const dateLabel = Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const timeLabel = Number.isNaN(date.getTime()) ? "" : `${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })} ${recordedZone}`;
  const quantity = Number(entry.quantity) < 1 ? `${Math.round(Number(entry.quantity) * 1000)} ml` : liters(entry.quantity);
  copy.append(el("strong", "", title), el("small", "", `${quantity} · ${fixed(entry.abv, 1)}% ABV · ${dateLabel}`));
  const time = el("span", "history-time");
  time.append(el("strong", "", timeLabel), el("small", "", "logged"));
  button.append(time, drinkPhoto(entry, "history-media", (entry.drink_type || "?").slice(0, 1).toLocaleUpperCase()), copy, el("span", "history-map-link", "Map ›"));
  button.addEventListener("click", () => onOpenEntry(entry));
  item.append(button);
  return item;
}

export function renderPlayer(root, snapshot, username, { onBack, onOpenEntry }) {
  const target = root.querySelector("[data-run-home]");
  if (!target || !snapshot?.data) return;
  const { leaderboard = [], entries = [] } = snapshot.data;
  const index = leaderboard.findIndex((runner) => runner.username === username);
  const runner = leaderboard[index];
  target.replaceChildren();
  const back = el("button", "button button--quiet player-back", "‹ Back to standings");
  back.type = "button";
  back.addEventListener("click", onBack);
  target.append(back);
  if (!runner) {
    target.append(heading("Runner profile", "Runner unavailable", "This participant is not in the current run standings."));
    return;
  }
  const entriesForPlayer = playerEntries(entries, username);
  target.append(heading("Player history", username, ""));
  const summary = el("section", "runner-summary");
  const top = el("div", "runner-summary__top");
  top.append(avatar(username), el("strong", "", `Rank ${index + 1}`), el("span", "status-tag", `${entriesForPlayer.length} pours`));
  const metrics = el("dl", "runner-summary__metrics");
  metrics.append(metric(liters(runner.total_liters), "volume"), metric(alcohol(runner.total_alcohol), "pure alcohol"), metric(String(entriesForPlayer.length), "drinks"));
  summary.append(top, metrics);
  const history = el("section", "player-drinks");
  const historyHeading = el("div", "home-section__header");
  historyHeading.append(el("h2", "", "Drink history"), el("span", "status-tag status-tag--quiet", "Newest first"));
  history.append(historyHeading);
  if (!entriesForPlayer.length) {
    const empty = el("div", "home-empty");
    empty.append(el("strong", "", "No drinks in this run"), el("p", "", "This runner has no drink history available here."));
    history.append(empty);
  } else {
    const list = el("ol", "history-list");
    const more = el("button", "button button--secondary history-more", "Load more");
    let shown = 0;
    const reveal = () => {
      entriesForPlayer.slice(shown, shown + PAGE_SIZE).forEach((entry) => list.append(historyRow(entry, onOpenEntry)));
      shown += PAGE_SIZE;
      more.hidden = shown >= entriesForPlayer.length;
    };
    more.type = "button";
    more.addEventListener("click", reveal);
    reveal();
    history.append(list, more);
  }
  target.append(summary, history);
}

function renderEntryContext(root, entry, username, onBack) {
  const target = root.querySelector("[data-run-home]");
  if (!target || !entry) return false;
  target.replaceChildren();
  const back = el("button", "button button--quiet player-back", "‹ Back to player history");
  back.type = "button";
  back.addEventListener("click", onBack);
  const title = entry.brand ? `${entry.drink_type || "Drink"} · ${entry.brand}` : (entry.drink_type || "Drink");
  const quantity = Number(entry.quantity) < 1 ? `${Math.round(Number(entry.quantity) * 1000)} ml` : liters(entry.quantity);
  const coordinates = Number.isFinite(Number(entry.latitude)) && Number.isFinite(Number(entry.longitude))
    ? `${Number(entry.latitude).toFixed(5)}, ${Number(entry.longitude).toFixed(5)}`
    : "Location not recorded";
  const card = el("section", "entry-context");
  const copy = el("div", "entry-context__copy");
  copy.append(el("strong", "", title), el("span", "", `${quantity} · ${fixed(entry.abv, 1)}% ABV`));
  const details = el("dl", "entry-context__details");
  [[loggedAt(entry), "logged"], [coordinates, "map coordinates"], [username, "runner"]].forEach(([value, label]) => {
    details.append(metric(value, label));
  });
  card.append(drinkPhoto(entry, "entry-context__media", (entry.drink_type || "?").slice(0, 1).toLocaleUpperCase()), copy, details);
  target.append(back, heading("Drink map context", "Selected pour", ""), card);
  return true;
}

export function createStandingsController({ root = document, api, auth, getSnapshot, navigate }) {
  let active = false;
  let selectedPlayer = null;
  let selectedEntry = null;
  let metric = "alcohol";
  let metricLeaderboard = null;
  let metricError = null;
  let metricRequest = 0;
  const standingsSnapshot = () => {
    const snapshot = getSnapshot();
    if (!metricLeaderboard || !snapshot.data) return snapshot;
    return { ...snapshot, data: { ...snapshot.data, leaderboard: metricLeaderboard } };
  };
  const paintStandings = (pending = false) => renderStandings(root, standingsSnapshot(), {
    metric,
    pending,
    errorMessage: metricError?.message || "",
    onOpenPlayer: showPlayer,
    onMetricChange: changeMetric,
    onRetryMetric: () => changeMetric(metricError?.metric),
  });
  const changeMetric = async (nextMetric) => {
    if (!nextMetric || nextMetric === metric) return;
    const snapshot = getSnapshot();
    if (!snapshot.currentRun) return;
    const request = ++metricRequest;
    metricError = null;
    paintStandings(true);
    const result = await api.fetchLeaderboard(snapshot.currentRun.id, auth.getAccessToken(), null, nextMetric);
    if (request !== metricRequest || !active || selectedPlayer) return;
    if (result.ok) {
      metric = nextMetric;
      metricLeaderboard = Array.isArray(result.data) ? result.data : [];
    } else {
      metricError = {
        metric: nextMetric,
        message: result.network
          ? "You appear to be offline. The current ranking remains available."
          : "The current ranking remains available. Try this view again.",
      };
    }
    paintStandings(false);
  };
  const showStandings = () => {
    active = true;
    selectedPlayer = null;
    paintStandings();
    root.querySelector("main")?.focus({ preventScroll: true });
  };
  const paintPlayer = () => {
    renderPlayer(root, standingsSnapshot(), selectedPlayer, {
      onBack: () => navigate("standings"),
      onOpenEntry: (entry) => {
        selectedEntry = entry;
        sessionStorage.setItem("beerRun.revamp.selectedEntry", String(entry.id));
        navigate("map");
      },
    });
    root.querySelector("main")?.focus({ preventScroll: true });
  };
  const showPlayer = (username, pushHistory = true) => {
    active = true;
    selectedPlayer = username;
    if (pushHistory) history.pushState({ player: username }, "", `#standings/${encodeURIComponent(username)}`);
    paintPlayer();
  };
  return {
    showStandings,
    showPlayer,
    showSelectedEntryContext() {
      const snapshot = getSnapshot();
      const storedId = sessionStorage.getItem("beerRun.revamp.selectedEntry");
      const entry = selectedEntry || snapshot.data?.entries?.find((candidate) => String(candidate.id) === storedId);
      if (!entry) return false;
      selectedEntry = entry;
      selectedPlayer = entry.username || selectedPlayer;
      active = true;
      return renderEntryContext(root, entry, selectedPlayer || "Unknown runner", () => {
        const username = selectedPlayer;
        navigate("standings");
        history.replaceState({ player: username }, "", `#standings/${encodeURIComponent(username)}`);
        showPlayer(username, false);
      });
    },
    hide() { active = false; selectedPlayer = null; },
    reset() {
      active = false;
      selectedPlayer = null;
      selectedEntry = null;
      metricLeaderboard = null;
      metricError = null;
      metricRequest += 1;
      sessionStorage.removeItem("beerRun.revamp.selectedEntry");
    },
    refresh() { if (active) selectedPlayer ? paintPlayer() : paintStandings(); },
  };
}

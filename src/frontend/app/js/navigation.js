import { createAccountAvatar } from "./avatar.js?v=beerrun-123-dicebear-gaze-muted";

const DESTINATIONS = new Set(["run", "standings", "log", "map", "you"]);
const RUN_DESTINATIONS = new Set(["standings", "log", "map"]);

export function bindNavigation(root = document, { onNavigate = null } = {}) {
  let hasRun = false;
  let currentUsername = null;
  const setCurrentUser = (user) => {
    const username = user?.username || null;
    if (username === currentUsername) return;
    currentUsername = username;
    root.querySelectorAll('.nav-item[data-destination="you"]').forEach((link) => {
      const mark = username
        ? createAccountAvatar(username, "nav-avatar")
        : document.createElement("span");
      if (!username) {
        mark.className = "icon icon--user";
        mark.setAttribute("aria-hidden", "true");
      }
      link.firstElementChild.replaceWith(mark);
    });
  };
  const setRunAvailable = (available) => {
    hasRun = Boolean(available);
    root.querySelectorAll(".nav-item[data-destination]").forEach((link) => {
      const disabled = !hasRun && RUN_DESTINATIONS.has(link.dataset.destination);
      if (disabled) {
        link.setAttribute("aria-disabled", "true");
        link.setAttribute("tabindex", "-1");
        link.title = "Choose a run first";
      } else {
        link.removeAttribute("aria-disabled");
        link.removeAttribute("tabindex");
        link.removeAttribute("title");
      }
    });
  };
  const clearDestination = () => {
    root.querySelectorAll(".nav-item[data-destination]").forEach((candidate) => {
      candidate.classList.remove("is-current");
      candidate.removeAttribute("aria-current");
    });
  };
  const selectDestination = (destination, { notify = true } = {}) => {
    if (!DESTINATIONS.has(destination)) return;
    root.querySelectorAll(".nav-item[data-destination]").forEach((candidate) => {
      const isCurrent = candidate.dataset.destination === destination;
      candidate.classList.toggle("is-current", isCurrent);
      if (isCurrent) candidate.setAttribute("aria-current", "page");
      else candidate.removeAttribute("aria-current");
    });
    if (notify && typeof onNavigate === "function") onNavigate(destination);
  };
  root.addEventListener("click", (event) => {
    const link = event.target.closest("[data-destination]");
    if (!link || !DESTINATIONS.has(link.dataset.destination)) return;
    event.preventDefault();
    if (link.getAttribute("aria-disabled") === "true" || (!hasRun && RUN_DESTINATIONS.has(link.dataset.destination))) return;
    history.pushState(null, "", link.href);
    selectDestination(link.dataset.destination);
    root.dispatchEvent(new CustomEvent("beer-run:navigated", { detail: { destination: link.dataset.destination } }));
  });
  window.addEventListener("popstate", () => selectDestination(location.hash.slice(1) || "run"));
  setRunAvailable(false);
  return { clearDestination, selectDestination, setRunAvailable, setCurrentUser };
}

const DESTINATIONS = new Set(["run", "standings", "log", "map", "you"]);

export function bindNavigation(root = document, { onNavigate = null } = {}) {
  const clearDestination = () => {
    root.querySelectorAll(".nav-item[data-destination]").forEach((candidate) => {
      candidate.classList.remove("is-current");
      candidate.removeAttribute("aria-current");
    });
  };
  const selectDestination = (destination) => {
    if (!DESTINATIONS.has(destination)) return;
    root.querySelectorAll(".nav-item[data-destination]").forEach((candidate) => {
      const isCurrent = candidate.dataset.destination === destination;
      candidate.classList.toggle("is-current", isCurrent);
      if (isCurrent) candidate.setAttribute("aria-current", "page");
      else candidate.removeAttribute("aria-current");
    });
    if (typeof onNavigate === "function") onNavigate(destination);
  };
  root.addEventListener("click", (event) => {
    const link = event.target.closest("[data-destination]");
    if (!link || !DESTINATIONS.has(link.dataset.destination)) return;
    event.preventDefault();
    history.pushState(null, "", link.href);
    selectDestination(link.dataset.destination);
  });
  window.addEventListener("popstate", () => selectDestination(location.hash.slice(1) || "run"));
  return { clearDestination, selectDestination };
}

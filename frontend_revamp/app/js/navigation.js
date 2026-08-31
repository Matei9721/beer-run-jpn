const DESTINATIONS = new Set(["run", "standings", "log", "map", "you"]);

export function bindNavigation(root = document) {
  const links = [...root.querySelectorAll("[data-destination]")];
  root.addEventListener("click", (event) => {
    const link = event.target.closest("[data-destination]");
    if (!link || !DESTINATIONS.has(link.dataset.destination)) return;
    event.preventDefault();
    links.forEach((candidate) => {
      const isCurrent = candidate.dataset.destination === link.dataset.destination;
      candidate.classList.toggle("is-current", isCurrent);
      if (isCurrent) candidate.setAttribute("aria-current", "page");
      else candidate.removeAttribute("aria-current");
    });
  });
}

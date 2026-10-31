export { createOnboardingController } from "./tour.js?v=beerrun-126-wait-indicators";

export function setSystemNotice(root, {
  kind = "offline",
  title = "Connection paused",
  message = "Showing the latest available data.",
  retryLabel = "Retry",
} = {}) {
  const banner = root.querySelector("[data-system-banner]");
  if (!banner) return;
  banner.hidden = false;
  banner.dataset.systemKind = kind;
  const titleNode = banner.querySelector("[data-system-banner-title]");
  const copyNode = banner.querySelector("[data-system-banner-copy]");
  const retry = banner.querySelector("[data-system-retry]");
  if (titleNode) titleNode.textContent = title;
  if (copyNode) copyNode.textContent = message;
  if (retry) retry.textContent = retryLabel;
}

export function clearSystemNotice(root) {
  const banner = root.querySelector("[data-system-banner]");
  if (!banner) return;
  banner.hidden = true;
  banner.removeAttribute("data-system-kind");
}

export function bindSystemStateControls(root = document, { onRetry = null } = {}) {
  const retry = async (button) => {
    if (typeof onRetry !== "function") return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      await onRetry();
    } finally {
      if (button.isConnected) {
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    }
  };

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-system-retry]");
    if (button) void retry(button);
  });

  window.addEventListener("offline", () => {
    setSystemNotice(root, {
      title: "Connection paused",
      message: "You’re offline. Current run data and navigation remain available.",
    });
    root.querySelectorAll("[data-sync-status]").forEach((status) => {
      status.textContent = "Offline · showing available data";
    });
  });

  window.addEventListener("online", () => {
    const banner = root.querySelector("[data-system-banner]");
    if (!banner || banner.hidden || banner.dataset.systemKind !== "offline") return;
    setSystemNotice(root, {
      kind: "restored",
      title: "Device is back online",
      message: "BeerRun has not synced yet. Refresh to bring every view up to date.",
      retryLabel: "Refresh",
    });
  });
}

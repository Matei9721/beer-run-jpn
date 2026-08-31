export function bindPreviewFeedback(root = document) {
  const statusRegions = [...root.querySelectorAll("[data-sync-status]")];
  const announce = (message) => statusRegions.forEach((region) => { region.textContent = message; });
  root.querySelectorAll("[data-refresh]").forEach((button) => {
    button.addEventListener("click", () => announce("Preview shell checked just now"));
  });
  root.querySelector("[data-preview-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    announce("Preview action confirmed");
  });
}

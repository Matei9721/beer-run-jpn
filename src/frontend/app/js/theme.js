export const THEME_STORAGE_KEY = "beer_run_revamp_theme_preference";
export const THEME_PREFERENCES = new Set(["system", "light", "dark"]);

function readPreference(storage) {
  const saved = storage.getItem(THEME_STORAGE_KEY);
  return THEME_PREFERENCES.has(saved) ? saved : "system";
}

function resolveTheme(preference, mediaQuery) {
  return preference === "system" ? (mediaQuery.matches ? "dark" : "light") : preference;
}

function withoutColorTransitions(root, apply) {
  const documentRoot = root.ownerDocument;
  if (!documentRoot?.head) return apply();
  const guard = documentRoot.createElement("style");
  guard.dataset.themeTransitionGuard = "";
  guard.textContent = "*,*::before,*::after{transition:none!important}";
  documentRoot.head.append(guard);
  root.getBoundingClientRect();
  const result = apply();
  requestAnimationFrame(() => guard.remove());
  return result;
}

export function createThemeController({ root = document.documentElement, storage = localStorage } = {}) {
  const mediaQuery = matchMedia("(prefers-color-scheme: dark)");
  let preference = readPreference(storage);
  const apply = () => {
    root.dataset.theme = resolveTheme(preference, mediaQuery);
    return root.dataset.theme;
  };
  const handleSystemChange = () => {
    if (preference === "system") withoutColorTransitions(root, apply);
  };
  mediaQuery.addEventListener("change", handleSystemChange);
  apply();

  return {
    getPreference: () => preference,
    setPreference(nextPreference) {
      preference = THEME_PREFERENCES.has(nextPreference) ? nextPreference : "system";
      storage.setItem(THEME_STORAGE_KEY, preference);
      return withoutColorTransitions(root, apply);
    },
    destroy() { mediaQuery.removeEventListener("change", handleSystemChange); },
  };
}

export function bindThemeControls(controller, container) {
  if (!container) return;
  const controls = [...container.querySelectorAll('input[name="preview-theme"]')];
  const selected = controls.find(({ value }) => value === controller.getPreference());
  if (selected) selected.checked = true;
  container.addEventListener("change", (event) => {
    if (event.target instanceof HTMLInputElement) controller.setPreference(event.target.value);
  });
}

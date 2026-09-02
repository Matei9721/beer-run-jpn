import { createApiClient } from "./api.js?v=revamp-023-15";
import { createAuthState } from "./auth.js?v=revamp-023-15";
import { createFormState } from "./form-state.js?v=revamp-023-15";
import { createMapController } from "./map.js?v=revamp-023-15";
import { createLogController } from "./log.js?v=revamp-023-15";
import { bindNavigation } from "./navigation.js?v=revamp-023-15";
import { createRunHomeController } from "./run-home.js?v=revamp-023-15";
import { createRunSelectionState } from "./run-selection.js?v=revamp-023-15";
import { createStandingsController } from "./standings.js?v=revamp-023-15";
import { bindThemeControls, createThemeController } from "./theme.js?v=revamp-023-15";
import { bindPreviewFeedback } from "./ui.js?v=revamp-023-15";

const services = Object.freeze({
  api: createApiClient(),
  auth: createAuthState(),
  form: createFormState(),
  runs: createRunSelectionState(),
});

const theme = createThemeController();
bindThemeControls(theme, document.querySelector("[data-theme-controls]"));
const runHome = createRunHomeController({
  api: services.api,
  auth: services.auth,
  selection: services.runs,
  root: document,
});
let standings;
let mapController;
let logController;
const ensureContentSurface = () => {
  let surface = document.querySelector("[data-run-home]");
  if (surface) return surface;
  surface = document.createElement("div");
  surface.className = "home-content";
  surface.dataset.runHome = "";
  document.querySelector("main")?.replaceChildren(surface);
  return surface;
};
const navigation = bindNavigation(document, { onNavigate: (destination) => {
  if (destination === "standings") {
    logController.hide();
    mapController.hide();
    ensureContentSurface();
    standings.showStandings();
  } else if (destination === "map") {
    logController.hide();
    standings.hide();
    mapController.show();
  }
  else if (destination === "log") {
    standings.hide();
    mapController.hide();
    logController.show();
  }
  else {
    logController.hide();
    standings.hide();
    mapController.hide();
    ensureContentSurface();
    if (destination === "run") runHome.showHome();
  }
} });
standings = createStandingsController({
  root: document,
  api: services.api,
  auth: services.auth,
  getSnapshot: runHome.getSnapshot,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
mapController = createMapController({
  root: document,
  getSnapshot: runHome.getSnapshot,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
logController = createLogController({
  root: document,
  api: services.api,
  auth: services.auth,
  formState: services.form,
  getSnapshot: runHome.getSnapshot,
  refresh: runHome.refresh,
  navigate: (destination) => {
    history.pushState(null, "", `#${destination}`);
    navigation.selectDestination(destination);
  },
});
document.addEventListener("beer-run:open-player", (event) => {
  navigation.selectDestination("standings");
  standings.showPlayer(event.detail.username);
});
runHome.subscribe(() => {
  standings.refresh();
  mapController.refresh();
});
document.addEventListener("click", (event) => {
  const entryLink = event.target.closest("[data-entry-id][data-destination='map']");
  if (!entryLink) return;
  mapController.show(entryLink.dataset.entryId);
});
bindPreviewFeedback(document, { onRefresh: () => runHome.refresh() });
const restoreDestination = () => {
  const match = location.hash.match(/^#standings\/(.+)$/);
  if (match) {
    navigation.selectDestination("standings");
    standings.showPlayer(decodeURIComponent(match[1]), false);
  } else if (location.hash === "#standings") navigation.selectDestination("standings");
  else if (location.hash === "#map") navigation.selectDestination("map");
  else if (location.hash === "#log") navigation.selectDestination("log");
};
window.addEventListener("popstate", restoreDestination);
void runHome.initialize().then(() => {
  restoreDestination();
});

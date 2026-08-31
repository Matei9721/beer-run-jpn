import { createApiClient } from "./api.js?v=revamp-021-19";
import { createAuthState } from "./auth.js?v=revamp-021-19";
import { createFormState } from "./form-state.js?v=revamp-021-19";
import { createMapState } from "./map.js?v=revamp-021-19";
import { bindNavigation } from "./navigation.js?v=revamp-021-19";
import { createRunHomeController } from "./run-home.js?v=revamp-021-19";
import { createRunSelectionState } from "./run-selection.js?v=revamp-021-19";
import { createStandingsController } from "./standings.js?v=revamp-021-19";
import { bindThemeControls, createThemeController } from "./theme.js?v=revamp-021-19";
import { bindPreviewFeedback } from "./ui.js?v=revamp-021-19";

const services = Object.freeze({
  api: createApiClient(),
  auth: createAuthState(),
  form: createFormState(),
  map: createMapState(),
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
const navigation = bindNavigation(document, { onNavigate: (destination) => {
  if (destination === "standings") standings.showStandings();
  else if (destination === "map" && standings.showSelectedEntryContext()) return;
  else {
    standings.hide();
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
document.addEventListener("beer-run:open-player", (event) => {
  navigation.selectDestination("standings");
  standings.showPlayer(event.detail.username);
});
runHome.subscribe(() => standings.refresh());
bindPreviewFeedback(document, { onRefresh: () => runHome.refresh() });
const restoreDestination = () => {
  const match = location.hash.match(/^#standings\/(.+)$/);
  if (match) {
    navigation.selectDestination("standings");
    standings.showPlayer(decodeURIComponent(match[1]), false);
  } else if (location.hash === "#standings") navigation.selectDestination("standings");
};
window.addEventListener("popstate", restoreDestination);
void runHome.initialize().then(() => {
  restoreDestination();
});

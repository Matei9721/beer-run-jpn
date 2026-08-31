import { createApiClient } from "./api.js?v=revamp-020-7";
import { createAuthState } from "./auth.js?v=revamp-020-7";
import { createFormState } from "./form-state.js?v=revamp-020-7";
import { createMapState } from "./map.js?v=revamp-020-7";
import { bindNavigation } from "./navigation.js?v=revamp-020-7";
import { createRunHomeController } from "./run-home.js?v=revamp-020-7";
import { createRunSelectionState } from "./run-selection.js?v=revamp-020-7";
import { bindThemeControls, createThemeController } from "./theme.js?v=revamp-020-7";
import { bindPreviewFeedback } from "./ui.js?v=revamp-020-7";

const services = Object.freeze({
  api: createApiClient(),
  auth: createAuthState(),
  form: createFormState(),
  map: createMapState(),
  runs: createRunSelectionState(),
});

const theme = createThemeController();
bindThemeControls(theme, document.querySelector("[data-theme-controls]"));
bindNavigation();

const runHome = createRunHomeController({
  api: services.api,
  auth: services.auth,
  selection: services.runs,
  root: document,
});
bindPreviewFeedback(document, { onRefresh: () => runHome.refresh() });
void runHome.initialize();

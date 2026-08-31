import { createApiClient } from "./api.js?v=revamp-019-1";
import { createAuthState } from "./auth.js?v=revamp-019-1";
import { createFormState } from "./form-state.js?v=revamp-019-1";
import { createMapState } from "./map.js?v=revamp-019-1";
import { bindNavigation } from "./navigation.js?v=revamp-019-1";
import { createRunSelectionState } from "./run-selection.js?v=revamp-019-1";
import { bindThemeControls, createThemeController } from "./theme.js?v=revamp-019-1";
import { bindPreviewFeedback } from "./ui.js?v=revamp-019-1";

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
bindPreviewFeedback();
void services;

import { updateRunSwitcher } from "./ui.js?v=revamp-025-12";
import { buildInviteShareUrl } from "./invite.js?v=revamp-029-08";
import { showConfirmation } from "./confirmation.js?v=revamp-047-10";

const SEARCH_MIN_LENGTH = 2;
const QUICK_SWITCHER_LIMIT = 6;
const QUICK_SEARCH_LIMIT = 20;

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function sameId(left, right) {
  return left !== null && left !== undefined
    && right !== null && right !== undefined
    && Number(left) === Number(right);
}

function pluralize(value, label) {
  const count = Number(value) || 0;
  return `${count} ${label}${count === 1 ? "" : "s"}`;
}

function roleLabel(role) {
  if (role === "owner") return "Owner";
  if (role === "member") return "Member";
  return "View only";
}

function runInitial(name) {
  return Array.from(String(name || "?").trim())[0]?.toLocaleUpperCase() || "?";
}

function pageHeading(eyebrow, title, copy) {
  const heading = element("header", "page-heading");
  heading.append(element("p", "eyebrow", eyebrow), element("h1", "", title));
  heading.lastChild.id = "run-library-heading";
  heading.append(element("p", "page-heading__copy", copy));
  return heading;
}

function action(label, className = "button button--secondary") {
  const button = element("button", className, label);
  button.type = "button";
  return button;
}

function runRow(run, { currentRunId = null, knownMembership = false } = {}) {
  const isCurrent = sameId(run.id, currentRunId);
  const button = action("", "run-library-row");
  button.dataset.runChoice = String(run.id);
  button.setAttribute("aria-label", `${isCurrent ? "View current run" : "Switch to"} ${run.name}`);
  button.setAttribute("aria-pressed", String(isCurrent));

  const mark = element("span", "run-library-row__mark", runInitial(run.name));
  mark.setAttribute("aria-hidden", "true");
  const copy = element("span", "run-library-row__copy");
  copy.append(element("strong", "run-library-row__name", run.name));
  const details = [
    roleLabel(run.current_user_role),
    run.is_public ? "Public" : "Private",
    pluralize(run.member_count, "member"),
  ];
  if (knownMembership) details.push("In My runs");
  copy.append(element("span", "run-library-row__meta", details.join(" · ")));
  const affordance = element("span", "run-library-row__action", isCurrent ? "Current" : "Switch");
  affordance.setAttribute("aria-hidden", "true");
  button.append(mark, copy, affordance);
  return button;
}

function emptyState(title, copy, actionLabel = "", actionName = "libraryCreate") {
  const state = element("div", "run-library-empty");
  state.append(element("strong", "", title), element("p", "", copy));
  if (actionLabel) {
    const button = action(actionLabel, "button button--secondary");
    button.dataset[actionName] = "";
    state.append(button);
  }
  return state;
}

function inlineError(message) {
  const notice = element("div", "run-library-error");
  notice.setAttribute("role", "alert");
  notice.append(element("strong", "", "Could not load this section"), element("p", "", message));
  return notice;
}

export function createRunLibraryController({
  root = document,
  api,
  auth,
  getSnapshot,
  onSelectRun,
  onQuickSelectRun,
  onIdentityChange,
  onOpenLibrary,
  onShowRun,
}) {
  let active = false;
  let view = "library";
  let identity = null;
  let memberships = [];
  let loadGeneration = 0;
  let loadController = null;
  let searchGeneration = 0;
  let searchController = null;
  let lastFocused = null;
  let announcement = "";
  let switcherDialog = null;
  let switcherGeneration = 0;
  let switcherController = null;
  let switcherCloseTimer = null;
  let quickQuery = "";
  let managementGeneration = 0;

  const main = () => root.querySelector("main");
  const mutationTarget = (run) => ({
    userId: getSnapshot().currentUser?.id,
    token: auth.getAccessToken(),
    runId: run.id,
  });
  const targetIsCurrent = (target) => (
    getSnapshot().currentUser?.id === target.userId
    && auth.getAccessToken() === target.token
    && Number(getSnapshot().currentRun?.id) === Number(target.runId)
  );
  const identityIsCurrent = (target) => (
    getSnapshot().currentUser?.id === target.userId
    && auth.getAccessToken() === target.token
  );

  async function reconcileRunMutation(outcome, target, { successMessage, staleMessage }) {
    if (!identityIsCurrent(target)) return;
    if (outcome?.result?.reason === "session-rejected") {
      document.dispatchEvent(new CustomEvent("beer-run:session-rejected"));
      return;
    }
    if (!outcome?.confirmed && outcome?.result?.reason !== "stale-target") return;
    announcement = outcome.confirmed ? successMessage : staleMessage;
    try {
      await onIdentityChange?.();
      if (!identityIsCurrent(target)) return;
      view = "library";
      history.replaceState(null, "", "#runs");
      await load();
    } catch {
      view = "library";
      history.replaceState(null, "", "#runs");
      announcement = outcome.confirmed
        ? `${successMessage} Refresh the run library to update this view.`
        : staleMessage;
      renderLibrary();
    }
    main()?.querySelector("#run-library-heading")?.focus?.({ preventScroll: true });
  }

  function setTriggerState(isOpen) {
    const trigger = root.querySelector("[data-run-switcher]");
    if (!trigger) return;
    trigger.setAttribute("aria-expanded", String(isOpen));
    trigger.classList.toggle("is-open", isOpen);
  }

  function abortWork() {
    loadGeneration += 1;
    searchGeneration += 1;
    loadController?.abort();
    searchController?.abort();
    loadController = null;
    searchController = null;
  }

  function finishSwitcherClose({ restoreFocus = true } = {}) {
    if (!switcherDialog) return;
    const dialog = switcherDialog;
    switcherDialog = null;
    if (dialog.open && typeof dialog.close === "function") dialog.close();
    dialog.remove();
    document.body.classList.remove("run-switcher-open");
    document.body.style.removeProperty("--run-switcher-scrollbar-width");
    setTriggerState(false);
    if (restoreFocus) root.querySelector("[data-run-switcher]")?.focus?.({ preventScroll: true });
  }

  function closeSwitcher({ restoreFocus = true, immediate = false } = {}) {
    if (!switcherDialog) return;
    switcherGeneration += 1;
    switcherController?.abort();
    switcherController = null;
    clearTimeout(switcherCloseTimer);
    switcherDialog.classList.remove("is-visible");
    switcherDialog.classList.add("is-closing");
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (immediate || reducedMotion) {
      finishSwitcherClose({ restoreFocus });
      return;
    }
    switcherCloseTimer = setTimeout(() => finishSwitcherClose({ restoreFocus }), 140);
  }

  function createSwitcherDialog() {
    clearTimeout(switcherCloseTimer);
    const dialog = element("dialog", "run-quick-switcher");
    dialog.id = "run-switcher-dialog";
    dialog.setAttribute("aria-labelledby", "run-quick-switcher-heading");
    dialog.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeSwitcher();
    }, { capture: true });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeSwitcher();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeSwitcher();
    });
    const scrollbarWidth = Math.max(0, window.innerWidth - document.documentElement.clientWidth);
    document.body.style.setProperty("--run-switcher-scrollbar-width", `${scrollbarWidth}px`);
    document.body.append(dialog);
    document.body.classList.add("run-switcher-open");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    switcherDialog = dialog;
    setTriggerState(true);
    requestAnimationFrame(() => dialog.classList.add("is-visible"));
    return dialog;
  }

  function quickCurrent(run) {
    const current = element("section", "quick-switcher-current");
    current.setAttribute("aria-label", "Active run");
    const mark = element("span", "quick-switcher-current__mark", runInitial(run?.name));
    mark.setAttribute("aria-hidden", "true");
    current.append(mark);
    const copy = element("span", "quick-switcher-current__copy");
    copy.append(
      element("span", "eyebrow", "Active run"),
      element("strong", "", run?.name || "No run selected"),
      element("span", "", run
        ? `${run.is_public ? "Public" : "Private"} · ${roleLabel(run.current_user_role)}`
        : "Run unavailable"),
    );
    current.append(copy, element("span", "status-tag", "Current"));
    return current;
  }

  function renderQuickSwitcher({ loading = false, loadError = "" } = {}) {
    if (!switcherDialog) return;
    const hadFocus = switcherDialog.contains(document.activeElement);
    const hadSearchFocus = document.activeElement?.matches?.("[data-quick-run-search]");
    const panel = element("section", "quick-switcher-panel");
    panel.setAttribute("aria-busy", String(loading));
    const header = element("header", "quick-switcher-header");
    const heading = element("div", "quick-switcher-heading");
    heading.append(element("p", "eyebrow", "Beer runs"));
    const title = element("h2", "", "Switch run");
    title.id = "run-quick-switcher-heading";
    heading.append(title);
    const close = action("Close", "button button--quiet quick-switcher-close");
    close.dataset.quickSwitcherClose = "";
    header.append(heading, close);
    panel.append(header, quickCurrent(getSnapshot().currentRun));

    const options = element("section", "quick-switcher-options");
    const optionsHeading = element("h3", "", "My other runs");
    options.append(optionsHeading);
    if (loading) {
      const skeleton = element("div", "quick-switcher-skeleton run-library-skeleton");
      skeleton.setAttribute("role", "status");
      skeleton.setAttribute("aria-label", "Loading your runs");
      skeleton.append(element("span", "skeleton-row"), element("span", "skeleton-row"));
      options.append(skeleton);
    } else if (loadError) {
      options.append(inlineError(loadError));
    } else if (!identity) {
      options.append(emptyState("Sign in to see My runs", "You can still browse public runs in the full library."));
    } else {
      const otherRuns = memberships
        .filter((run) => !sameId(run.id, getSnapshot().currentRun?.id))
        .sort((left, right) => String(left.name).localeCompare(String(right.name), undefined, { sensitivity: "base" }));
      if (!otherRuns.length) {
        options.append(emptyState("No other runs yet", "Use the full library to create a run or find a public crew."));
      } else {
        if (otherRuns.length > QUICK_SWITCHER_LIMIT) {
          const search = element("label", "quick-switcher-search");
          search.append(element("span", "run-search__label", "Search my runs"));
          const input = element("input", "run-search__input");
          input.type = "search";
          input.autocomplete = "off";
          input.placeholder = "Type a run name";
          input.value = quickQuery;
          input.dataset.quickRunSearch = "";
          input.addEventListener("input", (event) => {
            quickQuery = event.currentTarget.value;
            if (event.isComposing) return;
            renderQuickSwitcher();
          });
          input.addEventListener("compositionend", (event) => {
            quickQuery = event.currentTarget.value;
            renderQuickSwitcher();
          });
          search.append(input);
          options.append(search);
        }

        const normalizedQuery = quickQuery.trim().toLocaleLowerCase();
        const matchingRuns = normalizedQuery
          ? otherRuns.filter((run) => String(run.name).toLocaleLowerCase().includes(normalizedQuery))
          : otherRuns;
        const visibleLimit = normalizedQuery ? QUICK_SEARCH_LIMIT : QUICK_SWITCHER_LIMIT;
        const visibleRuns = matchingRuns.slice(0, visibleLimit);
        const status = element("p", "quick-switcher-status");
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        if (normalizedQuery) {
          status.textContent = matchingRuns.length
            ? `${pluralize(matchingRuns.length, "matching run")}${matchingRuns.length > visibleLimit ? ` · First ${visibleLimit} shown` : ""}`
            : `No runs match “${quickQuery.trim()}”.`;
        } else if (otherRuns.length > QUICK_SWITCHER_LIMIT) {
          status.textContent = `Showing ${QUICK_SWITCHER_LIMIT} of ${otherRuns.length} runs alphabetically.`;
        }
        if (status.textContent) options.append(status);

        if (!visibleRuns.length) {
          options.append(emptyState("No matching runs", "Try a shorter or different name."));
        } else {
          const list = element("div", "quick-switcher-list run-library-list");
          visibleRuns.forEach((run) => {
            const row = runRow(run, { currentRunId: getSnapshot().currentRun?.id });
            row.addEventListener("click", () => void quickSelect(run, row));
            list.append(row);
          });
          options.append(list);
        }
      }
    }
    panel.append(options);

    const footer = element("footer", "quick-switcher-footer");
    const openLibrary = action("Open full run library", "button button--secondary");
    openLibrary.dataset.quickSwitcherLibrary = "";
    footer.append(openLibrary);
    panel.append(footer);
    switcherDialog.replaceChildren(panel);
    close.addEventListener("click", () => closeSwitcher());
    openLibrary.addEventListener("click", () => {
      closeSwitcher({ restoreFocus: false, immediate: true });
      onOpenLibrary?.();
    });
    if (hadSearchFocus) {
      const input = switcherDialog.querySelector("[data-quick-run-search]");
      input?.focus({ preventScroll: true });
      input?.setSelectionRange(input.value.length, input.value.length);
    } else if (hadFocus) close.focus({ preventScroll: true });
  }

  async function loadQuickSwitcher() {
    const request = ++switcherGeneration;
    switcherController?.abort();
    switcherController = new AbortController();
    const signal = switcherController.signal;
    const token = auth.getAccessToken();
    renderQuickSwitcher({ loading: true });

    let nextIdentity = null;
    if (token) {
      const identityResult = await api.fetchCurrentUser(token, signal);
      if (request !== switcherGeneration || identityResult.aborted) return;
      if (identityResult.ok) nextIdentity = identityResult.data;
    }
    const snapshotIdentity = getSnapshot().currentUser;
    const identityChanged = !sameId(snapshotIdentity?.id, nextIdentity?.id)
      && (snapshotIdentity || nextIdentity);
    if (identityChanged && typeof onIdentityChange === "function") {
      await onIdentityChange();
      if (request !== switcherGeneration || !switcherDialog) return;
    }

    identity = nextIdentity;
    memberships = [];
    let loadError = "";
    if (identity) {
      const result = await api.fetchMyBeerRuns(token, signal);
      if (request !== switcherGeneration || result.aborted) return;
      if (result.ok && Array.isArray(result.data)) memberships = result.data;
      else loadError = result.network
        ? "Connection unavailable. Your active run has not changed."
        : "Your memberships could not be loaded. Close and try again.";
    }
    switcherController = null;
    renderQuickSwitcher({ loadError });
  }

  async function quickSelect(run, trigger) {
    trigger.disabled = true;
    trigger.setAttribute("aria-busy", "true");
    closeSwitcher({ restoreFocus: false, immediate: true });
    await onQuickSelectRun?.(run, { persist: true });
  }

  function openSwitcher() {
    if (switcherDialog) {
      closeSwitcher();
      return;
    }
    quickQuery = "";
    createSwitcherDialog();
    renderQuickSwitcher({ loading: true });
    switcherDialog?.querySelector("[data-quick-switcher-close]")?.focus?.({ preventScroll: true });
    void loadQuickSwitcher();
  }

  function prepareSurface() {
    const target = main();
    target?.classList.remove("main-content--map");
    target?.classList.add("main-content--runs");
    document.body.classList.remove("map-view");
    return target;
  }

  function renderLoading() {
    const target = prepareSurface();
    if (!target) return;
    const content = element("div", "run-library-content run-library-content--loading");
    content.id = "run-library";
    content.dataset.runLibrary = "";
    content.setAttribute("aria-labelledby", "run-library-heading");
    content.append(pageHeading("Run library", "Your beer runs", "Switch runs, discover public crews, or start a new one."));
    const current = element("section", "ticket-surface run-library-current run-library-skeleton");
    current.setAttribute("aria-label", "Loading current run");
    current.append(
      element("span", "skeleton-line skeleton-line--eyebrow"),
      element("span", "skeleton-line skeleton-line--heading"),
      element("span", "skeleton-line skeleton-line--wide"),
    );
    const list = element("section", "run-library-section run-library-skeleton");
    list.append(element("span", "skeleton-line skeleton-line--heading"));
    list.append(element("span", "skeleton-row"), element("span", "skeleton-row"));
    content.append(current, list);
    target.replaceChildren(content);
  }

  function renderCurrentRun(container, run) {
    const section = element("section", "ticket-surface run-library-current");
    section.setAttribute("aria-labelledby", "run-library-current-name");
    const top = element("div", "run-library-current__top");
    const copy = element("div", "run-library-current__copy");
    copy.append(element("p", "eyebrow", "Viewing now"));
    const title = element("h2", "", run?.name || "No run selected");
    title.id = "run-library-current-name";
    copy.append(title);
    if (run) {
      copy.append(element("p", "run-library-current__meta", [
        run.is_public ? "Public" : "Private",
        pluralize(run.member_count, "member"),
        roleLabel(run.current_user_role),
      ].join(" · ")));
    } else {
      copy.append(element("p", "run-library-current__meta", "Choose a readable public run to continue."));
    }
    const status = element("span", "status-tag", run ? "Active run" : "Unavailable");
    top.append(copy, status);
    section.append(top);

    if (run) {
      const actions = element("div", "run-library-current__actions");
      const back = action("View run", "button run-library-current__primary-action");
      back.dataset.libraryShowRun = "";
      actions.append(back);
      const utilities = element("div", "run-library-current__utilities");
      if (identity && ["owner", "member"].includes(run.current_user_role)) {
        const manage = action("Manage run", "run-library-current__utility");
        manage.dataset.libraryManage = "";
        utilities.append(manage);
      }
      if (utilities.childElementCount) actions.append(utilities);
      section.append(actions);
    }
    container.append(section);
  }

  function renderMemberships(container, currentRun, loadError = "") {
    const section = element("section", "run-library-section run-library-memberships");
    section.setAttribute("aria-labelledby", "run-library-memberships-heading");
    const heading = element("div", "run-library-section__heading");
    const copy = element("div", "");
    const title = element("h2", "", "My runs");
    title.id = "run-library-memberships-heading";
    copy.append(title, element("p", "", identity ? "Runs where you are a member." : "Memberships are tied to your account."));
    heading.append(copy);
    if (identity) {
      const create = action("", "button button--primary");
      create.dataset.libraryCreate = "";
      const icon = element("span", "icon icon--plus");
      icon.setAttribute("aria-hidden", "true");
      create.append(icon, document.createTextNode("Create run"));
      heading.append(create);
    }
    section.append(heading);

    if (loadError) {
      section.append(inlineError(loadError));
    } else if (!identity) {
      section.append(emptyState(
        "Log in to see My runs",
        "Public runs remain available below while you are logged out.",
        "Log in",
        "authOpen",
      ));
    } else {
      const otherRuns = memberships.filter((run) => !sameId(run.id, currentRun?.id));
      if (!otherRuns.length) {
        section.append(emptyState(
          memberships.length ? "No other runs yet" : "You have not joined a run yet",
          memberships.length
            ? "The run above is your only membership."
            : "Create a run here, or find a public crew below.",
          "Create run",
        ));
      } else {
        const list = element("div", "run-library-list");
        otherRuns.forEach((run) => list.append(runRow(run, { currentRunId: currentRun?.id })));
        section.append(list);
      }
    }
    container.append(section);
  }

  function renderDiscovery(container) {
    const section = element("section", "run-library-section run-library-discovery");
    section.setAttribute("aria-labelledby", "run-library-discovery-heading");
    const heading = element("div", "run-library-section__heading");
    const copy = element("div", "");
    const title = element("h2", "", "Browse public runs");
    title.id = "run-library-discovery-heading";
    copy.append(title, element("p", "", "Search by the beginning of a run name. Private runs never appear here."));
    heading.append(copy);
    section.append(heading);

    const form = element("form", "run-search");
    form.dataset.publicRunSearch = "";
    const label = element("label", "run-search__field");
    label.htmlFor = "public-run-search";
    label.append(element("span", "run-search__label", "Run name"));
    const controls = element("span", "run-search__controls");
    const input = element("input", "run-search__input");
    input.id = "public-run-search";
    input.name = "q";
    input.type = "search";
    input.minLength = SEARCH_MIN_LENGTH;
    input.maxLength = 64;
    input.autocomplete = "off";
    input.placeholder = "Try Beer, Kyoto, or Weekend";
    const submit = action("Search", "button button--primary");
    submit.type = "submit";
    controls.append(input, submit);
    label.append(controls);
    form.append(label);
    const status = element("p", "run-search__status", "Enter at least 2 characters to search.");
    status.dataset.publicRunSearchStatus = "";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const results = element("div", "run-library-list run-search__results");
    results.dataset.publicRunResults = "";
    form.append(status, results);
    section.append(form);
    container.append(section);
  }

  function bindLibrary() {
    const target = main();
    target?.querySelector("[data-auth-open]")?.addEventListener("click", () => {
      root.dispatchEvent(new CustomEvent("beer-run:open-auth", { detail: { mode: "login", returnTo: "#runs" } }));
    });
    target?.querySelectorAll("[data-library-create]").forEach((button) => {
      button.addEventListener("click", () => openView("create"));
    });
    target?.querySelector("[data-library-manage]")?.addEventListener("click", () => openView("manage"));
    target?.querySelector("[data-library-show-run]")?.addEventListener("click", () => onShowRun?.());
    target?.querySelectorAll("[data-run-choice]").forEach((button) => {
      button.addEventListener("click", () => {
        const run = memberships.find((candidate) => sameId(candidate.id, button.dataset.runChoice));
        if (run) void select(run, button);
      });
    });
    target?.querySelector("[data-public-run-search]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      void search(event.currentTarget.elements.q.value);
    });
  }

  function renderLibrary({ loadError = "" } = {}) {
    if (!active || view !== "library") return;
    const target = prepareSurface();
    if (!target) return;
    const currentRun = getSnapshot().currentRun;
    updateRunSwitcher(root, currentRun, getSnapshot().currentUser);
    const content = element("div", "run-library-content");
    content.id = "run-library";
    content.dataset.runLibrary = "";
    content.setAttribute("aria-labelledby", "run-library-heading");
    content.append(pageHeading("Run library", "Your beer runs", "Switch runs, discover public crews, or start a new one."));
    if (announcement) {
      const notice = element("p", "run-library-notice", announcement);
      notice.setAttribute("role", "status");
      content.append(notice);
      announcement = "";
    }
    renderCurrentRun(content, currentRun);
    renderMemberships(content, currentRun, loadError);
    renderDiscovery(content);
    target.replaceChildren(content);
    bindLibrary();
  }

  async function load() {
    const request = ++loadGeneration;
    loadController?.abort();
    loadController = new AbortController();
    const signal = loadController.signal;
    const token = auth.getAccessToken();
    renderLoading();

    let nextIdentity = null;
    if (token) {
      const identityResult = await api.fetchCurrentUser(token, signal);
      if (request !== loadGeneration || identityResult.aborted) return;
      if (identityResult.ok) nextIdentity = identityResult.data;
    }

    const snapshotIdentity = getSnapshot().currentUser;
    const identityChanged = !sameId(snapshotIdentity?.id, nextIdentity?.id)
      && (snapshotIdentity || nextIdentity);
    if (identityChanged && typeof onIdentityChange === "function") {
      await onIdentityChange();
      if (request !== loadGeneration) return;
    }

    identity = nextIdentity;
    memberships = [];
    let loadError = "";
    if (identity) {
      const result = await api.fetchMyBeerRuns(token, signal);
      if (request !== loadGeneration || result.aborted) return;
      if (result.ok && Array.isArray(result.data)) memberships = result.data;
      else loadError = result.network
        ? "Connection unavailable. Your current run remains selected."
        : "Your memberships could not be loaded. Refresh and try again.";
    }
    loadController = null;
    renderLibrary({ loadError });
  }

  async function select(run, trigger) {
    trigger.disabled = true;
    trigger.setAttribute("aria-busy", "true");
    const pending = onSelectRun?.(run, { persist: true });
    onShowRun?.();
    await pending;
  }

  async function search(rawQuery) {
    const query = String(rawQuery || "").trim();
    const status = main()?.querySelector("[data-public-run-search-status]");
    const results = main()?.querySelector("[data-public-run-results]");
    if (!status || !results) return;
    searchGeneration += 1;
    const request = searchGeneration;
    searchController?.abort();
    searchController = null;
    results.replaceChildren();
    if (query.length < SEARCH_MIN_LENGTH) {
      status.textContent = "Enter at least 2 characters to search.";
      return;
    }

    status.textContent = "Searching public runs…";
    searchController = new AbortController();
    const result = await api.searchPublicBeerRuns(query, identity ? auth.getAccessToken() : null, searchController.signal);
    if (request !== searchGeneration || result.aborted || !active || view !== "library") return;
    searchController = null;
    if (!result.ok) {
      status.textContent = result.network
        ? "Public search is offline. Try again when the connection returns."
        : "Public search could not be completed. Try again.";
      return;
    }

    const runs = Array.isArray(result.data) ? result.data.filter((run) => run.is_public) : [];
    if (!runs.length) {
      status.textContent = `No public runs begin with “${query}”.`;
      results.append(emptyState("No public runs found", "Try a shorter or different beginning."));
      return;
    }
    const membershipIds = new Set(memberships.map((run) => Number(run.id)));
    runs.forEach((run) => {
      const row = runRow(run, {
        currentRunId: getSnapshot().currentRun?.id,
        knownMembership: membershipIds.has(Number(run.id)),
      });
      row.addEventListener("click", () => void select(run, row));
      results.append(row);
    });
    status.textContent = `${pluralize(runs.length, "public run")} found.`;
  }

  function apiMessage(result, fallback) {
    if (result?.network) return "Connection unavailable. Nothing was changed.";
    const detail = result?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail[0]?.msg || fallback;
    return fallback;
  }

  function field(labelText, { name, value = "", type = "text", maxLength = 64 } = {}) {
    const label = element("label", "manage-field");
    const labelCopy = element("span", "manage-field__label", labelText);
    const input = element("input", "manage-field__input");
    input.name = name;
    input.type = type;
    input.value = value;
    input.maxLength = maxLength;
    input.required = true;
    input.autocomplete = "off";
    label.append(labelCopy, input);
    return label;
  }

  function setFormStatus(form, message, { error = false } = {}) {
    const status = form.querySelector("[data-form-status]");
    if (!status) return;
    status.textContent = message;
    status.classList.toggle("is-error", error);
  }

  function renderCreate() {
    const target = prepareSurface();
    if (!target) return;
    const content = element("div", "run-library-content manage-flow");
    content.id = "run-library";
    content.dataset.runLibrary = "";
    content.setAttribute("aria-labelledby", "run-library-heading");
    content.append(pageHeading("New run", "Create a beer run", "A short dedicated flow keeps creation separate from browsing."));

    const form = element("form", "manage-form ticket-surface");
    form.append(field("Run name", { name: "name" }));
    const choices = element("fieldset", "manage-choice-group");
    choices.append(element("legend", "", "Visibility"));
    [["private", "Private", "Invite only", true], ["public", "Public", "Anyone can view", false]].forEach(([value, title, copy, checked]) => {
      const label = element("label", "manage-choice");
      const radio = element("input");
      radio.type = "radio";
      radio.name = "visibility";
      radio.value = value;
      radio.checked = checked;
      const text = element("span", "manage-choice__copy");
      text.append(element("strong", "", title), element("small", "", copy));
      label.append(radio, text);
      choices.append(label);
    });
    form.append(choices);
    const status = element("p", "manage-form__status");
    status.dataset.formStatus = "";
    status.setAttribute("role", "status");
    form.append(status);
    const actions = element("div", "manage-actions");
    const cancel = action("Cancel", "button button--secondary");
    cancel.dataset.libraryBack = "";
    const submit = action("Create run", "button button--primary");
    submit.type = "submit";
    actions.append(cancel, submit);
    form.append(actions);
    content.append(form);
    target.replaceChildren(content);

    cancel.addEventListener("click", () => openView("library"));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = form.elements.name.value.trim();
      if (!/^[A-Za-z0-9 _-]{3,64}$/.test(name)) {
        setFormStatus(form, "Use 3–64 letters, numbers, spaces, underscores, or hyphens.", { error: true });
        form.elements.name.focus();
        return;
      }
      submit.disabled = true;
      submit.setAttribute("aria-busy", "true");
      setFormStatus(form, "Creating your run…");
      const result = await api.createBeerRun({ name, is_public: form.elements.visibility.value === "public" }, auth.getAccessToken());
      if (!active || view !== "create") return;
      if (!result.ok) {
        submit.disabled = false;
        submit.removeAttribute("aria-busy");
        setFormStatus(form, apiMessage(result, "This run could not be created. Try again."), { error: true });
        return;
      }
      await onSelectRun?.(result.data, { persist: true });
      onShowRun?.();
    });
    form.elements.name.focus({ preventScroll: true });
  }

  function memberRow(member) {
    const row = element("li", "manage-member");
    const mark = element("span", "manage-member__mark", runInitial(member.username));
    mark.setAttribute("aria-hidden", "true");
    const copy = element("span", "manage-member__copy");
    copy.append(element("strong", "", member.username), element("small", "", roleLabel(member.role)));
    row.append(mark, copy);
    if (member.role === "owner") row.append(element("span", "status-tag", "Owner"));
    return row;
  }

  async function renderManage() {
    const target = prepareSurface();
    if (!target) return;
    const run = getSnapshot().currentRun;
    const isOwner = run?.current_user_role === "owner";
    const request = ++managementGeneration;
    const content = element("div", "run-library-content manage-flow");
    content.id = "run-library";
    content.dataset.runLibrary = "";
    content.setAttribute("aria-labelledby", "run-library-heading");
    content.append(pageHeading(isOwner ? "Owner controls" : "Run membership", `Manage ${run?.name || "run"}`, "Members, invitations, identity, and permanent actions are separated by purpose."));
    const loading = element("section", "manage-section manage-section--loading");
    loading.append(element("h2", "", "Members"), element("p", "", "Loading the run roster…"));
    content.append(loading);
    target.replaceChildren(content);

    const result = await api.fetchBeerRunMembers(run.id, auth.getAccessToken());
    if (request !== managementGeneration || !active || view !== "manage") return;
    if (!result.ok && [401, 403, 404].includes(result.status)) {
      announcement = "Your access to that run changed. The run library has been refreshed.";
      await onIdentityChange?.();
      if (request !== managementGeneration || !active) return;
      view = "library";
      history.replaceState(null, "", "#runs");
      await load();
      return;
    }
    loading.remove();
    const roster = element("section", "manage-section");
    const head = element("div", "manage-section__heading");
    const headCopy = element("div");
    const members = result.ok && Array.isArray(result.data) ? result.data : [];
    headCopy.append(element("h2", "", "Members"), element("p", "", result.ok
      ? `${members.length} ${members.length === 1 ? "person" : "people"}`
      : apiMessage(result, "The roster could not be loaded.")));
    head.append(headCopy);
    roster.append(head);
    if (members.length) {
      const list = element("ul", "manage-members");
      members.forEach((member) => list.append(memberRow(member)));
      roster.append(list);
    }
    content.append(roster);

    let inviteStatus = null;
    if (isOwner) {
      const inviteSection = element("section", "manage-invite");
      const inviteHeading = element("div", "manage-invite__heading");
      inviteHeading.append(
        element("h2", "", "Invite people"),
        element("p", "", "Create one reusable link for this run, then copy or share it."),
      );
      inviteStatus = element("p", "manage-form__status");
      inviteStatus.dataset.inviteStatus = "";
      inviteStatus.setAttribute("role", "status");
      inviteStatus.setAttribute("aria-live", "polite");
      const share = action("Get invite link", "button button--primary");
      share.dataset.manageInvite = "";
      inviteSection.append(inviteHeading, share, inviteStatus);
      content.append(inviteSection);

      const tools = element("section", "manage-tools");
      const rename = action("Rename run", "button button--secondary");
      rename.dataset.manageRename = "";
      tools.append(rename);
      content.append(tools);

      const renameForm = element("form", "manage-form manage-form--rename");
      renameForm.hidden = true;
      renameForm.append(field("New run name", { name: "name", value: run.name }));
      const renameStatus = element("p", "manage-form__status");
      renameStatus.dataset.formStatus = "";
      renameStatus.setAttribute("role", "status");
      const renameActions = element("div", "manage-actions");
      const dismissRename = action("Cancel", "button button--secondary");
      const saveRename = action("Save name", "button button--primary");
      saveRename.type = "submit";
      renameActions.append(dismissRename, saveRename);
      renameForm.append(renameStatus, renameActions);
      content.append(renameForm);
      rename.addEventListener("click", () => { renameForm.hidden = false; renameForm.elements.name.focus(); });
      dismissRename.addEventListener("click", () => { renameForm.hidden = true; });
      renameForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = renameForm.elements.name.value.trim();
        saveRename.disabled = true;
        const update = await api.updateBeerRun(run.id, { name }, auth.getAccessToken());
        saveRename.disabled = false;
        if (!update.ok) {
          setFormStatus(renameForm, apiMessage(update, "The run could not be renamed."), { error: true });
          return;
        }
        await onSelectRun?.(update.data, { persist: true });
        renderManage();
      });

    }

    const danger = element("section", "manage-danger");
    danger.append(element("p", "eyebrow", "Danger area"), element("h2", "", isOwner ? "Permanent run controls" : "Leave this run"));
    danger.append(element("p", "", isOwner
      ? "Deleting permanently removes this run and its history for everyone."
      : "Your past pours stay in the run after you leave."));
    const dangerActions = element("div", "manage-actions");
    if (!isOwner) {
      const leave = action("Leave run", "button button--danger");
      leave.dataset.manageLeave = "";
      dangerActions.append(leave);
    } else {
      const remove = action("Delete run", "button button--danger");
      remove.dataset.manageDelete = "";
      dangerActions.append(remove);
    }
    danger.append(dangerActions);
    content.append(danger);

    const back = action("Back to run library", "button button--secondary manage-back");
    back.dataset.libraryBack = "";
    content.append(back);

    content.querySelector("[data-manage-invite]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const inviteRequest = ++managementGeneration;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      inviteStatus.textContent = "Preparing the invite link...";
      inviteStatus.classList.remove("is-error");
      const invite = await api.createBeerRunInvite(run.id, auth.getAccessToken());
      if (inviteRequest !== managementGeneration || !active || view !== "manage"
        || Number(getSnapshot().currentRun?.id) !== Number(run.id)) return;
      button.removeAttribute("aria-busy");
      if (!invite.ok) {
        if ([401, 403, 404].includes(invite.status)) {
          announcement = invite.status === 403
            ? "You are no longer the owner of this run."
            : "Your run access changed while preparing the invite.";
          await onIdentityChange?.();
          if (inviteRequest !== managementGeneration || !active) return;
          view = "library";
          history.replaceState(null, "", "#runs");
          await load();
          return;
        }
        button.disabled = false;
        inviteStatus.textContent = apiMessage(invite, "An invite link could not be created.");
        inviteStatus.classList.add("is-error");
        inviteStatus.setAttribute("role", "alert");
        return;
      }
      const url = buildInviteShareUrl(invite.data, run.id);
      if (!url) {
        button.disabled = false;
        inviteStatus.textContent = "BeerRun returned an invalid invite link. Try again.";
        inviteStatus.classList.add("is-error");
        inviteStatus.setAttribute("role", "alert");
        return;
      }
      button.hidden = true;
      const inviteSection = button.closest(".manage-invite");
      const linkPanel = element("div", "manage-invite__link");
      const linkInput = element("input", "manage-invite__url");
      linkInput.type = "text";
      linkInput.readOnly = true;
      linkInput.value = url;
      linkInput.setAttribute("aria-label", `Invite link for ${run.name}`);
      linkInput.addEventListener("focus", () => linkInput.select());
      const inviteActions = element("div", "manage-actions");
      const copy = action("Copy link", "button button--primary");
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(url);
          inviteStatus.textContent = "Invite link copied.";
        } catch {
          linkInput.focus();
          linkInput.select();
          inviteStatus.textContent = "Copy the selected link from the field above.";
        }
      });
      inviteActions.append(copy);
      if (typeof navigator.share === "function") {
        const shareLink = action("Share invite", "button button--secondary");
        shareLink.addEventListener("click", async () => {
          try {
            await navigator.share({
              title: `Join ${run.name} on BeerRun`,
              text: `Join ${run.name} on BeerRun.`,
              url,
            });
            inviteStatus.textContent = "Invite shared.";
          } catch (error) {
            if (error?.name !== "AbortError") inviteStatus.textContent = "Sharing did not open. You can copy the link instead.";
          }
        });
        inviteActions.append(shareLink);
      }
      linkPanel.append(linkInput, inviteActions);
      inviteSection.insertBefore(linkPanel, inviteStatus);
      inviteStatus.textContent = "Invite ready to share.";
      inviteStatus.classList.remove("is-error");
      inviteStatus.setAttribute("role", "status");
    });
    back.addEventListener("click", () => openView("library"));
    content.querySelector("[data-manage-leave]")?.addEventListener("click", async (event) => {
      const trigger = event.currentTarget;
      const target = mutationTarget(run);
      const outcome = await showConfirmation({
        root,
        trigger,
        focusFallback: () => root.querySelector("[data-manage-leave], #run-library-heading, main"),
        eyebrow: "Membership change",
        title: `Leave ${run.name}?`,
        message: run.is_public
          ? "You will leave this run, but you can still view it publicly. Your recorded pours will stay."
          : "You will lose access to this private run, but your recorded pours will stay.",
        subjectRows: [["Run", run.name], ["History", "Your recorded pours stay"]],
        safeLabel: "Stay in this run",
        confirmLabel: "Leave run",
        pendingLabel: "Leaving run...",
        onConfirm: async () => {
          if (!targetIsCurrent(target)) return { ok: false, dismiss: true, reason: "identity-changed" };
          const leave = await api.leaveBeerRun(target.runId, target.token);
          if (!leave.ok) return {
            ...leave,
            dismiss: [401, 403, 404].includes(leave.status),
            reason: leave.status === 401 ? "session-rejected" : [403, 404].includes(leave.status) ? "stale-target" : undefined,
            message: [401, 403, 404].includes(leave.status)
              ? "Your membership changed before this action completed. Refresh and review the run again."
              : apiMessage(leave, "You could not leave this run. Nothing was changed."),
          };
          return { ...leave, ok: true, committed: true };
        },
      });
      await reconcileRunMutation(outcome, target, {
        successMessage: `You left ${run.name}.`,
        staleMessage: "Your membership changed. The run library has been refreshed.",
      });
    });
    content.querySelector("[data-manage-delete]")?.addEventListener("click", async (event) => {
      const trigger = event.currentTarget;
      const target = mutationTarget(run);
      const outcome = await showConfirmation({
        root,
        trigger,
        focusFallback: () => root.querySelector("[data-manage-delete], #run-library-heading, main"),
        title: "Delete this run?",
        message: `Deleting “${run.name}” permanently removes its entries, uploaded photos, memberships, invite link, and history. This cannot be undone.`,
        subjectRows: [["Run", run.name], ["Scope", "Everyone in this run"]],
        safeLabel: "Keep this run",
        confirmLabel: "Delete permanently",
        pendingLabel: "Deleting run...",
        exactText: run.name,
        exactTextLabel: "Type the exact run name to confirm",
        onConfirm: async () => {
          if (!targetIsCurrent(target)) return { ok: false, dismiss: true, reason: "identity-changed" };
          const removed = await api.deleteBeerRun(target.runId, target.token);
          if (!removed.ok) return {
            ...removed,
            dismiss: [401, 403, 404].includes(removed.status),
            reason: removed.status === 401 ? "session-rejected" : [403, 404].includes(removed.status) ? "stale-target" : undefined,
            message: [401, 403, 404].includes(removed.status)
              ? "This run or your owner access changed. Refresh before trying again."
              : apiMessage(removed, "This run could not be deleted. Nothing was changed."),
          };
          return { ...removed, ok: true, committed: true };
        },
      });
      await reconcileRunMutation(outcome, target, {
        successMessage: `${run.name} was deleted.`,
        staleMessage: "This run or your owner access changed. The run library has been refreshed.",
      });
    });
  }

  function renderHandoff(kind) {
    if (kind === "manage") void renderManage();
    else renderCreate();
  }

  function openView(nextView, { push = true } = {}) {
    if (nextView === "manage" && !["owner", "member"].includes(getSnapshot().currentRun?.current_user_role)) {
      view = "library";
      announcement = "Only run members can open management controls.";
      if (push) history.pushState(null, "", "#runs");
      else history.replaceState(null, "", "#runs");
      renderLibrary();
      return;
    }
    if (nextView === "create" && !identity) {
      view = "library";
      announcement = "Sign in before creating a run.";
      if (push) history.pushState(null, "", "#runs");
      else history.replaceState(null, "", "#runs");
      renderLibrary();
      return;
    }
    view = nextView;
    if (push) history.pushState(null, "", `#${nextView === "library" ? "runs" : nextView}`);
    if (view === "library") {
      renderLibrary();
      main()?.querySelector("#run-library-heading")?.focus?.({ preventScroll: true });
      void load();
    } else {
      renderHandoff(view);
    }
  }

  return {
    show(nextView = "library") {
      if (!active) lastFocused = document.activeElement;
      active = true;
      view = nextView;
      if (view === "library") void load();
      else {
        identity = getSnapshot().currentUser;
        openView(view, { push: false });
      }
      main()?.focus({ preventScroll: true });
    },
    hide({ restoreFocus = false } = {}) {
      if (!active) return;
      active = false;
      abortWork();
      main()?.classList.remove("main-content--runs");
      if (restoreFocus) (lastFocused || root.querySelector("[data-run-switcher]"))?.focus?.({ preventScroll: true });
    },
    refresh() {
      if (active && view === "library") return load();
      return null;
    },
    refreshSwitcher() {
      if (switcherDialog) return loadQuickSwitcher();
      return null;
    },
    isActive: () => active,
    isSwitcherOpen: () => Boolean(switcherDialog),
    getView: () => view,
    openSwitcher,
    closeSwitcher,
    openView,
  };
}

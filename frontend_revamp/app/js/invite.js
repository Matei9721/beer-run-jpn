export const PENDING_INVITE_KEY = "beer_run_pending_invite";
export const PENDING_INVITE_INTENT_KEY = "beer_run_pending_invite_intent";

const INVITE_CODE_PATTERN = /^[A-Za-z0-9_-]{43}$/;

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(label, className = "button button--secondary") {
  const node = element("button", className, label);
  node.type = "button";
  return node;
}

function inviteHeading(title, copy) {
  const heading = element("header", "page-heading invite-heading");
  heading.append(
    element("p", "eyebrow", "Admission pass"),
    element("h1", "", title),
    element("p", "page-heading__copy", copy),
  );
  return heading;
}

function inviteTicket({ name = "", loading = false, unavailable = false } = {}) {
  const ticket = element("section", "ticket-surface invite-ticket");
  const mark = element("span", "invite-ticket__mark");
  mark.setAttribute("aria-hidden", "true");
  mark.append(element("span", "icon icon--beer"));
  ticket.append(mark);
  if (loading) {
    ticket.setAttribute("aria-label", "Loading invitation");
    ticket.append(
      element("span", "skeleton-line skeleton-line--eyebrow"),
      element("span", "skeleton-line skeleton-line--heading"),
      element("span", "skeleton-line skeleton-line--wide"),
    );
    return ticket;
  }
  ticket.append(element("p", "eyebrow", unavailable ? "Invite unavailable" : "BeerRun invite"));
  const title = element("h2", "invite-ticket__run", unavailable ? "This invitation cannot be opened" : name);
  ticket.append(title);
  ticket.append(element(
    "p",
    "invite-ticket__copy",
    unavailable
      ? "The link may be invalid or no longer available. No private run details were shared."
      : "Only the run name is shown before you join. Member and activity details stay private.",
  ));
  return ticket;
}

function invitationUrl(locationLike = location) {
  return new URL(locationLike.href);
}

export function validInvitePreview(data) {
  return Boolean(
    data
    && Number.isInteger(Number(data.beer_run_id))
    && Number(data.beer_run_id) > 0
    && typeof data.beer_run_name === "string"
    && data.beer_run_name.length > 0,
  );
}

export function validAcceptedRun(data, previewId) {
  return Boolean(
    data
    && Number(data.id) === Number(previewId)
    && typeof data.name === "string"
    && data.name.length > 0
    && typeof data.is_public === "boolean"
    && typeof data.created_at === "string"
    && data.created_at.length > 0
    && Number.isInteger(data.member_count)
    && data.member_count > 0
    && ["member", "owner"].includes(data.current_user_role),
  );
}

export function validateOwnerInviteResponse(data, runId, locationLike = location) {
  if (!data || Number(data.beer_run_id) !== Number(runId)
    || !INVITE_CODE_PATTERN.test(data.code)
    || typeof data.invite_url !== "string"
    || typeof data.beer_run_name !== "string" || !data.beer_run_name
    || typeof data.created_at !== "string" || !data.created_at) return null;
  try {
    const url = new URL(data.invite_url, locationLike.origin);
    const values = url.searchParams.getAll("invite");
    if (url.origin !== locationLike.origin || url.pathname !== "/" || url.hash
      || values.length !== 1 || values[0] !== data.code
      || [...url.searchParams.keys()].some((key) => key !== "invite")) return null;
    return { data, url: url.href };
  } catch {
    return null;
  }
}

export function buildInviteShareUrl(invite, runId, locationLike = location) {
  const validated = validateOwnerInviteResponse(invite, runId, locationLike);
  if (!validated) return null;
  const provided = new URL(validated.url);
  if (locationLike.pathname !== "/revamp-preview") return provided.href;
  const preview = new URL(locationLike.href);
  preview.search = "";
  preview.searchParams.set("invite", validated.data.code);
  preview.hash = "invite";
  return preview.href;
}

export function createInviteController({
  root = document,
  api,
  auth,
  storage = sessionStorage,
  getSnapshot,
  onSelectRun = null,
  onShowRun = null,
  onDismiss = null,
}) {
  let active = false;
  let code = "";
  let preview = null;
  let knownMembership = null;
  let generation = 0;
  let requestController = null;
  let accepting = false;

  const main = () => root.querySelector("main");

  function codesFromLocation() {
    const url = invitationUrl();
    return url.searchParams.getAll("invite");
  }

  function routeHasInvite() {
    return codesFromLocation().length > 0 || location.hash === "#invite";
  }

  function resolveCode() {
    const values = codesFromLocation();
    if (values.length) {
      if (values.length !== 1 || !INVITE_CODE_PATTERN.test(values[0])) return "";
      storage.setItem(PENDING_INVITE_KEY, values[0]);
      return values[0];
    }
    return storage.getItem(PENDING_INVITE_KEY) || "";
  }

  function clearPending() {
    storage.removeItem(PENDING_INVITE_KEY);
    storage.removeItem(PENDING_INVITE_INTENT_KEY);
    const url = invitationUrl();
    url.searchParams.delete("invite");
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function prepareSurface() {
    const target = main();
    target?.classList.remove("main-content--map", "main-content--runs");
    target?.classList.add("main-content--invite");
    document.body.classList.remove("map-view");
    return target;
  }

  function contentShell(title, copy) {
    const content = element("div", "invite-content");
    content.dataset.inviteView = "";
    content.append(inviteHeading(title, copy));
    return content;
  }

  function renderLoading() {
    const target = prepareSurface();
    if (!target) return;
    const content = contentShell("Opening your invitation", "Checking the destination without revealing its private activity.");
    content.append(inviteTicket({ loading: true }));
    target.replaceChildren(content);
  }

  function bindDismiss(target) {
    target.querySelectorAll("[data-invite-dismiss]").forEach((control) => {
      control.addEventListener("click", () => dismiss());
    });
  }

  function renderUnavailable({ offline = false } = {}) {
    const target = prepareSurface();
    if (!target) return;
    const content = contentShell(
      offline ? "Invitation not loaded" : "Invitation unavailable",
      offline ? "BeerRun could not check this link yet." : "Use a new invite link from the run owner.",
    );
    if (offline) {
      const notice = element("section", "invite-notice");
      notice.setAttribute("role", "alert");
      notice.append(element("h2", "", "Connection paused"), element("p", "", "Check your connection, then try the invitation again."));
      const actions = element("div", "invite-actions");
      const retry = button("Try again", "button button--primary");
      retry.dataset.inviteRetry = "";
      const dismissButton = button("Not now", "button button--secondary");
      dismissButton.dataset.inviteDismiss = "";
      actions.append(retry, dismissButton);
      notice.append(actions);
      content.append(notice);
      target.replaceChildren(content);
      retry.addEventListener("click", () => void load());
      bindDismiss(target);
      return;
    }
    content.append(inviteTicket({ unavailable: true }));
    const dismissButton = button("Back to BeerRun", "button button--secondary invite-dismiss");
    dismissButton.dataset.inviteDismiss = "";
    content.append(dismissButton);
    target.replaceChildren(content);
    bindDismiss(target);
  }

  function openAuth(mode) {
    storage.setItem(PENDING_INVITE_INTENT_KEY, code);
    active = false;
    requestController?.abort();
    requestController = null;
    root.dispatchEvent(new CustomEvent("beer-run:open-auth", {
      detail: { mode, returnTo: "#invite" },
    }));
  }

  function setStatus(message, { error = false } = {}) {
    const status = root.querySelector("[data-invite-status]");
    if (!status) return;
    status.textContent = message;
    status.classList.toggle("is-error", error);
    status.setAttribute("role", error ? "alert" : "status");
    status.setAttribute("aria-live", error ? "assertive" : "polite");
  }

  function setActionPending(pending) {
    root.querySelectorAll("[data-invite-action]").forEach((control) => {
      control.disabled = pending;
      control.setAttribute("aria-busy", String(pending));
    });
  }

  async function openKnownRun(run) {
    if (!run || accepting) return;
    accepting = true;
    setActionPending(true);
    if (!await finishJoinedRun(run, { alreadyMember: true })) {
      accepting = false;
      setActionPending(false);
      setStatus("BeerRun could not confirm this membership. Refresh and try again.", { error: true });
    }
  }

  async function finishJoinedRun(run, { alreadyMember = false } = {}) {
    if (!validAcceptedRun(run, preview?.beer_run_id)) return false;
    setStatus(alreadyMember ? `Opening ${run.name}...` : `Joined ${run.name}. Opening the run...`);
    clearPending();
    await onSelectRun?.(run, { persist: true });
    if (!active) return true;
    active = false;
    accepting = false;
    main()?.classList.remove("main-content--invite");
    onShowRun?.({ joinedRun: run, alreadyMember });
    main()?.focus({ preventScroll: true });
    return true;
  }

  async function reconcileAcceptedMembership(user, token, context) {
    const result = await api.fetchMyBeerRuns(token, requestController?.signal || null);
    if (!active || user?.id !== getSnapshot()?.currentUser?.id
      || token !== auth.getAccessToken() || context !== getSnapshot()?.contextGeneration) return null;
    if (!result.ok || !Array.isArray(result.data)) return null;
    return result.data.find((run) => validAcceptedRun(run, preview?.beer_run_id)) || null;
  }

  async function accept() {
    if (accepting) return;
    if (!auth.getAccessToken()) {
      openAuth("login");
      return;
    }
    accepting = true;
    storage.removeItem(PENDING_INVITE_INTENT_KEY);
    setActionPending(true);
    setStatus("Joining this run...");
    const request = ++generation;
    requestController?.abort();
    requestController = new AbortController();
    const user = getSnapshot()?.currentUser || null;
    const token = auth.getAccessToken();
    const context = getSnapshot()?.contextGeneration;
    const result = await api.acceptInvite(code, token, requestController.signal);
    if (request !== generation || result.aborted || !active
      || user?.id !== getSnapshot()?.currentUser?.id
      || token !== auth.getAccessToken() || context !== getSnapshot()?.contextGeneration) return;
    requestController = null;
    if (!result.ok) {
      if (result.status === 401) {
        accepting = false;
        setActionPending(false);
        openAuth("login");
        return;
      }
      if (result.status === 404) {
        accepting = false;
        setActionPending(false);
        clearPending();
        renderUnavailable();
        return;
      }
      if (!result.network) {
        accepting = false;
        setActionPending(false);
        setStatus("BeerRun could not complete the join. Try again.", { error: true });
        return;
      }
    }
    if (result.ok && await finishJoinedRun(result.data)) return;
    const reconciled = (result.network || result.ok)
      ? await reconcileAcceptedMembership(user, token, context)
      : null;
    if (reconciled && await finishJoinedRun(reconciled)) return;
    accepting = false;
    setActionPending(false);
    setStatus("BeerRun could not confirm the join. Try again.", { error: true });
  }

  function renderPreview() {
    const target = prepareSurface();
    if (!target || !preview) return;
    const identity = getSnapshot()?.currentUser || null;
    const isMember = Boolean(knownMembership);
    const content = contentShell("You have been invited", "Review the run name, then choose whether to join.");
    const ticket = inviteTicket({ name: preview.beer_run_name });
    const state = element("div", "invite-ticket__state");
    state.append(element("span", "status-tag", isMember ? "Already joined" : "Invitation ready"));
    if (identity) state.append(element("span", "invite-signed-in", `Signed in as ${identity.username}`));
    ticket.append(state);
    const actions = element("div", "invite-actions");
    if (!identity) {
      const login = button("Log in to join", "button button--primary");
      login.dataset.inviteAction = "";
      login.addEventListener("click", () => openAuth("login"));
      const signup = button("Create an account", "button button--secondary");
      signup.dataset.inviteAction = "";
      signup.addEventListener("click", () => openAuth("signup"));
      actions.append(login, signup);
    } else if (isMember) {
      const open = button("Open this run", "button button--primary");
      open.dataset.inviteAction = "";
      open.addEventListener("click", () => void openKnownRun(knownMembership));
      actions.append(open);
    } else {
      const join = button("Join this run", "button button--primary");
      join.dataset.inviteAction = "";
      join.addEventListener("click", () => void accept());
      actions.append(join);
    }
    const dismissButton = button("Not now", "button button--quiet invite-not-now");
    dismissButton.dataset.inviteDismiss = "";
    const status = element("p", "invite-status");
    status.dataset.inviteStatus = "";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    content.append(ticket, actions, dismissButton, status);
    target.replaceChildren(content);
    bindDismiss(target);
    if (identity && !isMember && storage.getItem(PENDING_INVITE_INTENT_KEY) === code) void accept();
  }

  async function load() {
    active = true;
    accepting = false;
    code = resolveCode();
    preview = null;
    knownMembership = null;
    const request = ++generation;
    requestController?.abort();
    requestController = null;
    if (!INVITE_CODE_PATTERN.test(code)) {
      renderUnavailable();
      return;
    }
    renderLoading();
    requestController = new AbortController();
    const signal = requestController.signal;
    const result = await api.previewInvite(code, signal);
    if (request !== generation || result.aborted || !active) return;
    if (!result.ok || !validInvitePreview(result.data)) {
      requestController = null;
      if (!result.network) clearPending();
      renderUnavailable({ offline: Boolean(result.network) });
      return;
    }
    preview = result.data;
    const identity = getSnapshot()?.currentUser || null;
    const token = auth.getAccessToken();
    if (identity && token) {
      const memberships = await api.fetchMyBeerRuns(token, signal);
      if (request !== generation || memberships.aborted || !active) return;
      if (request !== generation || auth.getAccessToken() !== token || getSnapshot()?.currentUser?.id !== identity.id) return;
      if (memberships.ok && Array.isArray(memberships.data)) {
        knownMembership = memberships.data.find((run) => Number(run.id) === Number(preview.beer_run_id)) || null;
      }
    }
    requestController = null;
    renderPreview();
  }

  function dismiss({ notify = true } = {}) {
    if (!active && !routeHasInvite()) return;
    active = false;
    accepting = false;
    generation += 1;
    requestController?.abort();
    requestController = null;
    clearPending();
    main()?.classList.remove("main-content--invite");
    if (notify) {
      onDismiss?.();
      main()?.focus({ preventScroll: true });
    }
  }

  function hide() {
    if (!active) return;
    active = false;
    accepting = false;
    generation += 1;
    requestController?.abort();
    requestController = null;
    main()?.classList.remove("main-content--invite");
  }

  function cancelAuthContinuation() {
    storage.removeItem(PENDING_INVITE_INTENT_KEY);
  }

  function reset() {
    clearPending();
    hide();
  }

  return {
    cancelAuthContinuation,
    dismiss,
    hasInviteRoute: routeHasInvite,
    hide,
    isActive: () => active,
    reset,
    show: () => load(),
  };
}

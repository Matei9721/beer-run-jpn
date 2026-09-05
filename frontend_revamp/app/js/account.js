import { showConfirmation } from "./confirmation.js?v=revamp-047-10";

const ACCOUNT_CONFIRMATION = "DELETE MY ACCOUNT";

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function action(label, className = "button button--secondary") {
  const button = element("button", className, label);
  button.type = "button";
  return button;
}

function count(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function plural(value, singular, pluralLabel = `${singular}s`) {
  return `${value} ${value === 1 ? singular : pluralLabel}`;
}

function runList(summary) {
  return Array.isArray(summary?.owned_runs)
    ? summary.owned_runs.filter((run) => Number.isInteger(Number(run?.id)) && typeof run?.name === "string")
    : [];
}

function initialFor(username) {
  return Array.from(String(username || "?").trim())[0]?.toLocaleUpperCase() || "?";
}

function deletionMessage(result) {
  const detail = result?.data?.detail;
  if (result?.network) return "Connection unavailable. Nothing was deleted. Check your connection and try again.";
  if (result?.status === 401 && detail === "Incorrect password") return "That password is incorrect. Your account and data are unchanged.";
  if (result?.status === 422) return "Check your password and type the confirmation exactly as shown.";
  if (typeof detail === "string" && detail.includes("recovery is pending")) {
    return "BeerRun could not restore one or more photos. Your account was not deleted. Contact the server operator before trying again.";
  }
  if (typeof detail === "string" && detail) return `${detail}. Your account and data are unchanged.`;
  return "Your account could not be deleted. Nothing was removed. Try again.";
}

export function createAccountController({
  root = document,
  api,
  auth,
  theme,
  getSnapshot,
  onSignOut,
  onDeleteAccount,
  onManageOwnedRun,
  onSessionRejected,
  onOpenGuide,
}) {
  let active = false;
  let summary = null;
  let loading = false;
  let error = "";
  let notice = "";
  let generation = 0;
  let requestController = null;
  let lastFocused = null;

  const main = () => root.querySelector("main");

  function pageHeading() {
    const heading = element("header", "page-heading account-heading");
    heading.append(
      element("p", "eyebrow", "Your account"),
      element("h1", "", "Account and data"),
      element("p", "page-heading__copy", "Review your activity, choose a theme, or sign out."),
    );
    heading.querySelector("h1").id = "account-heading";
    return heading;
  }

  function summarySection(identity) {
    const section = element("section", "account-summary");
    section.setAttribute("aria-labelledby", "account-identity-heading");
    const header = element("div", "account-summary__header");
    const mark = element("span", "account-avatar", initialFor(identity.username));
    mark.setAttribute("aria-hidden", "true");
    const copy = element("div", "account-summary__identity");
    const name = element("h2", "", identity.username);
    name.id = "account-identity-heading";
    copy.append(name);
    const signOut = action("Sign out", "button button--secondary account-sign-out");
    signOut.dataset.accountSignOut = "";
    header.append(mark, copy, signOut);
    section.append(header);

    const stats = element("dl", "account-stats");
    const entries = summary ? count(summary.entry_count) : null;
    const memberships = summary ? count(summary.membership_count) : null;
    const owned = summary ? runList(summary).length : null;
    [
      [entries, entries === null ? "entries" : entries === 1 ? "entry" : "entries"],
      [memberships, memberships === null ? "memberships" : memberships === 1 ? "membership" : "memberships"],
      [owned, owned === null ? "owned runs" : owned === 1 ? "owned run" : "owned runs"],
    ].forEach(([value, label]) => {
      const stat = element("div", "account-stat");
      stat.append(
        element("dt", "", label),
        element("dd", "", loading || value === null ? "..." : String(value)),
      );
      stats.append(stat);
    });
    section.append(stats);
    return section;
  }

  function appearanceSection() {
    const section = element("section", "account-section account-appearance");
    const fieldset = element("fieldset", "account-appearance__fieldset");
    const legend = element("legend", "", "Appearance");
    const help = element("p", "account-section__copy", "Choose how BeerRun looks on this device.");
    help.id = "account-appearance-help";
    fieldset.setAttribute("aria-describedby", help.id);
    fieldset.append(legend, help);
    const options = element("div", "account-theme-options");
    [
      ["system", "System", "Match your device"],
      ["light", "Light", "Keep light mode on"],
      ["dark", "Dark", "Keep dark mode on"],
    ].forEach(([value, label, description]) => {
      const choice = element("label", "account-theme-choice");
      const radio = element("input");
      radio.type = "radio";
      radio.name = "account-theme";
      radio.value = value;
      radio.checked = theme.getPreference() === value;
      const choiceCopy = element("span", "account-theme-choice__copy");
      choiceCopy.append(element("strong", "", label), element("small", "", description));
      choice.append(radio, choiceCopy, element("span", "account-theme-choice__check", "Selected"));
      options.append(choice);
    });
    fieldset.append(options);
    section.append(fieldset);
    return section;
  }

  function blockerList(ownedRuns) {
    const list = element("ul", "account-owned-runs");
    ownedRuns.forEach((run) => {
      const item = element("li", "account-owned-run");
      const copy = element("span", "account-owned-run__copy");
      copy.append(element("strong", "", run.name), element("small", "", "Owner"));
      const manage = action("Manage run", "button button--secondary");
      manage.dataset.accountManageRun = String(run.id);
      item.append(copy, manage);
      list.append(item);
    });
    return list;
  }

  function guideSection() {
    const section = element("section", "account-section account-guide");
    const copy = element("div", "account-guide__copy");
    copy.append(
      element("h2", "", "Quick guide"),
      element("p", "account-section__copy", "See how to log drinks, check the standings, and find each stop on the map."),
    );
    const open = action("Open quick guide", "button button--secondary");
    open.dataset.accountOpenGuide = "";
    section.append(copy, open);
    return section;
  }

  function dangerSection() {
    const section = element("section", "account-danger");
    section.setAttribute("aria-labelledby", "account-delete-heading");
    const heading = element("h2", "", "Delete account");
    heading.id = "account-delete-heading";
    section.append(heading);

    if (loading) {
      section.append(element("p", "account-section__copy", "Checking whether this account can be deleted..."));
      const review = action("Loading account summary...", "button button--danger");
      review.disabled = true;
      section.append(review);
      return section;
    }
    if (error || !summary) {
      section.append(element("p", "account-section__copy", "We couldn't load the details needed to delete this account."));
      const retry = action("Retry account summary", "button button--secondary");
      retry.dataset.accountRetry = "";
      section.append(retry);
      return section;
    }

    const ownedRuns = runList(summary);
    if (ownedRuns.length) {
      const ownedRunReference = ownedRuns.length === 1 ? "it" : "them";
      section.append(element(
        "p",
        "account-section__copy",
        `You own ${plural(ownedRuns.length, "run")}. Delete ${ownedRunReference} before deleting your account. Run ownership can't be transferred yet.`,
      ));
      section.append(blockerList(ownedRuns));
      return section;
    }

    const entries = count(summary.entry_count);
    const memberships = count(summary.membership_count);
    section.append(element(
      "p",
      "account-section__copy",
      `Deleting your account permanently removes ${plural(memberships, "membership")}, your accepted Terms records, ${plural(entries, "entry", "entries")}, and any photos attached to your entries. It won't affect anyone else's data.`,
    ));
    const review = action("Review account deletion", "button button--danger");
    review.dataset.accountDelete = "";
    section.append(review);
    return section;
  }

  function render() {
    if (!active) return;
    const identity = getSnapshot().currentUser;
    if (!identity) {
      onSessionRejected?.();
      return;
    }
    const content = element("div", "account-content");
    content.dataset.accountView = "";
    content.setAttribute("aria-labelledby", "account-heading");
    content.append(pageHeading(), summarySection(identity), appearanceSection(), guideSection());
    const feedback = element("p", `account-feedback${error ? " is-error" : ""}`, error || notice);
    feedback.dataset.accountFeedback = "";
    feedback.setAttribute("role", error ? "alert" : "status");
    feedback.setAttribute("aria-live", error ? "assertive" : "polite");
    content.append(feedback, dangerSection());
    main()?.replaceChildren(content);
    bind();
  }

  function bind() {
    root.querySelector("[data-account-sign-out]")?.addEventListener("click", () => void onSignOut?.());
    root.querySelectorAll('input[name="account-theme"]').forEach((radio) => {
      radio.addEventListener("change", (event) => {
        if (event.target.checked) theme.setPreference(event.target.value);
      });
    });
    root.querySelector("[data-account-retry]")?.addEventListener("click", () => void loadSummary());
    root.querySelector("[data-account-open-guide]")?.addEventListener("click", () => onOpenGuide?.());
    root.querySelector("[data-account-delete]")?.addEventListener("click", (event) => void reviewDeletion(event.currentTarget));
    root.querySelectorAll("[data-account-manage-run]").forEach((button) => {
      button.addEventListener("click", async () => {
        const run = runList(summary).find((candidate) => Number(candidate.id) === Number(button.dataset.accountManageRun));
        if (!run) return;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        const result = await onManageOwnedRun?.(run);
        if (!active) return;
        if (result?.sessionRejected) {
          onSessionRejected?.();
          return;
        }
        if (!result?.ok) {
          error = result?.message || "That run could not be opened. Refresh the account summary and try again.";
          render();
        }
      });
    });
  }

  async function loadSummary() {
    if (!active) return;
    const request = ++generation;
    requestController?.abort();
    requestController = new AbortController();
    loading = true;
    error = "";
    notice = "";
    render();
    const result = await api.fetchAccountDeletionSummary(auth.getAccessToken(), requestController.signal);
    if (!active || request !== generation || result.aborted) return;
    requestController = null;
    loading = false;
    if (result.status === 401) {
      onSessionRejected?.();
      return;
    }
    if (!result.ok) {
      summary = null;
      error = result.network
        ? "Connection unavailable. Your account summary could not be loaded."
        : "Your account summary could not be loaded. Try again.";
      render();
      return;
    }
    summary = result.data;
    render();
  }

  async function reviewDeletion(trigger) {
    if (!summary || runList(summary).length) return;
    const entries = count(summary.entry_count);
    const memberships = count(summary.membership_count);
    const target = {
      userId: getSnapshot().currentUser?.id,
      token: auth.getAccessToken(),
    };
    const outcome = await showConfirmation({
      root,
      trigger,
      focusFallback: () => root.querySelector("[data-account-delete], [data-account-manage-run], main"),
      title: "Delete your account?",
      message: `Your profile, ${plural(memberships, "membership")}, accepted Terms records, ${plural(entries, "entry", "entries")}, and photos uploaded for your entries will be deleted. Other users' accounts, entries, photos, and runs will not be deleted.`,
      subjectRows: [
        ["Account", getSnapshot().currentUser?.username],
        ["Memberships", String(count(summary.membership_count))],
      ],
      safeLabel: "Keep my account",
      confirmLabel: "Delete my account",
      pendingLabel: "Deleting account...",
      password: true,
      exactText: ACCOUNT_CONFIRMATION,
      exactTextLabel: "Type DELETE MY ACCOUNT to confirm",
      onConfirm: async ({ password, confirmation }) => {
        if (getSnapshot().currentUser?.id !== target.userId || auth.getAccessToken() !== target.token) {
          return { ok: false, dismiss: true, reason: "identity-changed" };
        }
        const result = await onDeleteAccount?.({ ...target, password, confirmation });
        if (result?.ok) return result;
        if (result?.reason === "identity-changed") return { ...result, dismiss: true };
        if (result?.status === 401 && result?.data?.detail !== "Incorrect password") {
          return { ...result, dismiss: true, reason: "session-rejected" };
        }
        const blockers = result?.status === 409 ? runList(result.data?.detail) : [];
        if (blockers.length) {
          summary = { ...summary, owned_runs: blockers };
          notice = "Ownership changed. Resolve the listed runs before trying again.";
          render();
          return { ok: false, dismiss: true, reason: "ownership-blocked" };
        }
        return { ok: false, message: deletionMessage(result), focus: result?.status === 422 ? "confirmation" : "password" };
      },
    });
    if (outcome?.result?.reason === "session-rejected") {
      onSessionRejected?.();
      return;
    }
    if (outcome?.result?.reason === "identity-changed") return;
    if (outcome?.result?.reason === "ownership-blocked" && active) {
      requestAnimationFrame(() => root.querySelector("[data-account-manage-run]")?.focus({ preventScroll: true }));
    }
  }

  function hide({ restoreFocus = false } = {}) {
    if (!active) return;
    active = false;
    generation += 1;
    requestController?.abort();
    requestController = null;
    main()?.classList.remove("main-content--account");
    if (restoreFocus && lastFocused?.isConnected) lastFocused.focus({ preventScroll: true });
    lastFocused = null;
  }

  return {
    show() {
      const identity = getSnapshot().currentUser;
      if (!identity) {
        onSessionRejected?.();
        return;
      }
      if (!active) lastFocused = document.activeElement;
      active = true;
      summary = null;
      loading = true;
      error = "";
      notice = "";
      main()?.classList.add("main-content--account");
      render();
      void loadSummary();
      main()?.focus({ preventScroll: true });
    },
    hide,
    isActive: () => active,
    completeSuccess() {
      summary = null;
      loading = false;
      error = "";
      notice = "";
      hide();
    },
  };
}

let activeDialog = null;
let confirmationId = 0;

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function action(label, className) {
  const button = element("button", className, label);
  button.type = "button";
  return button;
}

function addField(form, { id, name, label, type = "text", autocomplete = "off", help = "" }) {
  const wrapper = element("label", "confirmation-field");
  const labelNode = element("span", "confirmation-field__label", label);
  const input = element("input", "confirmation-field__input");
  input.id = id;
  input.name = name;
  input.type = type;
  input.autocomplete = autocomplete;
  input.required = true;
  input.spellcheck = false;
  wrapper.append(labelNode, input);
  if (help) {
    const helpNode = element("span", "confirmation-field__help", help);
    helpNode.id = `${id}-help`;
    input.setAttribute("aria-describedby", helpNode.id);
    wrapper.append(helpNode);
  }
  form.append(wrapper);
  return input;
}

function addSubject(panel, rows) {
  if (!Array.isArray(rows) || !rows.length) return;
  const subject = element("dl", "confirmation-subject");
  rows.forEach(([label, value]) => {
    if (!value) return;
    const row = element("div", "confirmation-subject__row");
    row.append(element("dt", "", label), element("dd", "", String(value)));
    subject.append(row);
  });
  if (subject.children.length) panel.append(subject);
}

export function showConfirmation({
  root = document,
  trigger = document.activeElement,
  focusFallback = null,
  eyebrow = "Permanent action",
  title,
  message,
  subjectRows = [],
  safeLabel = "Cancel",
  confirmLabel,
  pendingLabel = "Working...",
  exactText = "",
  exactTextLabel = "Type the exact text to confirm",
  password = false,
  onConfirm,
} = {}) {
  if (activeDialog) return Promise.resolve({ confirmed: false, busy: true });

  return new Promise((resolve) => {
    const id = ++confirmationId;
    const dialog = element("dialog", "confirmation-dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", `confirmation-title-${id}`);
    dialog.setAttribute("aria-describedby", `confirmation-message-${id}`);
    const panel = element("form", "confirmation-panel");
    panel.noValidate = true;

    const header = element("div", "confirmation-header");
    const heading = element("div", "confirmation-heading");
    heading.append(element("p", "eyebrow", eyebrow));
    const titleNode = element("h2", "", title || "Confirm this action");
    titleNode.id = `confirmation-title-${id}`;
    heading.append(titleNode);
    const close = action("×", "confirmation-close");
    close.setAttribute("aria-label", safeLabel);
    header.append(heading, close);
    panel.append(header);

    addSubject(panel, subjectRows);
    const copy = element("p", "confirmation-message", message || "This action cannot be undone.");
    copy.id = `confirmation-message-${id}`;
    panel.append(copy);

    let passwordInput = null;
    let exactInput = null;
    if (password) {
      passwordInput = addField(panel, {
        id: `confirmation-password-${id}`,
        name: "password",
        label: "Current password",
        type: "password",
        autocomplete: "current-password",
      });
    }
    if (exactText) {
      exactInput = addField(panel, {
        id: `confirmation-exact-${id}`,
        name: "confirmation",
        label: exactTextLabel,
        help: exactText,
      });
    }

    const status = element("p", "confirmation-status");
    status.setAttribute("role", "alert");
    status.setAttribute("aria-live", "assertive");
    panel.append(status);

    const actions = element("div", "confirmation-actions");
    const cancel = action(safeLabel, "button button--secondary");
    const confirm = action(confirmLabel || "Confirm", "button button--danger confirmation-submit");
    confirm.type = "submit";
    confirm.dataset.idleLabel = confirm.textContent;
    actions.append(cancel, confirm);
    panel.append(actions);
    dialog.append(panel);

    let pending = false;
    activeDialog = dialog;

    const canSubmit = () => (
      !pending
      && (!passwordInput || Boolean(passwordInput.value))
      && (!exactInput || exactInput.value === exactText)
    );
    const updateSubmit = () => { confirm.disabled = !canSubmit(); };
    const restore = () => {
      const target = trigger?.isConnected ? trigger : focusFallback?.();
      target?.focus?.({ preventScroll: true });
    };
    const finish = (result) => {
      if (dialog.open && typeof dialog.close === "function") dialog.close();
      dialog.remove();
      activeDialog = null;
      requestAnimationFrame(restore);
      resolve(result);
    };
    const setPending = (value) => {
      pending = value;
      panel.setAttribute("aria-busy", String(value));
      panel.querySelectorAll("button, input").forEach((control) => { control.disabled = value; });
      confirm.textContent = value ? pendingLabel : confirm.dataset.idleLabel;
      if (!value) updateSubmit();
    };

    close.addEventListener("click", () => { if (!pending) finish({ confirmed: false }); });
    cancel.addEventListener("click", () => { if (!pending) finish({ confirmed: false }); });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      if (!pending) finish({ confirmed: false });
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog && !pending) finish({ confirmed: false });
    });
    passwordInput?.addEventListener("input", () => { status.textContent = ""; updateSubmit(); });
    exactInput?.addEventListener("input", () => { status.textContent = ""; updateSubmit(); });
    panel.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!canSubmit()) return;
      status.textContent = "";
      setPending(true);
      let result;
      try {
        result = await onConfirm?.({
          password: passwordInput?.value || "",
          confirmation: exactInput?.value || "",
        });
      } catch {
        result = { ok: false, message: "BeerRun could not complete this action. Nothing was changed." };
      }
      if (result?.ok) {
        finish({ confirmed: true, result });
        return;
      }
      if (result?.dismiss) {
        finish({ confirmed: false, result });
        return;
      }
      setPending(false);
      status.textContent = result?.message || "BeerRun could not complete this action. Nothing was changed.";
      const retryTarget = result?.focus === "confirmation" ? exactInput : passwordInput || exactInput || cancel;
      retryTarget?.focus?.({ preventScroll: true });
    });

    root.body.append(dialog);
    updateSubmit();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    (passwordInput || exactInput || cancel).focus({ preventScroll: true });
  });
}

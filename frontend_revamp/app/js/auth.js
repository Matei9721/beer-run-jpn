export const ACCESS_TOKEN_KEY = "access_token";

const USERNAME_PATTERN = /^[A-Za-z0-9_-]+$/;
const PASSWORD_LETTER_PATTERN = /[A-Za-z]/;
const PASSWORD_DIGIT_PATTERN = /[0-9]/;

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

function field({ id, name, label, type = "text", autocomplete, help = "" }) {
  const wrapper = element("div", "auth-field");
  const labelNode = element("label", "auth-field__label", label);
  labelNode.htmlFor = id;
  const input = element("input", "auth-field__input");
  input.id = id;
  input.name = name;
  input.type = type;
  input.autocomplete = autocomplete;
  input.required = true;
  input.spellcheck = false;
  input.setAttribute("aria-describedby", `${id}-help ${id}-error`);
  wrapper.append(labelNode, input);
  const helpNode = element("p", "auth-field__help", help);
  helpNode.id = `${id}-help`;
  if (!help) helpNode.hidden = true;
  const error = element("p", "auth-field__error");
  error.id = `${id}-error`;
  error.dataset.errorFor = name;
  wrapper.append(helpNode, error);
  return wrapper;
}

function heading(mode) {
  const header = element("header", "auth-heading");
  header.append(
    element("p", "eyebrow", mode === "signup" ? "Join the run" : "Welcome back"),
    element("h1", "", mode === "signup" ? "Create your account" : "Log in to BeerRun"),
    element(
      "p",
      "auth-heading__copy",
      mode === "signup"
        ? "Age acknowledgement and the private signup code stay explicit."
        : "Continue logging drinks and switch between your runs.",
    ),
  );
  header.querySelector("h1").id = "auth-view-title";
  return header;
}

function brand({ desktop = false } = {}) {
  const identity = element("span", `auth-brand${desktop ? " auth-brand--desktop" : ""}`);
  const mark = element("span", "product-mark", "B");
  mark.setAttribute("aria-hidden", "true");
  identity.append(mark, element("span", "product-wordmark", "BeerRun"));
  return identity;
}

function validateLogin(form) {
  const errors = {};
  if (!form.elements.username.value.trim()) errors.username = "Enter your username.";
  if (!form.elements.password.value) errors.password = "Enter your password.";
  return errors;
}

function validateSignup(form) {
  const errors = {};
  const username = form.elements.username.value.trim();
  const password = form.elements.password.value;
  if (!username) errors.username = "Enter a username.";
  else if (username.length < 3 || username.length > 32) errors.username = "Use 3-32 characters.";
  else if (!USERNAME_PATTERN.test(username)) errors.username = "Use only letters, numbers, underscores, or hyphens.";
  if (!form.elements.signup_code.value.trim()) errors.signup_code = "Enter your signup code.";
  if (!password) errors.password = "Create a password.";
  else if (password.length < 8) errors.password = "Use at least 8 characters.";
  else if (!PASSWORD_LETTER_PATTERN.test(password) || !PASSWORD_DIGIT_PATTERN.test(password)) {
    errors.password = "Include at least one letter and one number.";
  }
  if (!form.elements.confirm_password.value) errors.confirm_password = "Confirm your password.";
  else if (password !== form.elements.confirm_password.value) errors.confirm_password = "Passwords do not match.";
  if (!form.elements.terms_agreed.checked) errors.terms_agreed = "Confirm your age and agreement to continue.";
  return errors;
}

function loginForm() {
  const form = element("form", "auth-form");
  form.dataset.authForm = "login";
  form.noValidate = true;
  form.autocomplete = "on";
  form.append(
    field({ id: "login-username", name: "username", label: "Username", autocomplete: "username" }),
    field({ id: "login-password", name: "password", label: "Password", type: "password", autocomplete: "current-password" }),
  );
  const status = element("p", "auth-form__message");
  status.dataset.authMessage = "";
  status.setAttribute("role", "alert");
  status.setAttribute("aria-live", "assertive");
  const submit = button("Log in", "button button--primary auth-submit");
  submit.type = "submit";
  form.append(status, submit);
  return form;
}

function signupForm() {
  const form = element("form", "auth-form auth-form--signup");
  form.dataset.authForm = "signup";
  form.noValidate = true;
  form.autocomplete = "on";
  const identityFields = element("div", "auth-form__grid");
  identityFields.append(
    field({
      id: "signup-username",
      name: "username",
      label: "Username",
      autocomplete: "username",
      help: "3-32 letters, numbers, underscores, or hyphens.",
    }),
    field({ id: "signup-code", name: "signup_code", label: "Signup code", autocomplete: "off" }),
  );
  const passwordFields = element("div", "auth-form__grid");
  passwordFields.append(
    field({
      id: "signup-password",
      name: "password",
      label: "Password",
      type: "password",
      autocomplete: "new-password",
      help: "At least 8 characters, including a letter and a number.",
    }),
    field({
      id: "signup-confirm-password",
      name: "confirm_password",
      label: "Confirm password",
      type: "password",
      autocomplete: "new-password",
    }),
  );
  const legal = element("div", "auth-legal");
  const legalLabel = element("label", "auth-legal__choice");
  const checkbox = element("input");
  checkbox.type = "checkbox";
  checkbox.name = "terms_agreed";
  checkbox.required = true;
  checkbox.disabled = true;
  checkbox.setAttribute("aria-describedby", "signup-terms-status signup-terms-error");
  const copy = element("span");
  copy.append(document.createTextNode("I am at least 18 and agree to the "));
  const terms = element("a", "auth-legal__link", "Terms of Service");
  terms.href = "/terms";
  terms.dataset.termsLink = "";
  const privacy = element("a", "auth-legal__link", "Privacy Notice");
  privacy.href = "/privacy";
  privacy.dataset.privacyLink = "";
  copy.append(terms, document.createTextNode(" and "), privacy, document.createTextNode("."));
  legalLabel.append(checkbox, copy);
  const legalStatus = element("p", "auth-legal__status", "Loading the current Terms...");
  legalStatus.id = "signup-terms-status";
  legalStatus.dataset.legalStatus = "";
  legalStatus.setAttribute("role", "status");
  const legalError = element("p", "auth-field__error");
  legalError.id = "signup-terms-error";
  legalError.dataset.errorFor = "terms_agreed";
  legal.append(legalLabel, legalStatus, legalError);
  const status = element("p", "auth-form__message");
  status.dataset.authMessage = "";
  status.setAttribute("role", "alert");
  status.setAttribute("aria-live", "assertive");
  const submit = button("Create account", "button button--primary auth-submit");
  submit.type = "submit";
  form.append(identityFields, passwordFields, legal, status, submit);
  return form;
}

function renderView(mode) {
  const view = element("section", "auth-view");
  view.dataset.authView = "";
  view.dataset.authMode = mode;
  view.setAttribute("aria-labelledby", "auth-view-title");
  const mobileHeader = element("header", "auth-mobile-header");
  const close = button("Close", "button button--quiet auth-close");
  close.dataset.authClose = "";
  mobileHeader.append(brand(), close);
  const stage = element("div", "auth-view__stage");
  const panel = element("div", "auth-panel");
  panel.append(brand({ desktop: true }), heading(mode), mode === "signup" ? signupForm() : loginForm());
  const alternate = element("div", "auth-alternate");
  alternate.append(element("span", "", mode === "signup" ? "Already have an account?" : "New here?"));
  const switcher = button(mode === "signup" ? "Log in instead" : "Create an account", "button button--quiet auth-alternate__action");
  switcher.dataset.authModeSwitch = mode === "signup" ? "login" : "signup";
  alternate.append(switcher);
  panel.append(alternate);
  stage.append(panel);
  view.append(mobileHeader, stage);
  return view;
}

function clearErrors(form) {
  form.querySelectorAll("[data-error-for]").forEach((node) => { node.textContent = ""; });
  form.querySelectorAll("input").forEach((input) => input.removeAttribute("aria-invalid"));
  const message = form.querySelector("[data-auth-message]");
  if (message) message.textContent = "";
}

function showErrors(form, errors) {
  clearErrors(form);
  Object.entries(errors).forEach(([name, message]) => {
    const input = form.elements[name];
    const error = form.querySelector(`[data-error-for="${name}"]`);
    if (input) input.setAttribute("aria-invalid", "true");
    if (error) error.textContent = message;
  });
  const first = Object.keys(errors)[0];
  form.elements[first]?.focus({ preventScroll: true });
  form.elements[first]?.scrollIntoView({ block: "center", behavior: "smooth" });
}

function setMessage(form, message) {
  const target = form.querySelector("[data-auth-message]");
  if (target) target.textContent = message;
}

function setPending(form, pending, label = "") {
  form.setAttribute("aria-busy", String(pending));
  form.querySelectorAll("input, button").forEach((control) => { control.disabled = pending; });
  const submit = form.querySelector("button[type='submit']");
  if (submit) submit.textContent = pending ? label : submit.dataset.idleLabel;
}

function signupServerError(result) {
  if (result.status === 409) return { username: "That username already exists." };
  if (result.status === 403) return { signup_code: "That signup code is not valid." };
  if (result.status === 422) {
    const detail = typeof result.data?.detail === "string" ? result.data.detail : "Check your account details and try again.";
    if (detail.toLowerCase().includes("username")) return { username: detail };
    if (detail.toLowerCase().includes("password")) return { password: detail };
    if (detail.toLowerCase().includes("terms")) return { terms_agreed: detail };
    return { form: detail };
  }
  return { form: result.network ? "BeerRun could not be reached. Check your connection and try again." : "BeerRun could not create the account. Try again." };
}

export function createAuthState({ storage = localStorage } = {}) {
  return {
    getAccessToken: () => storage.getItem(ACCESS_TOKEN_KEY),
    setAccessToken(token) { storage.setItem(ACCESS_TOKEN_KEY, token); },
    removeAccessToken() { storage.removeItem(ACCESS_TOKEN_KEY); },
  };
}

export function createAuthController({
  root = document,
  api,
  auth,
  onAuthenticated = null,
  onClose = null,
}) {
  let mode = "login";
  let returnTo = "#run";
  let legalMetadata = null;
  let legalGeneration = 0;
  let requestController = null;
  let active = false;

  const main = () => root.querySelector("main");

  async function loadLegalMetadata() {
    const view = root.querySelector("[data-auth-view][data-auth-mode='signup']");
    if (!view) return;
    const generation = ++legalGeneration;
    const status = view.querySelector("[data-legal-status]");
    const checkbox = view.querySelector("input[name='terms_agreed']");
    if (status) status.textContent = "Loading the current Terms...";
    if (checkbox) checkbox.disabled = true;
    const result = await api.fetchLegalMetadata();
    if (generation !== legalGeneration || !active || mode !== "signup") return;
    if (!result.ok || !result.data?.terms_version) {
      legalMetadata = null;
      if (status) status.textContent = result.network
        ? "The current Terms could not be loaded. Check your connection and try again."
        : "The current Terms are unavailable. Try again in a moment.";
      return;
    }
    legalMetadata = result.data;
    const terms = view.querySelector("[data-terms-link]");
    const privacy = view.querySelector("[data-privacy-link]");
    if (terms) terms.href = legalMetadata.terms_url;
    if (privacy) privacy.href = legalMetadata.privacy_url;
    if (checkbox) checkbox.disabled = false;
    if (status) status.textContent = "Current legal terms loaded.";
  }

  function focusFirst() {
    requestAnimationFrame(() => root.querySelector("[data-auth-form] input:not(:disabled)")?.focus({ preventScroll: true }));
  }

  function bind() {
    const view = root.querySelector("[data-auth-view]");
    const form = view?.querySelector("[data-auth-form]");
    const submit = form?.querySelector("button[type='submit']");
    if (submit) submit.dataset.idleLabel = submit.textContent;
    view?.querySelector("[data-auth-close]")?.addEventListener("click", () => close());
    view?.querySelector("[data-auth-mode-switch]")?.addEventListener("click", (event) => {
      const nextMode = event.currentTarget.dataset.authModeSwitch;
      history.pushState(null, "", `#${nextMode}`);
      show(nextMode, { returnTo });
    });
    form?.addEventListener("input", (event) => {
      event.target.removeAttribute("aria-invalid");
      const error = form.querySelector(`[data-error-for="${event.target.name}"]`);
      if (error) error.textContent = "";
      setMessage(form, "");
    });
    form?.addEventListener("submit", (event) => {
      event.preventDefault();
      if (mode === "signup") void submitSignup(form);
      else void submitLogin(form);
    });
    focusFirst();
  }

  async function finishAuthentication(token) {
    if (typeof token !== "string" || !token) {
      return { ok: false, message: "BeerRun returned an invalid session. Try again." };
    }
    auth.setAccessToken(token);
    const destination = returnTo;
    active = false;
    root.querySelector("[data-revamp-preview]")?.classList.remove("is-auth-view");
    document.body.classList.remove("auth-view-open");
    const user = await onAuthenticated?.({ returnTo: destination }) || null;
    root.dispatchEvent(new CustomEvent("beer-run:authenticated", { detail: { user, returnTo: destination } }));
    return { ok: true };
  }

  async function submitLogin(form) {
    const errors = validateLogin(form);
    if (Object.keys(errors).length) {
      showErrors(form, errors);
      return;
    }
    clearErrors(form);
    requestController?.abort();
    requestController = new AbortController();
    setPending(form, true, "Logging in...");
    const result = await api.login(form.elements.username.value.trim(), form.elements.password.value, requestController.signal);
    if (!active || result.aborted) return;
    if (!result.ok) {
      setPending(form, false);
      if (result.status === 401) setMessage(form, "The username or password is incorrect.");
      else setMessage(form, result.network ? "BeerRun could not be reached. Check your connection and try again." : "BeerRun could not log you in. Try again.");
      return;
    }
    const authenticated = await finishAuthentication(result.data?.access_token);
    if (!authenticated.ok && active) {
      setPending(form, false);
      setMessage(form, authenticated.message);
    }
  }

  async function submitSignup(form) {
    const errors = validateSignup(form);
    if (!legalMetadata) errors.form = "The current Terms must load before an account can be created.";
    if (Object.keys(errors).length) {
      const fieldErrors = Object.fromEntries(Object.entries(errors).filter(([name]) => name !== "form"));
      if (Object.keys(fieldErrors).length) showErrors(form, fieldErrors);
      if (errors.form) setMessage(form, errors.form);
      if (!legalMetadata) void loadLegalMetadata();
      return;
    }
    clearErrors(form);
    requestController?.abort();
    requestController = new AbortController();
    setPending(form, true, "Creating account...");
    const result = await api.signup({
      username: form.elements.username.value.trim(),
      password: form.elements.password.value,
      signup_code: form.elements.signup_code.value,
      terms_agreed: true,
      terms_version: legalMetadata.terms_version,
    }, requestController.signal);
    if (!active || result.aborted) return;
    if (!result.ok) {
      setPending(form, false);
      const errorsFromServer = signupServerError(result);
      const formMessage = errorsFromServer.form;
      delete errorsFromServer.form;
      if (Object.keys(errorsFromServer).length) showErrors(form, errorsFromServer);
      if (formMessage) setMessage(form, formMessage);
      if (result.status === 422 && String(result.data?.detail || "").toLowerCase().includes("current terms")) {
        legalMetadata = null;
        void loadLegalMetadata();
      }
      return;
    }
    const authenticated = await finishAuthentication(result.data?.access_token);
    if (!authenticated.ok && active) {
      setPending(form, false);
      setMessage(form, authenticated.message);
    }
  }

  function show(nextMode = "login", options = {}) {
    mode = nextMode === "signup" ? "signup" : "login";
    if (options.returnTo && !["#login", "#signup"].includes(options.returnTo)) returnTo = options.returnTo;
    else if (!active) returnTo = "#run";
    active = true;
    requestController?.abort();
    requestController = null;
    legalGeneration += 1;
    root.querySelector("[data-revamp-preview]")?.classList.add("is-auth-view");
    document.body.classList.remove("map-view", "run-switcher-open");
    document.body.classList.add("auth-view-open");
    main()?.classList.remove("main-content--map", "main-content--runs");
    main()?.replaceChildren(renderView(mode));
    bind();
    if (options.message) setMessage(root.querySelector("[data-auth-form]"), options.message);
    if (mode === "signup") void loadLegalMetadata();
  }

  function close({ notify = true } = {}) {
    if (!active) return;
    active = false;
    legalGeneration += 1;
    requestController?.abort();
    requestController = null;
    root.querySelector("[data-revamp-preview]")?.classList.remove("is-auth-view");
    document.body.classList.remove("auth-view-open");
    if (notify) onClose?.({ returnTo });
  }

  async function validateStoredSession() {
    const token = auth.getAccessToken();
    if (!token) return { status: "none" };
    const result = await api.fetchCurrentUser(token);
    if (result.ok) return { status: "valid", user: result.data };
    if (result.status === 401) {
      auth.removeAccessToken();
      return { status: "stale" };
    }
    return { status: "unavailable", network: Boolean(result.network) };
  }

  root.addEventListener("beer-run:open-auth", (event) => {
    const nextMode = event.detail?.mode === "signup" ? "signup" : "login";
    const destination = event.detail?.returnTo || location.hash || "#run";
    history.pushState(null, "", `#${nextMode}`);
    show(nextMode, { returnTo: destination });
  });

  return { show, close, validateStoredSession, isActive: () => active };
}

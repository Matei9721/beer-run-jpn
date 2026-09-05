const DOCUMENTS = Object.freeze({
  terms: { url: "/terms", label: "Terms" },
  privacy: { url: "/privacy", label: "Privacy" },
});

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function brand() {
  const identity = element("span", "product-identity legal-view__brand");
  identity.append(
    element("span", "product-mark", "B"),
    element("span", "product-wordmark", "BeerRun"),
  );
  identity.firstElementChild.setAttribute("aria-hidden", "true");
  return identity;
}

function documentTabs(current) {
  const nav = element("nav", "legal-view__tabs");
  nav.setAttribute("aria-label", "Legal documents");
  Object.entries(DOCUMENTS).forEach(([name, document]) => {
    const link = element("a", "legal-view__tab", document.label);
    link.href = `#${name}`;
    link.dataset.legalDocument = name;
    if (name === current) link.setAttribute("aria-current", "page");
    nav.append(link);
  });
  return nav;
}

function sectionNavigation(article) {
  const links = [...article.querySelectorAll("section[id] h2")].map((heading) => {
    const link = element("button", "legal-sections__link", heading.textContent.trim());
    link.type = "button";
    link.dataset.sectionTarget = `legal-${heading.parentElement.id}`;
    heading.parentElement.id = `legal-${heading.parentElement.id}`;
    return link;
  });
  const nav = element("nav", "legal-sections");
  nav.setAttribute("aria-label", "On this page");
  nav.append(element("p", "legal-sections__label", "On this page"), ...links);
  return nav;
}

function prepareArticle(source, current) {
  const article = source.querySelector(".legal-document");
  if (!article) return null;
  article.querySelectorAll("a[href='/terms'], a[href='/privacy']").forEach((link) => {
    const name = link.getAttribute("href").slice(1);
    link.href = `#${name}`;
    link.dataset.legalDocument = name;
  });
  article.className = "legal-copy";
  article.dataset.legalCopy = current;
  return article;
}

function loadingView(current, returnTo) {
  const view = element("section", "legal-view");
  view.dataset.legalView = current;
  const header = element("header", "legal-view__header");
  const backLabel = returnTo === "#signup" ? "Back to signup" : returnTo === "#login" ? "Back to login" : "Back to BeerRun";
  const back = element("a", "button button--quiet legal-view__back", backLabel);
  back.href = returnTo;
  back.dataset.legalBack = "";
  header.append(brand(), documentTabs(current), back);
  const status = element("div", "legal-loading");
  status.setAttribute("role", "status");
  status.append(
    element("span", "skeleton-line skeleton-line--eyebrow"),
    element("span", "skeleton-line skeleton-line--heading"),
    element("span", "skeleton-line skeleton-line--copy"),
  );
  view.append(header, status);
  return view;
}

export function createLegalController({ root = document, fetchImpl = fetch } = {}) {
  let active = false;
  let returnTo = "#run";
  let generation = 0;
  let requestController = null;

  const main = () => root.querySelector("main");

  async function show(name, options = {}) {
    const current = DOCUMENTS[name] ? name : "terms";
    if (options.returnTo && !["#terms", "#privacy"].includes(options.returnTo)) returnTo = options.returnTo;
    else if (!active) returnTo = "#run";
    active = true;
    const request = ++generation;
    requestController?.abort();
    requestController = new AbortController();
    root.querySelector("[data-revamp-preview]")?.classList.add("is-legal-view");
    document.body.classList.remove("map-view", "auth-view-open", "run-switcher-open");
    document.body.classList.add("legal-view-open");
    main()?.classList.remove("main-content--map", "main-content--runs", "main-content--account");
    main()?.classList.add("main-content--legal");
    main()?.replaceChildren(loadingView(current, returnTo));

    try {
      const response = await fetchImpl(DOCUMENTS[current].url, { signal: requestController.signal });
      if (!response.ok) throw new Error(`Legal document returned ${response.status}`);
      const source = new DOMParser().parseFromString(await response.text(), "text/html");
      if (!active || request !== generation) return;
      const article = prepareArticle(source, current);
      if (!article) throw new Error("Legal document content is missing");
      const layout = element("div", "legal-layout");
      layout.append(sectionNavigation(article), article);
      layout.querySelector(".legal-sections")?.addEventListener("click", (event) => {
        const link = event.target.closest(".legal-sections__link");
        if (!link) return;
        const section = layout.querySelector(`#${link.dataset.sectionTarget}`);
        if (!section) return;
        event.preventDefault();
        section.querySelector("h2")?.setAttribute("tabindex", "-1");
        section.scrollIntoView({ behavior: "smooth", block: "start" });
        section.querySelector("h2")?.focus({ preventScroll: true });
      });
      root.querySelector("[data-legal-view]")?.replaceChildren(
        root.querySelector(".legal-view__header"),
        layout,
      );
      article.querySelector("h1")?.setAttribute("tabindex", "-1");
      article.querySelector("h1")?.focus({ preventScroll: true });
    } catch (error) {
      if (error.name === "AbortError" || !active || request !== generation) return;
      const panel = element("div", "legal-error");
      panel.setAttribute("role", "alert");
      panel.append(
        element("h1", "", "This document could not be loaded"),
        element("p", "", "Check your connection and try again. Your current app state has not changed."),
      );
      const retry = element("button", "button button--secondary", "Try again");
      retry.type = "button";
      retry.addEventListener("click", () => show(current));
      panel.append(retry);
      root.querySelector("[data-legal-view]")?.replaceChildren(
        root.querySelector(".legal-view__header"),
        panel,
      );
    }
  }

  function hide() {
    if (!active) return;
    active = false;
    generation += 1;
    requestController?.abort();
    requestController = null;
    document.body.classList.remove("legal-view-open");
    root.querySelector("[data-revamp-preview]")?.classList.remove("is-legal-view");
    main()?.classList.remove("main-content--legal");
  }

  return { show, hide, isActive: () => active, getReturnTo: () => returnTo };
}

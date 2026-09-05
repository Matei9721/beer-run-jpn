const ONBOARDING_STORAGE_KEY = "beer_run_revamp_onboarding_complete";
const ONBOARDING_VERSION = "route-stamp-v5";

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function setStoredCompletion(storage) {
  try {
    storage.setItem(ONBOARDING_STORAGE_KEY, ONBOARDING_VERSION);
  } catch {
    // The guide remains dismissible when browser storage is unavailable.
  }
}

function hasStoredCompletion(storage) {
  try {
    return storage.getItem(ONBOARDING_STORAGE_KEY) === ONBOARDING_VERSION;
  } catch {
    return false;
  }
}

export function createOnboardingController({ root = document, storage = localStorage, onComplete = null } = {}) {
  let dialog = null;
  let lastFocused = null;
  let currentStep = 0;

  function finish({ destination = "" } = {}) {
    if (!dialog) return;
    const closing = dialog;
    dialog = null;
    setStoredCompletion(storage);
    document.body.classList.remove("onboarding-open");
    if (closing.open && typeof closing.close === "function") closing.close();
    closing.remove();
    if (lastFocused?.isConnected) lastFocused.focus({ preventScroll: true });
    lastFocused = null;
    if (destination && typeof onComplete === "function") onComplete({ destination });
  }

  function buildDialog() {
    const modal = element("dialog", "onboarding-dialog");
    modal.setAttribute("aria-labelledby", "onboarding-heading-1");
    modal.setAttribute("aria-describedby", "onboarding-copy-1");

    const surface = element("section", "onboarding-surface");
    const top = element("header", "onboarding-topbar");
    const brand = element("span", "onboarding-brand");
    const mark = element("span", "product-mark", "B");
    mark.setAttribute("aria-hidden", "true");
    brand.append(mark, element("span", "product-wordmark", "BeerRun"));
    const skip = element("button", "button button--quiet onboarding-skip", "Skip for now");
    skip.type = "button";
    skip.dataset.onboardingSkip = "";
    const topActions = element("span", "onboarding-topbar__actions");
    topActions.append(skip);
    top.append(brand, topActions);

    const slides = element("div", "onboarding-slides");
    const slideContent = [
      {
        chapter: "Start here",
        eyebrow: "Welcome to BeerRun",
        title: "Keep the score. Keep the story.",
        copy: "Log drinks as the night unfolds, see who’s ahead, and remember the places and photos worth keeping.",
      },
      {
        chapter: "Log a drink",
        eyebrow: "While it’s in your hand",
        title: "Log it while it’s still in your hand.",
        copy: "Record the drink, volume, strength, and brand. Capture your location when you save it; add a photo when the evidence deserves one.",
      },
      {
        chapter: "Follow the night",
        eyebrow: "After every round",
        title: "Watch the night turn into a story.",
        copy: "See who’s leading, open anyone’s drink history, then jump from a pour to the place it happened.",
      },
    ];

    const stage = element("div", "onboarding-stage");
    const chapterNav = element("nav", "onboarding-chapters");
    chapterNav.setAttribute("aria-label", "Guide chapters");
    const chapterIntro = element("div", "onboarding-chapters__intro");
    chapterIntro.append(
      element("span", "eyebrow", "The short version"),
      element("strong", "", "Three things to know"),
    );
    chapterNav.append(chapterIntro);
    slideContent.forEach((content, index) => {
      const chapter = element("button", "onboarding-chapter");
      chapter.type = "button";
      chapter.dataset.onboardingStep = String(index);
      chapter.setAttribute("aria-controls", `onboarding-slide-${index + 1}`);
      chapter.append(
        element("span", "onboarding-chapter__number", `0${index + 1}`),
        element("span", "onboarding-chapter__label", content.chapter),
      );
      if (index === 0) {
        chapter.classList.add("is-active");
        chapter.setAttribute("aria-current", "step");
      }
      chapterNav.append(chapter);
    });

    slideContent.forEach((content, index) => {
      const slide = element("article", `onboarding-slide onboarding-slide--${index + 1}`);
      slide.id = `onboarding-slide-${index + 1}`;
      slide.dataset.onboardingSlide = String(index);
      slide.hidden = index !== 0;
      const copy = element("div", "onboarding-copy");
      copy.append(element("p", "eyebrow", content.eyebrow));
      const title = element("h1", "", content.title);
      title.id = `onboarding-heading-${index + 1}`;
      title.tabIndex = -1;
      const description = element("p", "onboarding-copy__body", content.copy);
      description.id = `onboarding-copy-${index + 1}`;
      copy.append(title, description);
      slide.append(copy);
      slides.append(slide);
    });
    stage.append(chapterNav, slides);

    const footer = element("footer", "onboarding-footer");
    const back = element("button", "button button--secondary onboarding-back", "Back");
    back.type = "button";
    back.dataset.onboardingBack = "";
    back.hidden = true;
    const stepCount = element("span", "onboarding-step-count", "1 of 3");
    stepCount.setAttribute("aria-live", "polite");
    const next = element("button", "button button--primary onboarding-next", "Next");
    next.type = "button";
    next.dataset.onboardingNext = "";
    footer.append(back, stepCount, next);

    function renderStep(index, { focus = true } = {}) {
      currentStep = Math.max(0, Math.min(slideContent.length - 1, index));
      modal.querySelectorAll("[data-onboarding-slide]").forEach((slide) => {
        slide.hidden = Number(slide.dataset.onboardingSlide) !== currentStep;
      });
      modal.querySelectorAll("[data-onboarding-step]").forEach((dot) => {
        const selected = Number(dot.dataset.onboardingStep) === currentStep;
        dot.classList.toggle("is-active", selected);
        if (selected) dot.setAttribute("aria-current", "step");
        else dot.removeAttribute("aria-current");
      });
      stepCount.textContent = `${currentStep + 1} of 3`;
      back.hidden = currentStep === 0;
      next.textContent = currentStep < slideContent.length - 1 ? "Next" : "Go to the run";
      const activeTitle = modal.querySelector(`#onboarding-heading-${currentStep + 1}`);
      modal.setAttribute("aria-labelledby", activeTitle.id);
      modal.setAttribute("aria-describedby", `onboarding-copy-${currentStep + 1}`);
      if (focus) activeTitle.focus({ preventScroll: true });
    }

    surface.append(top, stage, footer);
    modal.append(surface);
    modal.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish();
    });
    modal.addEventListener("click", (event) => {
      if (event.target.closest("[data-onboarding-skip]")) finish();
      const step = event.target.closest("[data-onboarding-step]");
      if (step) renderStep(Number(step.dataset.onboardingStep));
      if (event.target.closest("[data-onboarding-back]")) renderStep(currentStep - 1);
      if (event.target.closest("[data-onboarding-next]")) {
        if (currentStep < slideContent.length - 1) renderStep(currentStep + 1);
        else finish({ destination: "run" });
      }
    });
    modal.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft" && currentStep > 0) {
        event.preventDefault();
        renderStep(currentStep - 1);
      }
      if (event.key === "ArrowRight" && currentStep < slideContent.length - 1) {
        event.preventDefault();
        renderStep(currentStep + 1);
      }
    });
    return { modal, renderStep };
  }

  function show({ force = false } = {}) {
    if (dialog || (!force && hasStoredCompletion(storage))) return false;
    lastFocused = document.activeElement;
    const built = buildDialog();
    dialog = built.modal;
    root.body.append(dialog);
    document.body.classList.add("onboarding-open");
    dialog.showModal();
    built.renderStep(0);
    return true;
  }

  return {
    show,
    consider({ blocked = false } = {}) {
      if (blocked) return false;
      return show();
    },
    close: finish,
    isActive: () => Boolean(dialog),
    isComplete: () => hasStoredCompletion(storage),
  };
}

export function setSystemNotice(root, {
  kind = "offline",
  title = "Connection paused",
  message = "Showing the latest available data.",
  retryLabel = "Retry",
} = {}) {
  const banner = root.querySelector("[data-system-banner]");
  if (!banner) return;
  banner.hidden = false;
  banner.dataset.systemKind = kind;
  const titleNode = banner.querySelector("[data-system-banner-title]");
  const copyNode = banner.querySelector("[data-system-banner-copy]");
  const retry = banner.querySelector("[data-system-retry]");
  if (titleNode) titleNode.textContent = title;
  if (copyNode) copyNode.textContent = message;
  if (retry) retry.textContent = retryLabel;
}

export function clearSystemNotice(root) {
  const banner = root.querySelector("[data-system-banner]");
  if (!banner) return;
  banner.hidden = true;
  banner.removeAttribute("data-system-kind");
}

export function bindSystemStateControls(root = document, { onRetry = null } = {}) {
  const retry = async (button) => {
    if (typeof onRetry !== "function") return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      await onRetry();
    } finally {
      if (button.isConnected) {
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    }
  };

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-system-retry]");
    if (button) void retry(button);
  });

  window.addEventListener("offline", () => {
    setSystemNotice(root, {
      title: "Connection paused",
      message: "You’re offline. Current run data and navigation remain available.",
    });
    root.querySelectorAll("[data-sync-status]").forEach((status) => {
      status.textContent = "Offline · showing available data";
    });
  });

  window.addEventListener("online", () => {
    const banner = root.querySelector("[data-system-banner]");
    if (!banner || banner.hidden || banner.dataset.systemKind !== "offline") return;
    setSystemNotice(root, {
      kind: "restored",
      title: "Device is back online",
      message: "BeerRun has not synced yet. Refresh to bring every view up to date.",
      retryLabel: "Refresh",
    });
  });
}

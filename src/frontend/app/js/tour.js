import { driver } from "../assets/vendor/driver/driver.js?v=1.3.6";
import { createBrandWordmark } from "./ui.js?v=beerrun-126-wait-indicators";

export const TOUR_STORAGE_KEY = "beer_run_tour_v1";
export function visibleTourTab(destination, root = document) {
  return [...root.querySelectorAll(`.nav-item[data-destination="${destination}"]`)]
    .find((link) => link.getClientRects().length > 0);
}
export function scrollTourTargetIntoView(element, root = document, viewport = window) {
  if (!element || element.closest(".mobile-footer")) return;
  const bounds = element.getBoundingClientRect();
  const top = viewport.visualViewport?.offsetTop || 0;
  const footer = root.querySelector(".mobile-footer");
  const bottom = Math.min(top + (viewport.visualViewport?.height || viewport.innerHeight),
    footer?.getClientRects().length ? footer.getBoundingClientRect().top : viewport.innerHeight);
  // A target behind the fixed menu is inside the viewport but cannot be tapped.
  if (bounds.top < top + 16 || bounds.bottom > bottom - 16) {
    element.scrollIntoView({ behavior: "instant", block: "center", inline: "nearest" });
  }
}
export function hasVisited(storage) {
  try {
    if (storage.getItem(TOUR_STORAGE_KEY) || storage.getItem("beer_run_revamp_onboarding_complete") || storage.getItem("access_token")) return true;
    for (let index = 0; index < storage.length; index += 1) {
      if (storage.key(index)?.startsWith("beerRunJpn.selectedRun.user.")) return true;
    }
  } catch { /* Storage may be disabled; the in-memory decision still applies. */ }
  return false;
}

export function buildTourSteps({ data = null, mapAvailable = true, authenticated = false } = {}) {
  const step = (id, page, destination, element, title, description, nextBtnText = "Next", extra = {}) => ({
    id, page, destination, element, ...extra,
    popover: { title, description, nextBtnText, showProgress: true, ...extra.popover },
  });
  const tab = (destination, label, source) => step(`tab-${destination}`, source.page, source.destination,
    () => visibleTourTab(destination), `Open the ${label} tab`, `Tap ${label} in the menu to change pages.`, "", {
      source, clickDestination: destination, disableActiveInteraction: false,
      popover: { showButtons: ["previous", "close"] },
    });
  const runner = data?.leaderboard?.find((row) => row.username);
  const mapped = mapAvailable && data?.entries?.find((entry) => entry.latitude != null && entry.longitude != null
    && Number.isFinite(Number(entry.latitude)) && Math.abs(Number(entry.latitude)) <= 90
    && Number.isFinite(Number(entry.longitude)) && Math.abs(Number(entry.longitude)) <= 180);
  const steps = [
    step("featured", "Choose a run", "run", "[data-tour='featured']", "Open BeerRunJPN", "Tap the highlighted button to open our featured trip through Japan.", "", {
      disableActiveInteraction: false, popover: { showButtons: ["close"], showProgress: false },
    }),
    step("run", "Run", "run", ".home-identity", "Run · The trip at a glance", "This is the Run page. It brings together the group’s totals, current leaders, and recent drinks.", "Show the run selector", {
      popover: { showButtons: ["next", "close"] },
    }),
    step("switcher", "Run", "run", "[data-run-switcher]", "Choose which trip you’re viewing", "This button shows BeerRunJPN, the run you just opened. Click it whenever you want to choose a different run."),
  ];
  steps.push(
    tab("standings", "Standings", steps.at(-1)),
    step("standings", "Standings", "standings", ".standings-heading", "Standings · Compare the crew", "This is the group leaderboard. Switch between pure alcohol and drink volume to compare everyone in this run.", runner ? "Show a runner" : "Next"),
  );
  if (runner) steps.push(
    step("runner-choice", "Standings", "standings", "[data-tour-runner]", "Open a runner’s history", "Tap the highlighted runner to see their individual totals and drink history.", "", {
      disableActiveInteraction: false, popover: { showButtons: ["previous", "close"] }, username: runner.username,
    }),
    step("runner", "Runner history", "standings", ".runner-summary", "Runner · Their part of the trip", "This runner’s page shows their rank, volume, and pure alcohol total. Their drinks are listed below, newest first. Each drink can also be opened on the map.", "Next", { username: runner.username }),
  );
  steps.push(
    tab("map", "Map", steps.at(-1)),
    step("map", "Map", "map", ".map-content .page-heading", "Map · Where it happened", "This is the drink map. Each pin is a drink with a saved location. Use the runner filter to follow one person’s stops.", mapped ? "Show a map pin" : "Next"),
  );
  if (mapped) steps.push(
    step("map-pin", "Map", "map", "[data-tour='map-pin']", "Open a drink on the map", "We’ve zoomed in on one drink. Tap the highlighted pin to open its details.", "", {
      entryId: mapped.id, disableActiveInteraction: false, popover: { showButtons: ["previous", "close"] },
    }),
    step("map-detail", "Drink details", "map", ".map-detail__identity", "Drink · The details behind a pin", "The detail panel shows what was logged, who had it, when it happened, and a photo if one was added. Close the panel to return to the map.", "Next", { entryId: mapped.id }),
  );
  steps.push(
    tab("log", "Log", steps.at(-1)),
    step("log", "Log", "log", ".log-content .page-heading", "Log · Add your own drink", "You need an account and membership in the run to save drinks. Enter the drink, volume, and strength. A photo is optional; location is required. Nothing is saved during this tour."),
  );
  steps.push(
    step("finish", "Tour complete", "run", undefined, authenticated ? "You’re ready to go" : "Ready for your own run?", authenticated
      ? "Start a run from My runs, join friends with an invite, or keep exploring public trips."
      : "Create an account to start a run or join your friends with an invite.", authenticated ? "Explore the run" : "Create an account", {
      popover: { showButtons: ["next", "close"] },
    }),
  );
  return steps;
}

export function createOnboardingController({ root = document, storage = localStorage, onPrepare, navigate, visit, getSnapshot = () => ({}), isAuthenticated = () => false } = {}) {
  let dialog = null;
  let tour = null;
  let steps = [];
  let decided = false;
  let preparing = false;
  let cancelled = false;
  let completed = false;
  let changing = false;
  let lastFocused = null;
  let transitionGeneration = 0;
  const remember = (value) => {
    decided = true;
    try { storage.setItem(TOUR_STORAGE_KEY, value); } catch { /* Keep the decision for this page visit. */ }
  };
  const closeDialog = () => {
    if (!dialog) return;
    dialog.close();
    dialog.remove();
    dialog = null;
    if (lastFocused?.isConnected) lastFocused.focus({ preventScroll: true });
  };
  const refreshHighlight = () => {
    if (!tour?.isActive() || changing) return;
    const step = steps[tour.getActiveIndex()];
    const tab = step?.clickDestination && visibleTourTab(step.clickDestination, root);
    if (tab && tab !== tour.getActiveElement()) {
      tour.moveTo(tour.getActiveIndex());
      return;
    }
    scrollTourTargetIntoView(tour.getActiveElement(), root);
    tour.refresh();
  };
  const cleanup = () => {
    window.removeEventListener("resize", refreshHighlight);
    window.visualViewport?.removeEventListener("resize", refreshHighlight);
    window.visualViewport?.removeEventListener("scroll", refreshHighlight);
    root.body.classList.remove("tour-running", "tour-changing");
    changing = false;
  };
  const close = () => {
    cancelled = true;
    transitionGeneration += 1;
    closeDialog();
    tour?.destroy();
    tour = null;
    cleanup();
  };
  const finish = (destination) => {
    completed = true;
    close();
    navigate?.(destination);
  };
  async function showStep(index) {
    if (!tour || cancelled || !steps[index]) return;
    const step = steps[index];
    const request = ++transitionGeneration;
    changing = true;
    root.body.classList.add("tour-changing");
    const source = step.source || step;
    const ready = visit ? await visit(source) : navigate?.(source.destination);
    if (request !== transitionGeneration || !tour || cancelled) return;
    if (ready === false && step.id === "map-pin") {
      const next = steps.findIndex((item) => item.id === "tab-log");
      steps[next].source = steps.find((item) => item.id === "map");
      return showStep(next);
    }
    window.scrollTo({ top: 0, behavior: "instant" });
    root.body.classList.remove("tour-changing");
    tour.moveTo(index);
    changing = false;
  }
  async function start() {
    preparing = true;
    cancelled = false;
    completed = false;
    closeDialog();
    try {
      await onPrepare?.();
      if (cancelled) return;
      if (!root.querySelector("[data-tour='featured']")) {
        remember("unavailable");
        const status = root.querySelector("[data-discovery-status]");
        if (status) status.textContent = "The featured run is unavailable. You can browse runs or retry the tour later.";
        return;
      }
      root.body.classList.add("tour-running");
      steps = buildTourSteps();
      tour = driver({
        animate: false,
        popoverClass: "beer-run-tour",
        overlayOpacity: 0.65,
        overlayClickBehavior: "none",
        disableActiveInteraction: true,
        stagePadding: 6,
        stageRadius: 12,
        onHighlightStarted: (element) => scrollTourTargetIntoView(element, root),
        onHighlighted: refreshHighlight,
        showProgress: false,
        progressText: "{{current}} of {{total}}",
        nextBtnText: "Next",
        prevBtnText: "Back",
        onNextClick: () => {
          if (changing) return;
          const index = tour.getActiveIndex();
          if (steps[index]?.clickDestination || ["featured", "runner-choice", "map-pin"].includes(steps[index]?.id)) return;
          if (steps[index]?.id === "finish") finish(isAuthenticated() ? "run" : "signup");
          else void showStep(index + 1);
        },
        onPrevClick: () => { if (!changing && tour.getActiveIndex() > 1) void showStep(tour.getActiveIndex() - 1); },
        onDestroyed: () => { remember(completed ? "completed" : "dismissed"); tour = null; cleanup(); },
        steps,
        onPopoverRender: (popover, { state }) => {
          if (steps[state.activeIndex]?.id !== "finish") return;
          popover.wrapper.classList.add("beer-run-tour--finish");
          if (isAuthenticated()) {
            popover.wrapper.classList.add("beer-run-tour--member");
            return;
          }
          const explore = document.createElement("button");
          explore.type = "button";
          explore.textContent = "Keep exploring";
          explore.addEventListener("click", () => finish("run"));
          popover.footerButtons.prepend(explore);
        },
      });
      window.addEventListener("resize", refreshHighlight);
      window.visualViewport?.addEventListener("resize", refreshHighlight);
      window.visualViewport?.addEventListener("scroll", refreshHighlight);
      tour.drive();
    } finally { preparing = false; }
  }
  function show({ force = false } = {}) {
    if (dialog || preparing || tour?.isActive() || (!force && (decided || hasVisited(storage)))) return false;
    lastFocused = document.activeElement;
    dialog = document.createElement("dialog");
    dialog.className = "tour-invitation";
    dialog.setAttribute("aria-labelledby", "tour-invitation-title");
    dialog.setAttribute("aria-describedby", "tour-invitation-copy");
    const brand = document.createElement("span");
    brand.className = "onboarding-brand brand-wordmark";
    brand.append(createBrandWordmark());
    const title = document.createElement("h2");
    title.id = "tour-invitation-title";
    title.textContent = force && hasVisited(storage) ? "Take a look around?" : "First time here?";
    const copy = document.createElement("p");
    copy.id = "tour-invitation-copy";
    copy.textContent = "Take a quick tour with BeerRunJPN. We’ll show you the standings, map, and how to log a drink.";
    const actions = document.createElement("div");
    actions.className = "state-actions";
    const yes = document.createElement("button");
    yes.className = "button button--primary";
    yes.textContent = "Yes, show me";
    yes.addEventListener("click", () => { remember("started"); void start(); });
    const no = document.createElement("button");
    no.className = "button button--secondary";
    no.textContent = "No, I’ll explore";
    no.addEventListener("click", () => { remember("declined"); closeDialog(); });
    actions.append(yes, no);
    dialog.append(brand, title, copy, actions);
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); remember("declined"); closeDialog(); });
    root.body.append(dialog);
    dialog.showModal();
    return true;
  }
  root.addEventListener("beer-run:discovery-selected", () => {
    if (!tour?.isActive() || steps[tour.getActiveIndex()]?.id !== "featured") return;
    steps = buildTourSteps({ data: getSnapshot().data, mapAvailable: Boolean(window.L), authenticated: isAuthenticated() });
    tour.setConfig({ ...tour.getConfig(), steps });
    void showStep(1);
  });
  root.addEventListener("beer-run:player-opened", (event) => {
    if (!changing && tour?.isActive() && steps[tour.getActiveIndex()]?.id === "runner-choice") {
      steps[tour.getActiveIndex() + 1].username = event.detail.username;
      void showStep(tour.getActiveIndex() + 1);
    }
  });
  root.addEventListener("beer-run:map-detail-opened", () => {
    if (!changing && tour?.isActive() && steps[tour.getActiveIndex()]?.id === "map-pin") void showStep(tour.getActiveIndex() + 1);
  });
  root.addEventListener("beer-run:navigated", (event) => {
    if (!changing && tour?.isActive() && steps[tour.getActiveIndex()]?.clickDestination === event.detail.destination) {
      void showStep(tour.getActiveIndex() + 1);
    }
  });
  root.addEventListener("beer-run:discovery-selection-failed", close);
  return { show, close, hide: close, consider: ({ blocked = false } = {}) => !blocked && show(), isActive: () => Boolean(dialog || preparing || tour?.isActive()), isComplete: () => decided || hasVisited(storage) };
}

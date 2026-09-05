const DESKTOP_MOTION_QUERY = "(min-width: 768px) and (hover: hover) and (pointer: fine)";

export function createLandingController({ root = document } = {}) {
  const page = root.querySelector("[data-landing-page]");
  const shell = root.querySelector("[data-revamp-preview]");
  const desktopMotion = window.matchMedia(DESKTOP_MOTION_QUERY);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let observer = null;

  const setMotionProfile = () => {
    if (!page) return;
    page.dataset.motionProfile = desktopMotion.matches ? "desktop" : "touch";
  };

  const disconnectObserver = () => {
    observer?.disconnect();
    observer = null;
  };

  const prepareReveals = () => {
    if (!page) return;
    disconnectObserver();
    const items = [...page.querySelectorAll("[data-landing-reveal]")];
    if (reducedMotion.matches || !("IntersectionObserver" in window)) {
      items.forEach((item) => item.classList.add("is-visible"));
      return;
    }
    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer?.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -10%", threshold: 0.14 });
    items.forEach((item) => observer.observe(item));
  };

  const show = () => {
    if (!page || !shell) return;
    shell.hidden = true;
    page.hidden = false;
    document.body.classList.add("landing-view");
    document.title = "BeerRun | Track the trip together";
    setMotionProfile();
    requestAnimationFrame(() => {
      page.classList.add("is-ready");
      prepareReveals();
    });
  };

  const hide = () => {
    if (!page || !shell) return;
    page.hidden = true;
    page.classList.remove("is-ready");
    shell.hidden = false;
    document.body.classList.remove("landing-view");
    document.title = "BeerRun | Route Stamp preview";
    disconnectObserver();
  };

  page?.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-landing-scroll]");
    if (!trigger) return;
    const target = page.querySelector(`#${trigger.dataset.landingScroll}`);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block: "start" });
  });

  desktopMotion.addEventListener("change", setMotionProfile);

  return {
    hide,
    show,
    isActive: () => Boolean(page && !page.hidden),
  };
}

const DRINK_TYPES = ["Beer", "Highball", "Sour", "Sake", "Wine", "Other"];
const QUANTITIES = [
  ["330 ml", 0.33],
  ["500 ml", 0.5],
  ["750 ml", 0.75],
  ["1 L", 1],
  ["Other", "other"],
];

const el = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};

const titleFor = (entry) => [entry.drink_type, entry.brand].filter(Boolean).join(" · ");
const quantityFor = (value) => Number(value) < 1 ? `${Math.round(Number(value) * 1000)} ml` : `${Number(value).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")} L`;
const timezoneName = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const timezoneCode = () => new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(new Date()).find((part) => part.type === "timeZoneName")?.value || "UTC";

function pageHeading(mode) {
  const header = el("header", "page-heading");
  header.append(
    el("p", "eyebrow", mode === "edit" ? "Edit pour" : "Quick log"),
    el("h1", "", mode === "edit" ? "Edit this drink" : "Log a drink"),
    el("p", "page-heading__copy", mode === "edit"
      ? "Update the details below. The original time and run stay unchanged."
      : "Photo is optional. We’ll capture your location automatically."),
  );
  return header;
}

function choiceGroup(label, name, choices, selected) {
  const fieldset = el("fieldset", "log-choice-group");
  fieldset.append(el("legend", "", label));
  const row = el("div", "log-choice-row");
  choices.forEach(([text, value]) => {
    const option = el("label", "log-choice");
    const input = el("input");
    input.type = "radio";
    input.name = name;
    input.value = value;
    input.checked = String(value) === String(selected);
    option.append(input, el("span", "", text));
    row.append(option);
  });
  fieldset.append(row);
  return fieldset;
}

function field(labelText, name, { value = "", type = "text", suffix = "", required = false, inputMode = "" } = {}) {
  const label = el("label", "log-field");
  const labelCopy = el("span", "log-field__label", labelText);
  if (!required) labelCopy.append(el("small", "", " optional"));
  const control = el("div", "log-field__control");
  const input = el("input");
  input.name = name;
  input.type = type;
  input.value = value;
  input.required = required;
  if (inputMode) input.inputMode = inputMode;
  control.append(input);
  if (suffix) control.append(el("span", "log-field__suffix", suffix));
  label.append(labelCopy, control);
  return label;
}

function formView({ entry = null, location = null, locationState = "idle", photoAction = "keep", error = "", pending = false }) {
  const mode = entry ? "edit" : "create";
  const content = el("div", "log-content");
  content.dataset.logView = "";
  content.append(pageHeading(mode));
  const form = el("form", "log-form");
  form.dataset.logForm = "";
  form.noValidate = true;
  const selectedDrink = !entry || DRINK_TYPES.includes(entry.drink_type) ? entry?.drink_type || "Beer" : "Other";
  form.append(choiceGroup("What are you drinking?", "drink_type", DRINK_TYPES.map((value) => [value, value]), selectedDrink));
  const customDrink = field("Custom drink name", "drink_type_custom", { value: DRINK_TYPES.includes(entry?.drink_type) ? "" : entry?.drink_type || "", required: true });
  customDrink.classList.toggle("is-hidden", selectedDrink !== "Other");
  customDrink.dataset.customDrink = "";
  form.querySelector(".log-choice-group")?.append(customDrink);
  const presetQuantity = QUANTITIES.find(([, value]) => value !== "other" && Math.abs(Number(value) - Number(entry?.quantity ?? 0.5)) < 0.001)?.[1] ?? "other";
  const quantityGroup = choiceGroup("How much?", "quantity_preset", QUANTITIES, presetQuantity);
  const customQuantity = field("Custom amount", "quantity_custom", { value: presetQuantity === "other" ? String(Number(entry?.quantity || 0)) : "", suffix: "L", required: true, type: "number", inputMode: "decimal" });
  customQuantity.classList.toggle("is-hidden", presetQuantity !== "other");
  customQuantity.dataset.customQuantity = "";
  quantityGroup.append(customQuantity);
  form.append(quantityGroup);
  const details = el("div", "log-field-grid");
  details.append(
    field("Brand", "brand", { value: entry?.brand || "" }),
    field("ABV", "abv", { value: entry?.abv ?? "", suffix: "%", required: true, type: "number", inputMode: "decimal" }),
  );
  form.append(details);

  const proof = el("section", "log-proof");
  proof.append(el("h2", "", "Photo and place"));
  const proofGrid = el("div", "log-proof__grid");
  const photo = el("div", "log-proof__item");
  photo.append(el("h3", "", "Photo"), el("p", "", entry?.image_path ? "Keep the current photo, replace it, or remove it." : "Optional. Add a photo from your camera or library."));
  const preview = el("div", "log-photo-preview");
  preview.dataset.photoPreview = "";
  if (entry?.image_path) {
    const image = el("img");
    image.src = entry.image_path.startsWith("/") ? entry.image_path : `/${entry.image_path}`;
    image.alt = "Current drink photo";
    preview.append(image);
  } else {
    preview.hidden = true;
  }
  const photoStatus = el("p", "log-photo-status", entry?.image_path ? "Current photo" : "No photo selected");
  photoStatus.dataset.photoStatus = "";
  photo.append(preview, photoStatus);
  const fileLabel = el("label", "button button--secondary log-file-button", entry?.image_path ? "Replace photo" : "Add photo");
  const fileInput = el("input");
  fileInput.type = "file";
  fileInput.name = "image";
  fileInput.accept = "image/*";
  fileLabel.append(fileInput);
  photo.append(fileLabel);
  const clearPhoto = el("button", "button button--quiet log-photo-clear", "Remove photo");
  clearPhoto.type = "button";
  clearPhoto.dataset.clearSelectedPhoto = "";
  clearPhoto.hidden = true;
  photo.append(clearPhoto);
  if (entry?.image_path) {
    const actions = el("div", "log-photo-actions");
    [["keep", "Keep"], ["remove", "Remove"]].forEach(([value, text]) => {
      const label = el("label", "log-photo-choice");
      const input = el("input");
      input.type = "radio";
      input.name = "photo_action";
      input.value = value;
      input.checked = photoAction === value;
      label.append(input, el("span", "", text));
      actions.append(label);
    });
    photo.append(actions);
  }

  const place = el("section", `log-location-field log-location log-location--${locationState}`);
  place.setAttribute("aria-labelledby", "log-location-title");
  const locationHeader = el("div", "log-location-field__header");
  const locationHeading = el("div", "log-location-field__heading");
  const locationTitle = el("h3", "", "Location");
  locationTitle.id = "log-location-title";
  locationTitle.append(el("small", "", " required"));
  const coordinateInfo = el("span", "log-coordinate-info");
  coordinateInfo.dataset.coordinates = "";
  coordinateInfo.hidden = !location;
  const coordinateTrigger = el("button", "log-coordinate-info__trigger", "i");
  coordinateTrigger.type = "button";
  coordinateTrigger.setAttribute("aria-label", "Show captured coordinates");
  coordinateTrigger.setAttribute("aria-describedby", "log-coordinate-tooltip");
  const coordinateTooltip = el("span", "log-coordinate-info__tooltip");
  coordinateTooltip.id = "log-coordinate-tooltip";
  coordinateTooltip.setAttribute("role", "tooltip");
  coordinateTooltip.append(el("span", "", "Captured coordinates"), el("code", "", location ? `${Number(location.latitude).toFixed(5)}, ${Number(location.longitude).toFixed(5)}` : ""));
  coordinateInfo.append(coordinateTrigger, coordinateTooltip);
  locationHeading.append(locationTitle, coordinateInfo);
  const locationCopy = location
    ? "Location captured. Ready to save."
    : locationState === "pending" ? "Finding your current location…" : entry ? "Using the saved location while a fresh position is requested." : "Finding your current location…";
  const locationStatus = el("div", "log-location-field__status");
  const statusDot = el("span", "log-location-field__dot");
  statusDot.setAttribute("aria-hidden", "true");
  const locationMessage = el("p", "log-location-field__message", locationCopy);
  locationMessage.dataset.locationMessage = "";
  locationStatus.append(statusDot, locationMessage);
  const locate = el("button", `button button--quiet log-location-field__action${locationState === "pending" ? " is-loading" : ""}`);
  locate.type = "button";
  locate.dataset.captureLocation = "";
  locate.setAttribute("aria-label", locationState === "pending" ? "Finding location" : "Recapture location");
  locate.title = locationState === "pending" ? "Finding location" : "Recapture location";
  locate.append(el("span", "icon icon--refresh"));
  locate.firstElementChild.setAttribute("aria-hidden", "true");
  locate.disabled = locationState === "pending" || pending;
  locationHeader.append(locationHeading, locate);
  place.append(locationHeader, locationStatus);
  proofGrid.append(photo, place);
  proof.append(proofGrid);
  form.append(proof);

  const errorNode = el("div", "log-error", error);
  errorNode.dataset.logError = "";
  errorNode.hidden = !error;
  errorNode.setAttribute("role", "alert");
  const actions = el("div", "log-submit-row");
  const cancel = el("button", "button button--quiet", mode === "edit" ? "Cancel edit" : "Back to run");
  cancel.type = "button";
  cancel.dataset.cancelLog = "";
  const submit = el("button", "button button--primary", pending ? (mode === "edit" ? "Saving changes…" : "Logging drink…") : (mode === "edit" ? "Save changes" : "Log this drink"));
  submit.type = "submit";
  submit.disabled = pending;
  actions.append(cancel, submit);
  form.append(errorNode, actions);
  content.append(form);
  return content;
}

function receiptView(entry) {
  const content = el("div", "log-content log-success");
  content.dataset.logView = "";
  const header = el("header", "page-heading");
  header.append(el("p", "eyebrow", "Entry saved"), el("h1", "", "That one counts."), el("p", "page-heading__copy", "Your drink is saved to this run."));
  const receipt = el("section", "ticket-surface success-receipt");
  receipt.append(el("p", "eyebrow", "BeerRun receipt"), el("h2", "", titleFor(entry)));
  const facts = el("dl", "success-receipt__facts");
  [["Amount", quantityFor(entry.quantity)], ["Strength", `${Number(entry.abv).toFixed(1)}% ABV`], ["Runner", entry.username]].forEach(([label, value]) => {
    const fact = el("div");
    fact.append(el("dt", "", label), el("dd", "", value));
    facts.append(fact);
  });
  receipt.append(facts, el("p", "success-receipt__place", `Saved at ${Number(entry.latitude).toFixed(5)}, ${Number(entry.longitude).toFixed(5)}`));
  const actions = el("div", "log-submit-row log-success__actions");
  const back = el("button", "button button--primary", "Back to run");
  back.type = "button";
  back.dataset.successRun = "";
  const another = el("button", "button button--secondary", "Log another");
  another.type = "button";
  another.dataset.logAnother = "";
  actions.append(back, another);
  content.append(header, receipt, actions);
  return content;
}

export function createLogController({ root = document, api, auth, formState, getSnapshot, refresh, navigate }) {
  let active = false;
  let entry = null;
  let location = null;
  let locationState = "idle";
  let photoAction = "keep";
  let error = "";
  let locationError = "";
  let requestController = null;

  const main = () => root.querySelector("main");
  const snapshotKey = () => {
    const snapshot = getSnapshot();
    return `${snapshot.currentRun?.id || ""}:${snapshot.contextGeneration}:${auth.getAccessToken() || ""}`;
  };
  const render = () => {
    if (!active) return;
    main()?.classList.remove("main-content--map");
    main()?.replaceChildren(formView({ entry, location, locationState, photoAction, error, pending: formState.isPending() }));
    bind();
  };
  const setError = (message) => {
    error = message;
    const node = root.querySelector("[data-log-error]");
    if (node) {
      node.textContent = message;
      node.hidden = !message;
    }
  };

  function setPendingUi(pending) {
    const form = root.querySelector("[data-log-form]");
    if (!form) return;
    form.querySelectorAll("button, input").forEach((control) => { control.disabled = pending; });
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.textContent = pending ? (entry ? "Saving changes…" : "Logging drink…") : (entry ? "Save changes" : "Log this drink");
  }

  function updateLocationUi() {
    const place = root.querySelector(".log-location");
    const button = root.querySelector("[data-capture-location]");
    if (!place || !button) return;
    place.className = `log-location-field log-location log-location--${locationState}`;
    const copy = place.querySelector("[data-location-message]");
    copy.textContent = locationError || (location
      ? "Location captured. Ready to save."
      : locationState === "pending" ? "Finding your current location…" : entry ? "Using the saved location. Recapture when you are ready." : "Location is required. Recapture to try again.");
    const coordinates = place.querySelector("[data-coordinates]");
    const code = coordinates?.querySelector("code");
    if (coordinates) coordinates.hidden = !location;
    if (code) code.textContent = location ? `${Number(location.latitude).toFixed(5)}, ${Number(location.longitude).toFixed(5)}` : "";
    const locating = locationState === "pending";
    button.classList.toggle("is-loading", locating);
    button.setAttribute("aria-label", locating ? "Finding location" : "Recapture location");
    button.title = locating ? "Finding location" : "Recapture location";
    button.disabled = locationState === "pending" || formState.isPending();
  }

  function captureLocation() {
    if (!navigator.geolocation) {
      setError("Location is not supported by this browser. Try a different device or browser.");
      return;
    }
    locationState = "pending";
    locationError = "";
    error = "";
    setError("");
    updateLocationUi();
    navigator.geolocation.getCurrentPosition(
      (position) => {
        location = { latitude: position.coords.latitude, longitude: position.coords.longitude };
        locationState = "ready";
        locationError = "";
        updateLocationUi();
      },
      (failure) => {
        locationState = "error";
        if (failure.code === failure.PERMISSION_DENIED) locationError = "Location access is blocked. Allow it for this site, then recapture.";
        else if (failure.code === failure.TIMEOUT) locationError = "No position returned. Check device location access, then recapture.";
        else locationError = "A position could not be captured. Check location access, then recapture.";
        updateLocationUi();
      },
      { enableHighAccuracy: false, timeout: 20000, maximumAge: 300000 },
    );
  }

  function buildFormData(form) {
    const data = new FormData();
    const preset = form.elements.quantity_preset.value;
    const quantity = preset === "other" ? Number(form.elements.quantity_custom.value) : Number(preset);
    const drinkType = form.elements.drink_type.value === "Other" ? form.elements.drink_type_custom.value.trim() : form.elements.drink_type.value;
    data.set("drink_type", drinkType);
    data.set("quantity", String(quantity));
    data.set("abv", form.elements.abv.value);
    data.set("brand", form.elements.brand.value.trim());
    if (location) {
      data.set("latitude", String(location.latitude));
      data.set("longitude", String(location.longitude));
    }
    data.set("client_timezone", timezoneName());
    data.set("client_timezone_code", timezoneCode());
    if (!entry) data.set("client_timestamp", new Date().toISOString());
    const image = form.elements.image.files[0];
    if (entry) {
      data.set("photo_action", image ? "replace" : photoAction);
      if (image) data.set("image", image);
    } else if (image) data.set("image", image);
    return { data, quantity, drinkType };
  }

  async function submit(form) {
    const snapshot = getSnapshot();
    const run = snapshot.currentRun;
    const token = auth.getAccessToken();
    if (!run || !snapshot.currentUser || !token || !run.current_user_role) {
      setError("Log in as a member of this run before saving a drink.");
      return;
    }
    if (!entry && !location) {
      setError("Capture your current location before logging this drink.");
      root.querySelector("[data-capture-location]")?.focus();
      return;
    }
    const { data, quantity, drinkType } = buildFormData(form);
    if (!drinkType || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(Number(form.elements.abv.value)) || Number(form.elements.abv.value) < 0) {
      setError("Check the drink type, amount, and ABV before saving.");
      return;
    }
    const context = snapshotKey();
    requestController?.abort();
    requestController = new AbortController();
    formState.setPending(true);
    error = "";
    setError("");
    setPendingUi(true);
    const result = entry
      ? await api.updateEntry(run.id, entry.id, data, token, requestController.signal)
      : await api.createEntry(run.id, data, token, requestController.signal);
    if (context !== snapshotKey() || !active) {
      formState.setPending(false);
      if (active) {
        setPendingUi(false);
        setError("The selected run or login changed while saving. Review the current run before trying again.");
      }
      return;
    }
    formState.setPending(false);
    setPendingUi(false);
    if (!result.ok) {
      if (result.status === 401 || result.status === 403 || result.status === 404) setError("Your login or run access changed before the save completed. Nothing was added here.");
      else if (result.network) setError("The save did not reach BeerRun. Check your connection and try again.");
      else setError(entry ? "BeerRun could not update this drink. Your original entry is unchanged." : "BeerRun could not save this drink. Try again, including the photo if you selected one.");
      return;
    }
    let saved = entry ? await result.response.json() : null;
    const createdId = saved?.id || (await result.response.json()).entry_id;
    await refresh();
    if (context !== snapshotKey() || !active) {
      if (active) setError("The entry was saved, but the selected run changed before the receipt loaded. Return to the run to review it.");
      return;
    }
    saved = getSnapshot().data?.entries?.find((candidate) => Number(candidate.id) === Number(createdId)) || saved;
    if (!saved) {
      setError("The drink was saved, but the receipt could not be loaded. Return to the run to see the refreshed entry.");
      return;
    }
    entry = null;
    location = null;
    main()?.replaceChildren(receiptView(saved));
    bind();
    root.querySelector(".log-success h1")?.focus?.();
  }

  function bind() {
    const form = root.querySelector("[data-log-form]");
    form?.addEventListener("change", (event) => {
      if (event.target.name === "quantity_preset") root.querySelector("[data-custom-quantity]")?.classList.toggle("is-hidden", event.target.value !== "other");
      if (event.target.name === "drink_type") {
        const custom = root.querySelector("[data-custom-drink]");
        custom?.classList.toggle("is-hidden", event.target.value !== "Other");
        if (event.target.value === "Other") custom?.querySelector("input")?.focus();
      }
      if (event.target.name === "image" && event.target.files.length) {
        photoAction = "replace";
        const file = event.target.files[0];
        const preview = root.querySelector("[data-photo-preview]");
        preview?.querySelector("img")?.remove();
        const image = el("img");
        image.src = URL.createObjectURL(file);
        image.alt = `Selected photo: ${file.name}`;
        image.addEventListener("load", () => URL.revokeObjectURL(image.src), { once: true });
        preview?.append(image);
        if (preview) preview.hidden = false;
        const status = root.querySelector("[data-photo-status]");
        if (status) status.textContent = `${file.name} selected`;
        const clear = root.querySelector("[data-clear-selected-photo]");
        if (clear) clear.hidden = false;
      }
      if (event.target.name === "photo_action") {
        photoAction = event.target.value;
        const preview = root.querySelector("[data-photo-preview]");
        const status = root.querySelector("[data-photo-status]");
        if (event.target.value === "remove") {
          if (preview) preview.hidden = true;
          if (status) status.textContent = "Photo will be removed when you save";
        } else if (entry?.image_path) {
          if (preview) preview.hidden = false;
          if (status) status.textContent = "Current photo will be kept";
        }
      }
    });
    form?.addEventListener("submit", (event) => { event.preventDefault(); void submit(form); });
    root.querySelector("[data-capture-location]")?.addEventListener("click", captureLocation);
    root.querySelector("[data-clear-selected-photo]")?.addEventListener("click", () => {
      const input = root.querySelector("input[name='image']");
      if (input) input.value = "";
      photoAction = "keep";
      const preview = root.querySelector("[data-photo-preview]");
      const status = root.querySelector("[data-photo-status]");
      const clear = root.querySelector("[data-clear-selected-photo]");
      if (entry?.image_path) {
        preview?.replaceChildren();
        const image = el("img");
        image.src = entry.image_path.startsWith("/") ? entry.image_path : `/${entry.image_path}`;
        image.alt = "Current drink photo";
        preview?.append(image);
        if (preview) preview.hidden = false;
        if (status) status.textContent = "Current photo will be kept";
      } else {
        preview?.replaceChildren();
        if (preview) preview.hidden = true;
        if (status) status.textContent = "No photo selected";
      }
      if (clear) clear.hidden = true;
    });
    root.querySelector("[data-cancel-log]")?.addEventListener("click", () => navigate("run"));
    root.querySelector("[data-success-run]")?.addEventListener("click", () => navigate("run"));
    root.querySelector("[data-log-another]")?.addEventListener("click", () => { formState.reset(); show(); });
  }

  function show(nextEntry = null) {
    if (active && entry && !nextEntry) {
      render();
      return;
    }
    active = true;
    entry = nextEntry;
    location = null;
    locationState = "idle";
    locationError = "";
    photoAction = "keep";
    error = "";
    formState.reset();
    render();
    captureLocation();
  }
  function hide() { active = false; requestController?.abort(); requestController = null; formState.setPending(false); }
  function reset() {
    hide();
    entry = null;
    location = null;
    locationState = "idle";
    locationError = "";
    photoAction = "keep";
    error = "";
    formState.reset();
  }
  root.addEventListener("beer-run:edit-entry", (event) => show(event.detail));
  return { show, hide, reset };
}

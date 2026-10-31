const DICEBEAR_ENDPOINT = "https://api.dicebear.com/10.x/gaze/svg";
const MUTED_BACKGROUND = "e8e4dc";
const MUTED_BODIES = "a5a58d,b98b73,8e9aaf,9c8a94,8fa38f,b0a58c";

function avatarSeed(username) {
  const value = String(username || "runner").trim().toLocaleLowerCase();
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
  }
  return `beerrun-${(hash >>> 0).toString(36)}`;
}

export function createAccountAvatar(username, className = "runner-mark") {
  const avatar = document.createElement("span");
  avatar.className = className;
  avatar.textContent = Array.from(String(username || "?").trim())[0]?.toLocaleUpperCase() || "?";
  avatar.setAttribute("aria-hidden", "true");

  const params = new URLSearchParams();
  params.set("seed", avatarSeed(username));
  params.set("backgroundColor", MUTED_BACKGROUND);
  MUTED_BODIES.split(",").forEach((color) => params.append("bodyColor", color));
  const image = document.createElement("img");
  image.className = "dicebear-avatar";
  image.alt = "";
  image.loading = "lazy";
  image.decoding = "async";
  image.referrerPolicy = "no-referrer";
  image.src = `${DICEBEAR_ENDPOINT}?${params.toString()}`;
  image.addEventListener("error", () => image.remove(), { once: true });
  avatar.append(image);
  return avatar;
}

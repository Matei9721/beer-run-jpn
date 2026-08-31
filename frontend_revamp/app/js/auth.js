export const ACCESS_TOKEN_KEY = "access_token";

export function createAuthState({ storage = localStorage } = {}) {
  return { getAccessToken: () => storage.getItem(ACCESS_TOKEN_KEY) };
}

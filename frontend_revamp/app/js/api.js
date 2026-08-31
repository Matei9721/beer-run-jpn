export function createApiClient({ fetchImpl = fetch } = {}) {
  return {
    async request(path, options = {}) {
      const response = await fetchImpl(path, options);
      return { ok: response.ok, status: response.status, response };
    },
  };
}

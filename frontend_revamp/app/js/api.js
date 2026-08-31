function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function abortedResult(error) {
  return error?.name === "AbortError" ? { ok: false, aborted: true } : null;
}

async function readJson(fetchImpl, path, { token = null, signal = null } = {}) {
  try {
    const response = await fetchImpl(path, {
      headers: authHeaders(token),
      signal,
    });
    if (!response.ok) {
      return { ok: false, status: response.status, network: false };
    }
    return { ok: true, data: await response.json() };
  } catch (error) {
    return abortedResult(error) || { ok: false, network: true };
  }
}

export function createApiClient({ fetchImpl = fetch } = {}) {
  return {
    async request(path, options = {}) {
      try {
        const response = await fetchImpl(path, options);
        return { ok: response.ok, status: response.status, response };
      } catch (error) {
        return abortedResult(error) || { ok: false, network: true };
      }
    },

    fetchCurrentUser(token, signal = null) {
      return readJson(fetchImpl, "/api/me", { token, signal });
    },

    fetchBeerRuns(token = null, signal = null) {
      return readJson(fetchImpl, "/api/beer-runs", { token, signal });
    },

    findPublicBeerRunByName(name, token = null, signal = null) {
      const query = new URLSearchParams({ view: "public", name });
      return readJson(fetchImpl, `/api/beer-runs?${query.toString()}`, { token, signal });
    },

    fetchBeerRun(beerRunId, token = null, signal = null) {
      return readJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}`, { token, signal });
    },

    fetchLeaderboard(beerRunId, token = null, signal = null, rankBy = "alcohol") {
      const query = new URLSearchParams({ rank_by: rankBy });
      return readJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/leaderboard?${query.toString()}`, { token, signal });
    },

    fetchEntries(beerRunId, token = null, signal = null) {
      return readJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/entries`, { token, signal });
    },
  };
}

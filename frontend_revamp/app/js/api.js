function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function abortedResult(error) {
  return error?.name === "AbortError" ? { ok: false, aborted: true } : null;
}

async function readJson(fetchImpl, path, { token = null, signal = null, cache = null } = {}) {
  try {
    const response = await fetchImpl(path, {
      headers: authHeaders(token),
      signal,
      ...(cache ? { cache } : {}),
    });
    if (!response.ok) {
      return { ok: false, status: response.status, network: false };
    }
    return { ok: true, data: await response.json() };
  } catch (error) {
    return abortedResult(error) || { ok: false, network: true };
  }
}

async function writeJson(fetchImpl, path, { method, token, body = null, signal = null } = {}) {
  try {
    const response = await fetchImpl(path, {
      method,
      headers: { ...authHeaders(token), ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : null,
      signal,
    });
    let data = null;
    try {
      data = await response.json();
    } catch {
      // A valid empty response does not need a synthetic parsing error.
    }
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return abortedResult(error) || { ok: false, network: true };
  }
}

async function writeForm(fetchImpl, path, fields, signal = null) {
  try {
    const response = await fetchImpl(path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(fields),
      signal,
    });
    let data = null;
    try {
      data = await response.json();
    } catch {
      // Authentication failures are still represented by their HTTP status.
    }
    return { ok: response.ok, status: response.status, data };
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

    fetchAccountDeletionSummary(token, signal = null) {
      return readJson(fetchImpl, "/api/me/deletion-summary", { token, signal });
    },

    deleteAccount(password, confirmation, token, signal = null) {
      return writeJson(fetchImpl, "/api/me", {
        method: "DELETE",
        token,
        body: { password, confirmation },
        signal,
      });
    },

    fetchLegalMetadata(signal = null) {
      return readJson(fetchImpl, "/api/legal/metadata", { signal });
    },

    login(username, password, signal = null) {
      return writeForm(fetchImpl, "/token", { username, password }, signal);
    },

    signup(payload, signal = null) {
      return writeJson(fetchImpl, "/api/signup", { method: "POST", body: payload, signal });
    },

    fetchBeerRuns(token = null, signal = null) {
      return readJson(fetchImpl, "/api/beer-runs", { token, signal });
    },

    fetchMyBeerRuns(token, signal = null) {
      const query = new URLSearchParams({ view: "mine" });
      return readJson(fetchImpl, `/api/beer-runs?${query.toString()}`, { token, signal });
    },

    findPublicBeerRunByName(name, token = null, signal = null) {
      const query = new URLSearchParams({ view: "public", name });
      return readJson(fetchImpl, `/api/beer-runs?${query.toString()}`, { token, signal });
    },

    searchPublicBeerRuns(search, token = null, signal = null) {
      const query = new URLSearchParams({ view: "public", q: search });
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

    createBeerRun(payload, token, signal = null) {
      return writeJson(fetchImpl, "/api/beer-runs", { method: "POST", token, body: payload, signal });
    },

    updateBeerRun(beerRunId, payload, token, signal = null) {
      return writeJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}`, { method: "PATCH", token, body: payload, signal });
    },

    fetchBeerRunMembers(beerRunId, token = null, signal = null) {
      return readJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/members`, { token, signal });
    },

    createBeerRunInvite(beerRunId, token, signal = null) {
      return writeJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/invites`, { method: "POST", token, signal });
    },

    previewInvite(code, signal = null) {
      return readJson(fetchImpl, `/api/invites/${encodeURIComponent(code)}`, { signal, cache: "no-store" });
    },

    acceptInvite(code, token, signal = null) {
      return writeJson(fetchImpl, `/api/invites/${encodeURIComponent(code)}/accept`, { method: "POST", token, signal });
    },

    leaveBeerRun(beerRunId, token, signal = null) {
      return writeJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/members/me`, { method: "DELETE", token, signal });
    },

    deleteBeerRun(beerRunId, token, signal = null) {
      return writeJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}`, { method: "DELETE", token, signal });
    },

    createEntry(beerRunId, formData, token, signal = null) {
      return this.request(`/api/beer-runs/${encodeURIComponent(beerRunId)}/entries`, {
        method: "POST",
        headers: authHeaders(token),
        body: formData,
        signal,
      });
    },

    updateEntry(beerRunId, entryId, formData, token, signal = null) {
      return this.request(`/api/beer-runs/${encodeURIComponent(beerRunId)}/entries/${encodeURIComponent(entryId)}`, {
        method: "PATCH",
        headers: authHeaders(token),
        body: formData,
        signal,
      });
    },

    deleteEntry(beerRunId, entryId, token, signal = null) {
      return writeJson(fetchImpl, `/api/beer-runs/${encodeURIComponent(beerRunId)}/entries/${encodeURIComponent(entryId)}`, {
        method: "DELETE",
        token,
        signal,
      });
    },
  };
}

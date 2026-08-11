/**
 * Network helpers for the beer-run scoped trip APIs.
 *
 * Scoped read helpers (leaderboard, entries, beer-runs) return a normalized
 * result so callers can distinguish successful array data from a non-OK HTTP
 * response or a network failure — renderers must never receive an error object
 * as if it were an array:
 *
 *   { ok: true,  data: <parsed array> }
 *   { ok: false, status: <http status>, network: false }   non-OK HTTP
 *   { ok: false, network: true }                            fetch threw
 */

function _authHeaders(token) {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export async function fetchBeerRuns(token = null) {
    try {
        const response = await fetch('/api/beer-runs', { headers: _authHeaders(token) });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        console.error("Error fetching beer runs:", error);
        return { ok: false, network: true };
    }
}

export async function fetchLeaderboard(beerRunId, token = null) {
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}/leaderboard`, {
            headers: _authHeaders(token),
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        console.error("Error fetching leaderboard:", error);
        return { ok: false, network: true };
    }
}

export async function fetchEntries(beerRunId, username = "", token = null) {
    const query = username ? `?username=${encodeURIComponent(username)}` : '';
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}/entries${query}`, {
            headers: _authHeaders(token),
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        console.error("Error fetching entries:", error);
        return { ok: false, network: true };
    }
}

export async function submitEntry(beerRunId, formData, token) {
    return await fetch(`/api/beer-runs/${beerRunId}/entries`, {
        method: 'POST',
        body: formData,
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
}

export async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        return await response.json();
    } catch (error) {
        console.error("Error fetching config:", error);
        return { types: [], quantities: [] };
    }
}

export async function fetchCurrentUser(token) {
    return await fetch('/api/me', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
}

export async function login(username, password) {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    return await fetch('/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: params
    });
}

export async function signup(username, password, signupCode) {
    return await fetch('/api/signup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            password,
            signup_code: signupCode
        })
    });
}

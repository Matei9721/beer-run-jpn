/**
 * Network helpers for the beer-run scoped trip APIs.
 *
 * Scoped read helpers (leaderboard, entries, beer-runs) return a normalized
 * result so callers can distinguish successful array data from a non-OK HTTP
 * response or a network failure - renderers must never receive an error object
 * as if it were an array:
 *
 *   { ok: true,  data: <parsed array> }
 *   { ok: false, status: <http status>, network: false }   non-OK HTTP
 *   { ok: false, network: true }                            fetch threw
 */

function _authHeaders(token) {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function _abortedResult(error) {
    return error && error.name === 'AbortError'
        ? { ok: false, aborted: true }
        : null;
}

async function _fetchRunList(params, token = null, signal = null) {
    const query = new URLSearchParams(params);
    try {
        const response = await fetch(`/api/beer-runs?${query.toString()}`, {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        console.error("Error fetching beer runs:", error);
        return { ok: false, network: true };
    }
}

export async function fetchBeerRuns(token = null, signal = null) {
    try {
        const response = await fetch('/api/beer-runs', {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        console.error("Error fetching beer runs:", error);
        return { ok: false, network: true };
    }
}

export function fetchMyBeerRuns(token, signal = null) {
    return _fetchRunList({ view: 'mine' }, token, signal);
}

export function findPublicBeerRunByName(name, token = null, signal = null) {
    return _fetchRunList({ view: 'public', name }, token, signal);
}

export function searchPublicBeerRuns(query, token = null, signal = null) {
    return _fetchRunList({ view: 'public', q: query }, token, signal);
}

export async function createBeerRun(name, isPublicOrToken, tokenOrSignal = null, signalOrMaybe = null) {
    // Accept the original private-create call shape (name, token, signal)
    // while allowing the visibility-aware shape (name, isPublic, token, signal).
    const visibilitySelected = typeof isPublicOrToken === 'boolean';
    const isPublic = visibilitySelected ? isPublicOrToken : false;
    const token = visibilitySelected ? tokenOrSignal : isPublicOrToken;
    const signal = visibilitySelected ? signalOrMaybe : tokenOrSignal;
    try {
        const response = await fetch('/api/beer-runs', {
            method: 'POST',
            headers: {
                ..._authHeaders(token),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name, is_public: Boolean(isPublic) }),
            signal,
        });
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export async function fetchBeerRunMembers(beerRunId, token = null, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}/members`, {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export async function fetchBeerRun(beerRunId, token = null, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}`, {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        console.error("Error fetching beer run:", error);
        return { ok: false, network: true };
    }
}

export async function updateBeerRun(beerRunId, updates, token, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${encodeURIComponent(beerRunId)}`, {
            method: 'PATCH',
            headers: {
                ..._authHeaders(token),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updates),
            signal,
        });
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export async function leaveBeerRun(beerRunId, token, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${encodeURIComponent(beerRunId)}/members/me`, {
            method: 'DELETE',
            headers: _authHeaders(token),
            signal,
        });
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, status: response.status, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export async function deleteBeerRun(beerRunId, token, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${encodeURIComponent(beerRunId)}`, {
            method: 'DELETE',
            headers: _authHeaders(token),
            signal,
        });
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, status: response.status, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

async function _inviteRequest(path, options = {}) {
    try {
        const response = await fetch(path, options);
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, status: response.status, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export function createBeerRunInvite(beerRunId, token, signal = null) {
    return _inviteRequest(`/api/beer-runs/${encodeURIComponent(beerRunId)}/invites`, {
        method: 'POST',
        headers: _authHeaders(token),
        signal,
    });
}

export function previewInvite(code, signal = null) {
    return _inviteRequest(`/api/invites/${encodeURIComponent(code)}`, { signal });
}

export function acceptInvite(code, token, signal = null) {
    return _inviteRequest(`/api/invites/${encodeURIComponent(code)}/accept`, {
        method: 'POST',
        headers: _authHeaders(token),
        signal,
    });
}

export async function fetchLeaderboard(beerRunId, token = null, signal = null) {
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}/leaderboard`, {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        console.error("Error fetching leaderboard:", error);
        return { ok: false, network: true };
    }
}

export async function fetchEntries(beerRunId, username = "", token = null, signal = null) {
    const query = username ? `?username=${encodeURIComponent(username)}` : '';
    try {
        const response = await fetch(`/api/beer-runs/${beerRunId}/entries${query}`, {
            headers: _authHeaders(token),
            signal,
        });
        if (!response.ok) {
            return { ok: false, status: response.status, network: false };
        }
        return { ok: true, data: await response.json() };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
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

async function _entryMutationRequest(path, options) {
    try {
        const response = await fetch(path, options);
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: typeof payload?.detail === 'string' ? payload.detail : null,
                network: false,
            };
        }
        return { ok: true, status: response.status, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export function patchEntry(beerRunId, entryId, formData, token, signal = null) {
    return _entryMutationRequest(
        `/api/beer-runs/${encodeURIComponent(beerRunId)}/entries/${encodeURIComponent(entryId)}`,
        {
            method: 'PATCH',
            body: formData,
            headers: _authHeaders(token),
            signal,
        },
    );
}

export function deleteEntry(beerRunId, entryId, token, signal = null) {
    return _entryMutationRequest(
        `/api/beer-runs/${encodeURIComponent(beerRunId)}/entries/${encodeURIComponent(entryId)}`,
        {
            method: 'DELETE',
            headers: _authHeaders(token),
            signal,
        },
    );
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

async function _accountDeletionRequest(path, options) {
    try {
        const response = await fetch(path, options);
        let payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                detail: payload?.detail ?? null,
                network: false,
            };
        }
        return { ok: true, status: response.status, data: payload };
    } catch (error) {
        const aborted = _abortedResult(error);
        if (aborted) return aborted;
        return { ok: false, network: true };
    }
}

export function fetchAccountDeletionSummary(token, signal = null) {
    return _accountDeletionRequest('/api/me/deletion-summary', {
        headers: _authHeaders(token),
        signal,
    });
}

export function deleteAccount(password, confirmation, token, signal = null) {
    return _accountDeletionRequest('/api/me', {
        method: 'DELETE',
        headers: {
            ..._authHeaders(token),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password, confirmation }),
        signal,
    });
}

export async function fetchLegalMetadata() {
    return await fetch('/api/legal/metadata');
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

export async function signup(username, password, signupCode, termsVersion) {
    return await fetch('/api/signup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            password,
            signup_code: signupCode,
            terms_agreed: true,
            terms_version: termsVersion,
        })
    });
}

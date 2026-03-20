export async function fetchLeaderboard() {
    try {
        const response = await fetch('/api/leaderboard');
        return await response.json();
    } catch (error) {
        console.error("Error fetching leaderboard:", error);
        return [];
    }
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

export async function fetchEntries(username = "") {

    try {
        const url = username ? `/api/entries?username=${encodeURIComponent(username)}` : '/api/entries';
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Error fetching entries:", error);
        return [];
    }
}

export async function submitEntry(formData, token) {
    const response = await fetch('/api/entries', { 
        method: 'POST', 
        body: formData,
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    return response;
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

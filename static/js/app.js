document.addEventListener('DOMContentLoaded', () => {
    const entryForm = document.getElementById('entry-form');
    const leaderboardData = document.getElementById('leaderboard-data');
    const locationStatus = document.getElementById('location-status');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');

    // Load initial leaderboard
    fetchLeaderboard();

    // Geolocation API
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                latInput.value = position.coords.latitude;
                lngInput.value = position.coords.longitude;
                locationStatus.innerText = `Location captured: ${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`;
                locationStatus.style.color = 'var(--success-color)';
            },
            (error) => {
                console.error("Geolocation error:", error);
                locationStatus.innerText = "Error: Allow location access to log drinks.";
                locationStatus.style.color = "red";
            },
            { enableHighAccuracy: true }
        );
    } else {
        locationStatus.innerText = "Geolocation not supported by browser.";
        locationStatus.style.color = "red";
    }

    // Form submission
    entryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!latInput.value || !lngInput.value) {
            alert("Waiting for location access. Please allow location and try again.");
            return;
        }

        const formData = new FormData(entryForm);
        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerText = "Logging...";

        try {
            const response = await fetch('/api/entries', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                console.log("Success:", result);
                
                // Show success UI
                entryForm.innerHTML = `<div class="success-msg">🔥 Logged! Keep it up! 🔥</div>
                                      <button onclick="window.location.reload()">Log Another</button>`;
                
                // Refresh leaderboard
                fetchLeaderboard();
            } else {
                throw new Error("Failed to log entry");
            }
        } catch (error) {
            console.error("Error:", error);
            alert("Oops! Something went wrong logging that drink.");
            submitBtn.disabled = false;
            submitBtn.innerText = "Log It!";
        }
    });

    async function fetchLeaderboard() {
        try {
            const response = await fetch('/api/leaderboard');
            const data = await response.json();
            
            if (data.length === 0) {
                leaderboardData.innerHTML = "<p>No drinks logged yet. Be the first!</p>";
                return;
            }

            let html = `
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Total (L)</th>
                            <th>Pure Alc (L)</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach(user => {
                html += `
                    <tr>
                        <td>${user.username}</td>
                        <td>${user.total_liters.toFixed(2)}</td>
                        <td>${user.total_alcohol.toFixed(3)}</td>
                    </tr>
                `;
            });

            html += `</tbody></table>`;
            leaderboardData.innerHTML = html;
        } catch (error) {
            console.error("Error fetching leaderboard:", error);
            leaderboardData.innerHTML = "<p>Error loading data.</p>";
        }
    }
});

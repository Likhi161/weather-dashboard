/**
 * WeatherVault - Frontend Application
 * =====================================
 * All S3 and Secrets data fetched via backend API only.
 * Uses async/await with try/catch on every fetch call.
 */

// ═══════════════════════════════════════════════════════════════
// API BASE URL
const API = 'http://13.206.82.46/api';

// ─── State ─────────────────────────────────────────────────────
let currentCity = 'London';

// ─── DOM Ready ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Enter key triggers search
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            searchWeather();
        }
    });

    // Initial loads
    checkHealth();
    loadCityChips();
    loadSecretsTab();
    searchWeather('London');
});

// ═══════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: 'fa-circle-check',
        error: 'fa-circle-xmark',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info',
    };

    toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 350);
    }, 3500);
}

// ═══════════════════════════════════════════════════════════════
// LOADING OVERLAY
// ═══════════════════════════════════════════════════════════════

function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// ═══════════════════════════════════════════════════════════════
// HEALTH CHECK
// ═══════════════════════════════════════════════════════════════

async function checkHealth() {
    try {
        const res = await fetch(`${API}/health`);
        const json = await res.json();

        if (json.success) {
            const data = json.data;

            // EC2 status
            const ec2Val = document.getElementById('statusEC2Value');
            ec2Val.textContent = data.ec2.status === 'running' ? 'Running' : 'Error';
            ec2Val.className = `status-value ${data.ec2.status === 'running' ? 'connected' : 'error'}`;

            // Secrets Manager status
            const secVal = document.getElementById('statusSecretsValue');
            secVal.textContent = data.secrets_manager.status === 'connected' ? 'Connected' : 'Error';
            secVal.className = `status-value ${data.secrets_manager.status === 'connected' ? 'connected' : 'error'}`;

            // S3 status
            const s3Val = document.getElementById('statusS3Value');
            s3Val.textContent = data.s3.status === 'connected' ? `${data.s3.file_count} files` : 'Error';
            s3Val.className = `status-value ${data.s3.status === 'connected' ? 'connected' : 'error'}`;

            // Overall health dot
            const healthDot = document.getElementById('healthDot');
            healthDot.className = `health-dot ${data.overall === 'healthy' ? 'healthy' : 'degraded'}`;

            // Update header badges
            if (data.secrets_manager.status === 'connected') {
                document.getElementById('badgeSecrets').style.borderColor = 'rgba(34, 197, 94, 0.3)';
            }
            if (data.s3.status === 'connected') {
                document.getElementById('badgeS3').style.borderColor = 'rgba(34, 197, 94, 0.3)';
            }

            showToast('AWS services health check complete', 'success');
        }
    } catch (err) {
        console.error('Health check failed:', err);

        document.getElementById('statusEC2Value').textContent = 'Offline';
        document.getElementById('statusEC2Value').className = 'status-value error';
        document.getElementById('statusSecretsValue').textContent = 'Offline';
        document.getElementById('statusSecretsValue').className = 'status-value error';
        document.getElementById('statusS3Value').textContent = 'Offline';
        document.getElementById('statusS3Value').className = 'status-value error';
        document.getElementById('healthDot').className = 'health-dot degraded';

        showToast('Cannot connect to backend API', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// CITY CHIPS (loaded from S3 via API)
// ═══════════════════════════════════════════════════════════════

async function loadCityChips() {
    try {
        const res = await fetch(`${API}/cities`);
        const json = await res.json();

        if (json.success && json.data) {
            const container = document.getElementById('cityChips');
            container.innerHTML = '';

            const cities = json.data.featured_cities || [];
            cities.forEach((city) => {
                const chip = document.createElement('button');
                chip.className = 'city-chip';
                chip.textContent = `${city.emoji} ${city.name}`;
                chip.onclick = () => {
                    document.getElementById('searchInput').value = city.name;
                    searchWeather(city.name);
                };
                container.appendChild(chip);
            });
        }
    } catch (err) {
        console.error('Failed to load city chips:', err);
        showToast('Could not load city list from S3', 'warning');
    }
}

// ═══════════════════════════════════════════════════════════════
// WEATHER SEARCH
// ═══════════════════════════════════════════════════════════════

async function searchWeather(cityParam) {
    const city = cityParam || document.getElementById('searchInput').value.trim();
    if (!city) {
        showToast('Please enter a city name', 'warning');
        return;
    }

    currentCity = city;
    document.getElementById('searchInput').value = city;
    showLoading();

    try {
        // Fetch current weather
        const res = await fetch(`${API}/weather/current?city=${encodeURIComponent(city)}`);
        const json = await res.json();

        if (!json.success) {
            hideLoading();
            showToast(json.error || 'Failed to fetch weather', 'error');
            return;
        }

        const w = json.data;

        // Show weather section
        document.getElementById('weatherSection').style.display = 'block';

        // Populate weather card
        document.getElementById('weatherCity').textContent = w.city;
        document.getElementById('weatherCountry').textContent = w.country;
        document.getElementById('weatherTemp').textContent = `${Math.round(w.temperature)}°`;
        document.getElementById('weatherFeels').textContent = Math.round(w.feels_like);
        document.getElementById('weatherMin').textContent = Math.round(w.temp_min);
        document.getElementById('weatherMax').textContent = Math.round(w.temp_max);
        document.getElementById('weatherDesc').textContent = w.description;
        document.getElementById('weatherIconImg').src = `https://openweathermap.org/img/wn/${w.icon}@4x.png`;
        document.getElementById('weatherIconImg').alt = w.description;

        // Stats
        document.getElementById('statHumidity').textContent = `${w.humidity}%`;
        document.getElementById('statWind').textContent = `${w.wind_speed} m/s`;
        document.getElementById('statPressure').textContent = `${w.pressure} hPa`;
        document.getElementById('statVisibility').textContent = `${(w.visibility / 1000).toFixed(1)} km`;

        // Load weather tip based on condition
        loadWeatherTip(w.description);

        // Load forecast
        loadForecast(city);

        hideLoading();
        showToast(`Weather loaded for ${w.city}`, 'success');

        // Auto-refresh history after 1.5s
        setTimeout(() => loadWeatherHistory(), 1500);

    } catch (err) {
        hideLoading();
        console.error('Weather search error:', err);
        showToast('Failed to connect to weather API', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// WEATHER TIP (from S3)
// ═══════════════════════════════════════════════════════════════

async function loadWeatherTip(description) {
    try {
        // Map description to condition keyword
        const desc = description.toLowerCase();
        let condition = 'cloudy';

        if (desc.includes('clear') || desc.includes('sun')) condition = 'sunny';
        else if (desc.includes('rain') || desc.includes('drizzle')) condition = 'rainy';
        else if (desc.includes('snow')) condition = 'snowy';
        else if (desc.includes('wind') || desc.includes('breeze')) condition = 'windy';
        else if (desc.includes('cloud') || desc.includes('overcast')) condition = 'cloudy';
        else if (desc.includes('storm') || desc.includes('thunder')) condition = 'stormy';
        else if (desc.includes('mist') || desc.includes('fog') || desc.includes('haze')) condition = 'cloudy';

        const res = await fetch(`${API}/weather-tip?condition=${encodeURIComponent(condition)}`);
        const json = await res.json();

        if (json.success && json.data) {
            const banner = document.getElementById('tipBanner');
            const tipText = document.getElementById('tipText');

            tipText.textContent = json.data.tip;
            banner.style.display = 'flex';
            banner.style.borderColor = json.data.color + '33';
            banner.style.background = json.data.color + '15';
        }
    } catch (err) {
        console.error('Failed to load weather tip:', err);
    }
}

// ═══════════════════════════════════════════════════════════════
// FORECAST
// ═══════════════════════════════════════════════════════════════

async function loadForecast(city) {
    try {
        const res = await fetch(`${API}/weather/forecast?city=${encodeURIComponent(city)}`);
        const json = await res.json();

        if (json.success && json.data) {
            const grid = document.getElementById('forecastGrid');
            grid.innerHTML = '';

            const forecast = json.data.forecast || [];
            forecast.forEach((item) => {
                const card = document.createElement('div');
                card.className = 'forecast-card';

                // Parse time
                const dateObj = new Date(item.datetime);
                const timeStr = dateObj.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                });
                const dateStr = dateObj.toLocaleDateString([], {
                    month: 'short',
                    day: 'numeric',
                });

                card.innerHTML = `
                    <div class="forecast-time">${dateStr} ${timeStr}</div>
                    <img src="https://openweathermap.org/img/wn/${item.icon}@2x.png" alt="${item.description}">
                    <div class="forecast-temp">${Math.round(item.temp)}°</div>
                    <div class="forecast-desc">${item.description}</div>
                    <div class="forecast-humidity">
                        <i class="fas fa-droplet"></i> ${item.humidity}%
                    </div>
                `;
                grid.appendChild(card);
            });
        }
    } catch (err) {
        console.error('Failed to load forecast:', err);
    }
}

// ═══════════════════════════════════════════════════════════════
// WEATHER HISTORY (from S3)
// ═══════════════════════════════════════════════════════════════

async function loadWeatherHistory() {
    try {
        const res = await fetch(`${API}/s3/weather-history`);
        const json = await res.json();

        if (json.success && json.data) {
            const grid = document.getElementById('historyGrid');
            grid.innerHTML = '';

            const history = json.data.history || [];

            if (history.length === 0) {
                grid.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No search history yet. Search for a city to start logging.</p>';
                return;
            }

            history.forEach((item) => {
                const card = document.createElement('div');
                card.className = 'history-card';

                const timestamp = item.timestamp
                    ? new Date(item.timestamp).toLocaleString()
                    : 'N/A';

                card.innerHTML = `
                    <div class="history-city">${item.city}</div>
                    <div class="history-temp">${typeof item.temperature === 'number' ? Math.round(item.temperature) + '°' : 'N/A'}</div>
                    <div class="history-desc">${item.description || 'N/A'}</div>
                    <div class="history-timestamp"><i class="far fa-clock"></i> ${timestamp}</div>
                    <div class="history-s3-path"><i class="fas fa-cloud"></i> ${item.s3_path}</div>
                `;

                card.style.cursor = 'pointer';
                card.onclick = () => {
                    document.getElementById('searchInput').value = item.city;
                    searchWeather(item.city);
                };

                grid.appendChild(card);
            });
        }
    } catch (err) {
        console.error('Failed to load weather history:', err);
    }
}

// ═══════════════════════════════════════════════════════════════
// TAB SWITCHING
// ═══════════════════════════════════════════════════════════════

function switchTab(tabName) {
    // Deactivate all tabs and content
    document.querySelectorAll('.tab-btn').forEach((btn) => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((content) => content.classList.remove('active'));

    // Activate selected tab
    if (tabName === 'secrets') {
        document.getElementById('tabSecrets').classList.add('active');
        document.getElementById('tabContentSecrets').classList.add('active');
        loadSecretsTab();
    } else if (tabName === 's3') {
        document.getElementById('tabS3').classList.add('active');
        document.getElementById('tabContentS3').classList.add('active');
        loadS3Tab();
    } else if (tabName === 'appInfo') {
        document.getElementById('tabAppInfo').classList.add('active');
        document.getElementById('tabContentAppInfo').classList.add('active');
    }
}

// ═══════════════════════════════════════════════════════════════
// SECRETS TAB
// ═══════════════════════════════════════════════════════════════

async function loadSecretsTab() {
    try {
        const res = await fetch(`${API}/secrets/info`);
        const json = await res.json();

        if (json.success && json.data) {
            const d = json.data;

            document.getElementById('secretName').textContent = d.secret_name;
            document.getElementById('secretApiPreview').textContent = d.api_key_preview;
            document.getElementById('secretAppId').textContent = d.app_id;
            document.getElementById('secretBucket').textContent = d.s3_bucket;

            // Render key pills
            const pillsContainer = document.getElementById('secretKeysPills');
            pillsContainer.innerHTML = '';
            (d.available_keys || []).forEach((key) => {
                const pill = document.createElement('span');
                pill.className = 'key-pill';
                pill.textContent = key;
                pillsContainer.appendChild(pill);
            });
        }
    } catch (err) {
        console.error('Failed to load secrets info:', err);
        showToast('Could not load Secrets Manager info', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// S3 TAB
// ═══════════════════════════════════════════════════════════════

async function loadS3Tab() {
    try {
        const res = await fetch(`${API}/s3/info`);
        const json = await res.json();

        if (json.success && json.data) {
            const d = json.data;

            document.getElementById('s3TotalFiles').textContent = d.total_files;
            document.getElementById('s3TotalSize').textContent = `${d.total_size_kb} KB`;
            document.getElementById('s3BucketName').textContent = d.bucket_name;
            document.getElementById('s3Region').textContent = d.region;

            // Render folder breakdown
            const folderContainer = document.getElementById('folderCards');
            folderContainer.innerHTML = '';

            const folders = d.folder_breakdown || {};
            Object.entries(folders).forEach(([name, info]) => {
                const card = document.createElement('div');
                card.className = 'folder-card';
                card.innerHTML = `
                    <div class="folder-name">
                        <i class="fas fa-folder"></i> ${name}
                    </div>
                    <div class="folder-stat">Files: <strong>${info.file_count}</strong></div>
                    <div class="folder-stat">Size: <strong>${info.total_size_kb} KB</strong></div>
                `;
                folderContainer.appendChild(card);
            });

            showToast('S3 bucket info refreshed', 'info');
        }
    } catch (err) {
        console.error('Failed to load S3 info:', err);
        showToast('Could not load S3 bucket info', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// APP INFO TAB
// ═══════════════════════════════════════════════════════════════

async function loadAppInfoTab() {
    try {
        const btn = document.getElementById('loadAppInfoBtn');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
        btn.disabled = true;

        const res = await fetch(`${API}/app-info`);
        const json = await res.json();

        if (json.success && json.data) {
            const d = json.data;
            const container = document.getElementById('appInfoData');

            // Build AWS services list
            const awsServicesList = (d.aws_services || [])
                .map((s) => `<li>${s.name}${s.type ? ` (${s.type})` : ''} — ${s.purpose}</li>`)
                .join('');

            // Build features list
            const featuresList = (d.features || [])
                .map((f) => `<li>${f}</li>`)
                .join('');

            // Build deployment info
            const deploy = d.deployment || {};
            const deployInfo = `
                <li>Server: ${deploy.server || 'N/A'}</li>
                <li>Platform: ${deploy.platform || 'N/A'}</li>
                <li>OS: ${deploy.os || 'N/A'}</li>
                <li>Method: ${deploy.method || 'N/A'}</li>
            `;

            const apiProvider = d.api_provider || {};

            container.innerHTML = `
                <div class="app-info-header">
                    <h4>${d.app_name || 'WeatherVault'}</h4>
                    <span class="version-badge">v${d.version || '2.0.0'}</span>
                    <p>${d.description || ''}</p>
                </div>

                <div class="app-info-grid">
                    <div class="app-info-section">
                        <h5><i class="fab fa-aws"></i> AWS Services</h5>
                        <ul>${awsServicesList}</ul>
                    </div>

                    <div class="app-info-section">
                        <h5><i class="fas fa-star"></i> Features</h5>
                        <ul>${featuresList}</ul>
                    </div>

                    <div class="app-info-section">
                        <h5><i class="fas fa-rocket"></i> Deployment</h5>
                        <ul>${deployInfo}</ul>
                    </div>

                    <div class="app-info-section">
                        <h5><i class="fas fa-plug"></i> API Provider</h5>
                        <ul>
                            <li>Name: ${apiProvider.name || 'N/A'}</li>
                            <li>Tier: ${apiProvider.tier || 'N/A'}</li>
                            <li>URL: ${apiProvider.url || 'N/A'}</li>
                        </ul>
                    </div>
                </div>

                <div class="s3-loaded-label">
                    <i class="fas fa-cloud"></i> Loaded from AWS S3
                </div>
            `;

            container.style.display = 'block';
            btn.innerHTML = '<i class="fas fa-cloud-arrow-down"></i> Reload from S3';
            btn.disabled = false;

            showToast('App info loaded from S3', 'success');
        }
    } catch (err) {
        console.error('Failed to load app info:', err);
        showToast('Could not load app info from S3', 'error');

        const btn = document.getElementById('loadAppInfoBtn');
        btn.innerHTML = '<i class="fas fa-cloud-arrow-down"></i> Load from S3';
        btn.disabled = false;
    }
}

// ═══════════════════════════════════════════════════════════════
// CACHE MANAGEMENT
// ═══════════════════════════════════════════════════════════════

async function clearAllCaches() {
    try {
        const res = await fetch(`${API}/cache/clear`, { method: 'POST' });
        const json = await res.json();

        if (json.success) {
            showToast('All caches cleared (Secrets + S3)', 'success');
            // Refresh tabs
            loadSecretsTab();
        } else {
            showToast(json.error || 'Failed to clear caches', 'error');
        }
    } catch (err) {
        console.error('Failed to clear caches:', err);
        showToast('Failed to clear caches', 'error');
    }
}

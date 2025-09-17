document.addEventListener('DOMContentLoaded', () => {
    const settingsForms = document.querySelectorAll('.settings-form');

    // Function to load settings and populate forms
    const loadSettings = async () => {
        try {
            const response = await dashboard.apiFetch('/api/settings');
            if (!response.ok) {
                throw new Error('Failed to fetch settings');
            }
            const settings = await response.json();

            // Populate General Settings
            document.querySelector('[name="dashboard_name"]').value = settings.general.dashboard_name;
            document.querySelector('[name="stream_quality"]').value = settings.general.default_stream_quality;
            document.querySelector('[name="auto_start"]').checked = settings.general.auto_start_streams;

            // Populate Storage Settings
            document.querySelector('[name="retention_period"]').value = settings.storage.retention_period_hours;
            document.querySelector('[name="auto_cleanup"]').checked = settings.storage.auto_cleanup;

            // Populate Cloudflare Settings
            document.querySelector('[name="cloudflare_domain"]').value = settings.cloudflare.domain;
            document.querySelector('[name="enable_https"]').checked = settings.cloudflare.enable_https;
            document.querySelector('[name="access_protection"]').value = settings.cloudflare.access_protection;

        } catch (error) {
            console.error('Error loading settings:', error);
            alert('Could not load settings from the server.');
        }
    };

    // Function to handle form submission
    const handleFormSubmit = async (event) => {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const data = {};

        // Group form data by tab
        const tabId = form.closest('.settings-tab').id;
        let settingsGroup = {};

        switch(tabId) {
            case 'general-tab':
                settingsGroup = {
                    general: {
                        dashboard_name: formData.get('dashboard_name'),
                        default_stream_quality: formData.get('stream_quality'),
                        auto_start_streams: formData.has('auto_start')
                    }
                };
                break;
            case 'storage-tab':
                settingsGroup = {
                    storage: {
                        retention_period_hours: parseInt(formData.get('retention_period'), 10),
                        auto_cleanup: formData.has('auto_cleanup')
                    }
                };
                break;
            case 'cloudflare-tab':
                settingsGroup = {
                    cloudflare: {
                        domain: formData.get('cloudflare_domain'),
                        enable_https: formData.has('enable_https'),
                        access_protection: formData.get('access_protection')
                    }
                };
                break;
            case 'motion-tab':
                const motionData = {};
                const cameras = await (await dashboard.apiFetch('/api/cameras')).json();
                cameras.forEach(camera => {
                    motionData[camera.id] = {
                        enabled: formData.has(`motion_enabled_${camera.id}`),
                        min_area: parseInt(formData.get(`motion_min_area_${camera.id}`), 10),
                        cooldown: parseInt(formData.get(`motion_cooldown_${camera.id}`), 10)
                    };
                });
                settingsGroup = { motion: motionData };
                break;
        }

        try {
            const response = await dashboard.apiFetch('/api/settings', {
                method: 'POST',
                body: JSON.stringify(settingsGroup)
            });

            if (response.ok) {
                alert('Settings saved successfully!');
            } else {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to save settings');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            alert(`Error: ${error.message}`);
        }
    };

    // Attach event listeners to all forms
    settingsForms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });

    // Function to update system stats
    const updateSystemStats = async () => {
        // Only run if the system tab is visible
        if (!document.getElementById('system-tab').classList.contains('active')) {
            return;
        }

        try {
            const response = await dashboard.apiFetch('/api/system/stats');
            if (!response.ok) return;

            const stats = await response.json();

            // Helper to format bytes
            const formatBytes = (bytes, decimals = 2) => {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const dm = decimals < 0 ? 0 : decimals;
                const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
            };

            // Update UI elements
            const cpuUsageEl = document.querySelector('#system-tab .info-grid .info-item:nth-child(1) .info-value');
            const memUsageEl = document.querySelector('#system-tab .info-grid .info-item:nth-child(2) .info-value');

            if (cpuUsageEl) cpuUsageEl.textContent = `${stats.cpu_usage.toFixed(1)}%`;
            if (memUsageEl) memUsageEl.textContent = `${formatBytes(stats.memory.used)} / ${formatBytes(stats.memory.total)}`;

        } catch (error) {
            console.error('Error fetching system stats:', error);
        }
    };

    // Attach event listeners to all forms
    settingsForms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });

    const populateMotionSettings = async () => {
        try {
            const [camResponse, settingsResponse] = await Promise.all([
                dashboard.apiFetch('/api/cameras'),
                dashboard.apiFetch('/api/settings')
            ]);

            if (!camResponse.ok || !settingsResponse.ok) {
                throw new Error('Failed to fetch camera or settings data');
            }

            const cameras = await camResponse.json();
            const settings = await settingsResponse.json();
            const motionSettings = settings.motion || {};

            const container = document.getElementById('motion-camera-list');
            container.innerHTML = ''; // Clear existing content

            cameras.forEach(camera => {
                const camSettings = motionSettings[camera.id] || {};
                const enabled = camSettings.enabled || false;
                const minArea = camSettings.min_area || 500;
                const cooldown = camSettings.cooldown || 60;

                const cameraDiv = document.createElement('div');
                cameraDiv.className = 'motion-camera-item form-group';
                cameraDiv.innerHTML = `
                    <h4>${camera.name} (${camera.ip})</h4>
                    <label>
                        <input type="checkbox" name="motion_enabled_${camera.id}" ${enabled ? 'checked' : ''}>
                        Enable Motion Detection
                    </label>
                    <div class="form-group">
                        <label>Minimum Motion Area (pixels)</label>
                        <input type="number" name="motion_min_area_${camera.id}" value="${minArea}" min="100" step="100">
                    </div>
                    <div class="form-group">
                        <label>Recording Cooldown (seconds)</label>
                        <input type="number" name="motion_cooldown_${camera.id}" value="${cooldown}" min="10" step="10">
                    </div>
                `;
                container.appendChild(cameraDiv);
            });

        } catch (error) {
            console.error('Error populating motion settings:', error);
        }
    };

    // Initial load of settings
    loadSettings();
    populateMotionSettings();

    // Start polling for system stats
    setInterval(updateSystemStats, 3000); // Update every 3 seconds
});

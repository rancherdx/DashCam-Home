// Dashboard JavaScript functionality - Complete Version

class CameraDashboard {
    constructor() {
        this.cameras = [];
        this.streams = new Map();
        this.apiToken = window.API_TOKEN;
        this.isAuthenticated = !!window.API_TOKEN;
        this.autoRefreshInterval = null;
        this.thumbnailRefreshInterval = null;
        this.init();
    }

    async init() {
        await this.initializeApp();
    }

    async initializeApp() {
        try {
            // Show loading state
            this.showLoadingState();
            
            if (!this.isAuthenticated) {
                console.error("API Token not found. Authentication will fail.");
                this.showNotification("API Token not found. Please configure it in your environment.", "error");
            }
            
            // Load cameras and setup the interface
            await this.loadCameras();
            this.setupEventListeners();
            this.startAutoRefresh();
            
            // Hide loading state
            this.hideLoadingState();
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showNotification('Failed to initialize application. Please refresh the page.', 'error');
        }
    }

    async apiFetch(url, options = {}) {
        if (!this.isAuthenticated) {
            console.error('Cannot make API call, not authenticated.');
            this.showNotification('Authentication token is missing.', 'error');
            return Promise.reject('Missing API Token');
        }

        const headers = {
            'X-Auth-Token': this.apiToken,
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Remove content-type for FormData requests
        if (options.body instanceof FormData) {
            delete headers['Content-Type'];
        }

        try {
            const response = await fetch(url, { ...options, headers });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP ${response.status}: ${response.statusText}`, errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response;
            
        } catch (error) {
            console.error('API request failed:', error);
            this.showNotification('API request failed. Please check your connection.', 'error');
            throw error;
        }
    }

    async loadCameras() {
        try {
            const response = await this.apiFetch('/api/cameras');
            this.cameras = await response.json();
            this.renderCameras();
        } catch (error) {
            console.error('Error loading cameras:', error);
            this.showNotification('Failed to load cameras.', 'error');
        }
    }

    renderCameras() {
        const grid = document.getElementById('camera-grid');
        if (!grid) return;

        if (this.cameras.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h2>No cameras configured</h2>
                    <p>Add your first camera to get started</p>
                    <a href="/setup" class="btn-primary">Add Camera</a>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.cameras.map(camera => `
            <div class="camera-card" data-camera-id="${camera.id}" draggable="true">
                <div class="camera-header">
                    <h3>${this.escapeHtml(camera.name)}</h3>
                    <span class="status-indicator ${camera.status === 'connected' ? 'online' : 'offline'}"></span>
                </div>
                
                <div class="camera-feed">
                    <video 
                        controls 
                        playsinline 
                        webkit-playsinline 
                        muted
                        data-camera-id="${camera.id}"
                        poster="/thumbnails/${camera.id}/latest.jpg?t=${Date.now()}"
                        onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
                    >
                        <source src="/streams/${camera.id}/index.m3u8" type="application/vnd.apple.mpegurl">
                    </video>
                    <div class="video-placeholder" style="display: none;">
                        <p>❌ Stream unavailable</p>
                        <button onclick="dashboard.retryStream('${camera.id}')">Retry</button>
                    </div>
                </div>
                
                <div class="camera-controls">
                    <button class="btn-small" onclick="dashboard.takeSnapshot('${camera.id}')">
                        📸 Snapshot
                    </button>
                    <button class="btn-small ${camera.recording ? 'recording' : ''}" 
                            onclick="dashboard.toggleRecording('${camera.id}')">
                        ${camera.recording ? '⏹️ Stop' : '⏺️ Record'}
                    </button>
                    <a href="/onvif/${camera.id}" class="btn-small">🎮 PTZ</a>
                    <button class="btn-small" onclick="dashboard.editCamera('${camera.id}')">
                        ✏️ Edit
                    </button>
                    <button class="btn-small btn-danger" onclick="dashboard.deleteCamera('${camera.id}', '${this.escapeHtml(camera.name)}')">
                        🗑️ Delete
                    </button>
                </div>
                
                <div class="camera-info">
                    <span>${this.escapeHtml(camera.ip)}</span>
                    <span class="status-badge ${camera.status}">${camera.status}</span>
                </div>
            </div>
        `).join('');

        // Initialize video players
        this.initializeVideoPlayers();
    }

    initializeVideoPlayers() {
        document.querySelectorAll('video').forEach(video => {
            const cameraId = video.dataset.cameraId;
            
            video.addEventListener('loadeddata', () => {
                console.log(`Video loaded for camera ${cameraId}`);
                this.updateThumbnail(cameraId);
            });
            
            video.addEventListener('error', (e) => {
                console.error(`Video error for camera ${cameraId}:`, e);
                this.showVideoError(cameraId);
            });
            
            video.addEventListener('play', () => {
                video.classList.add('playing');
            });
            
            video.addEventListener('pause', () => {
                video.classList.remove('playing');
            });
        });
    }

    async takeSnapshot(cameraId) {
        try {
            const response = await this.apiFetch(`/api/snapshot/${cameraId}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showNotification('Snapshot saved successfully!', 'success');
            } else {
                this.showNotification('Failed to take snapshot', 'error');
            }
        } catch (error) {
            this.showNotification('Error taking snapshot: ' + error.message, 'error');
        }
    }

    async toggleRecording(cameraId) {
        try {
            const camera = this.cameras.find(c => c.id === cameraId);
            const endpoint = camera.recording ? 
                `/api/recording/stop/${cameraId}` : 
                `/api/recording/start/${cameraId}`;
            
            const response = await this.apiFetch(endpoint, { method: 'POST' });
            
            if (response.ok) {
                await this.loadCameras(); // Refresh camera list
                const action = camera.recording ? 'stopped' : 'started';
                const cameraName = camera.name || 'Camera';
                this.showNotification(`Recording ${action} for ${cameraName}`, 'success');
            }
        } catch (error) {
            this.showNotification('Error controlling recording: ' + error.message, 'error');
        }
    }

    async editCamera(cameraId) {
        window.location.href = `/setup?camera_id=${cameraId}`;
    }

    async deleteCamera(cameraId, cameraName) {
        console.log(`Deleting camera: ${cameraName} (${cameraId})`);
        if (!confirm(`Are you sure you want to delete the camera "${cameraName}"? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await this.apiFetch(`/api/cameras/${cameraId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showNotification(`Camera "${cameraName}" deleted successfully.`, 'success');
                await this.loadCameras(); // Refresh the camera list
            } else {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete camera');
            }
        } catch (error) {
            this.showNotification(`Error deleting camera: ${error.message}`, 'error');
        }
    }

    async updateThumbnail(cameraId) {
        try {
            // Update thumbnail poster with timestamp to prevent caching
            const videoElement = document.querySelector(`video[data-camera-id="${cameraId}"]`);
            if (videoElement) {
                videoElement.poster = `/thumbnails/${cameraId}/latest.jpg?t=${Date.now()}`;
            }
        } catch (error) {
            console.error('Error updating thumbnail:', error);
        }
    }

    showVideoError(cameraId) {
        const videoElement = document.querySelector(`video[data-camera-id="${cameraId}"]`);
        if (videoElement) {
            videoElement.style.display = 'none';
            const placeholder = videoElement.nextElementSibling;
            if (placeholder && placeholder.classList.contains('video-placeholder')) {
                placeholder.style.display = 'block';
            }
        }
    }

    async retryStream(cameraId) {
        try {
            await this.apiFetch(`/api/stream/restart/${cameraId}`, { method: 'POST' });
            this.showNotification('Restarting stream...', 'info');
            
            // Reload after a short delay
            setTimeout(() => {
                this.loadCameras();
            }, 2000);
            
        } catch (error) {
            this.showNotification('Failed to restart stream: ' + (error.error || error.message), 'error');
        }
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadCameras();
                this.showNotification('Refreshing cameras...', 'info');
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'r' && e.ctrlKey) {
                e.preventDefault();
                this.loadCameras();
                this.showNotification('Refreshing cameras...', 'info');
            }
            
            if (e.key === 'Escape') {
                // Exit fullscreen or PiP
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else if (document.pictureInPictureElement) {
                    document.exitPictureInPicture();
                }
            }
        });

        // Visibility change (tab focus)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.loadCameras();
            }
        });

        // Window resize - adjust grid layout
        window.addEventListener('resize', this.debounce(() => {
            this.adjustGridLayout();
        }, 250));

        // Initialize drag and drop
        this.initDragAndDrop();
    }

    startAutoRefresh() {
        // Clear existing intervals
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        if (this.thumbnailRefreshInterval) {
            clearInterval(this.thumbnailRefreshInterval);
        }

        // Refresh camera status every 30 seconds
        this.autoRefreshInterval = setInterval(() => {
            if (!document.hidden && this.isAuthenticated) {
                this.loadCameras();
            }
        }, 30000);

        // Update thumbnails every 10 seconds
        this.thumbnailRefreshInterval = setInterval(() => {
            if (!document.hidden) {
                this.cameras.forEach(camera => {
                    this.updateThumbnail(camera.id);
                });
            }
        }, 10000);
    }

    initDragAndDrop() {
        const grid = document.getElementById('camera-grid');
        if (!grid) return;

        let draggedItem = null;

        grid.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('camera-card')) {
                draggedItem = e.target;
                e.target.style.opacity = '0.5';
                e.target.classList.add('dragging');
            }
        });

        grid.addEventListener('dragend', (e) => {
            if (draggedItem) {
                draggedItem.style.opacity = '1';
                draggedItem.classList.remove('dragging');
                draggedItem = null;
            }
        });

        grid.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem) {
                e.dataTransfer.dropEffect = 'move';
            }
        });

        grid.addEventListener('drop', (e) => {
            e.preventDefault();
            if (draggedItem && e.target.classList.contains('camera-card')) {
                grid.insertBefore(draggedItem, e.target.nextSibling);
                this.saveCameraOrder();
            }
        });
    }

    async saveCameraOrder() {
        const cameraIds = Array.from(document.querySelectorAll('.camera-card'))
            .map(card => card.dataset.cameraId);
        
        try {
            await this.apiFetch('/api/cameras/order', {
                method: 'POST',
                body: JSON.stringify({ order: cameraIds })
            });
            this.showNotification('Camera order saved', 'success');
        } catch (error) {
            console.error('Error saving camera order:', error);
            this.showNotification('Failed to save camera order', 'error');
        }
    }

    adjustGridLayout() {
        const grid = document.getElementById('camera-grid');
        if (!grid) return;

        // Adjust grid columns based on window size
        const width = window.innerWidth;
        if (width < 768) {
            grid.style.gridTemplateColumns = '1fr';
        } else if (width < 1200) {
            grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(350px, 1fr))';
        } else {
            grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(400px, 1fr))';
        }
    }

    showNotification(message, type = 'info') {
        // Remove existing notifications
        document.querySelectorAll('.notification').forEach(n => n.remove());
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span>${this.escapeHtml(message)}</span>
            <button onclick="this.parentElement.remove()">×</button>
        `;
        
        // Add styles if not already present
        if (!document.querySelector('#notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'notification-styles';
            styles.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 15px 20px;
                    border-radius: 5px;
                    color: white;
                    z-index: 1000;
                    max-width: 300px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    animation: slideIn 0.3s ease;
                }
                .notification.success { background: #27ae60; }
                .notification.error { background: #e74c3c; }
                .notification.info { background: #3498db; }
                .notification.warning { background: #f39c12; }
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `;
            document.head.appendChild(styles);
        }
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    showLoadingState() {
        let loading = document.getElementById('loading-overlay');
        if (!loading) {
            loading = document.createElement('div');
            loading.id = 'loading-overlay';
            loading.innerHTML = `
                <div class="loading-spinner"></div>
                <p>Loading cameras...</p>
            `;
            document.body.appendChild(loading);
            
            // Add styles
            const styles = document.createElement('style');
            styles.textContent = `
                #loading-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(255,255,255,0.9);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    z-index: 9999;
                }
                .loading-spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #3498db;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(styles);
        }
        loading.style.display = 'flex';
    }

    hideLoadingState() {
        const loading = document.getElementById('loading-overlay');
        if (loading) {
            loading.style.display = 'none';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Utility methods
    async exportConfig() {
        try {
            const response = await this.apiFetch('/api/export/config');
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'camera-dashboard-config.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            this.showNotification('Export failed: ' + error.message, 'error');
        }
    }

    async importConfig(file) {
        try {
            const formData = new FormData();
            formData.append('config', file);
            
            const response = await this.apiFetch('/api/import/config', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                this.showNotification('Configuration imported successfully!', 'success');
                await this.loadCameras();
            }
        } catch (error) {
            this.showNotification('Import failed: ' + error.message, 'error');
        }
    }
}

// Global dashboard instance
const dashboard = new CameraDashboard();

// Utility functions
function formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Picture-in-Picture functionality
function togglePiP(videoElement) {
    if (document.pictureInPictureElement) {
        document.exitPictureInPicture();
    } else if (document.pictureInPictureEnabled) {
        videoElement.requestPictureInPicture().catch(err => {
            console.error('Error entering PiP:', err);
        });
    }
}

// Fullscreen functionality
function toggleFullscreen(element) {
    if (!document.fullscreenElement) {
        element.requestFullscreen().catch(err => {
            console.error('Error attempting to enable fullscreen:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Additional initialization if needed
    
    // Add global error handler
    window.addEventListener('error', (e) => {
        console.error('Global error:', e.error);
        dashboard.showNotification('An unexpected error occurred', 'error');
    });
    
    // Add unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (e) => {
        console.error('Unhandled promise rejection:', e.reason);
        dashboard.showNotification('An unexpected error occurred', 'error');
        e.preventDefault();
    });
});

// Make functions available globally for HTML onclick attributes
window.togglePiP = togglePiP;
window.toggleFullscreen = toggleFullscreen;
window.formatTimestamp = formatTimestamp;
window.formatFileSize = formatFileSize;
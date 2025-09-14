document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('camera-modal');
    const addCameraBtn = document.getElementById('add-camera-btn');
    const closeBtn = document.querySelector('.close-btn');
    const cameraForm = document.getElementById('camera-form');
    const cameraListContainer = document.getElementById('camera-list-container');
    const modalTitle = document.getElementById('modal-title');
    const cameraIdInput = document.getElementById('camera-id');

    // --- Modal Handling ---
    addCameraBtn.addEventListener('click', () => {
        modal.style.display = 'block';
        modalTitle.textContent = 'Add Camera';
        cameraForm.reset();
        cameraIdInput.value = '';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // --- API Functions ---
    const getAuthToken = () => {
        // In a real app, you'd get this from a secure place after login
        return 'dev-api-token-change-in-production';
    };

    const fetchCameras = async () => {
        try {
            const response = await fetch('/api/cameras', {
                headers: { 'X-Auth-Token': getAuthToken() }
            });
            if (!response.ok) throw new Error('Failed to fetch cameras');
            const cameras = await response.json();
            renderCameras(cameras);
        } catch (error) {
            console.error('Error fetching cameras:', error);
            cameraListContainer.innerHTML = '<p>Error loading cameras.</p>';
        }
    };

    const saveCamera = async (cameraData) => {
        const cameraId = cameraIdInput.value;
        const method = cameraId ? 'PUT' : 'POST';
        const url = cameraId ? `/api/cameras/${cameraId}` : '/api/cameras';

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Auth-Token': getAuthToken()
                },
                body: JSON.stringify(cameraData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to save camera');
            }

            modal.style.display = 'none';
            fetchCameras(); // Refresh the list
        } catch (error) {
            console.error('Error saving camera:', error);
            alert(`Error: ${error.message}`);
        }
    };

    const deleteCamera = async (cameraId) => {
        if (!confirm('Are you sure you want to delete this camera?')) return;

        try {
            const response = await fetch(`/api/cameras/${cameraId}`, {
                method: 'DELETE',
                headers: { 'X-Auth-Token': getAuthToken() }
            });

            if (!response.ok) throw new Error('Failed to delete camera');

            fetchCameras(); // Refresh the list
        } catch (error) {
            console.error('Error deleting camera:', error);
            alert('Error deleting camera.');
        }
    };

    // --- Rendering ---
    const renderCameras = (cameras) => {
        if (!cameras || cameras.length === 0) {
            cameraListContainer.innerHTML = '<p>No cameras configured.</p>';
            return;
        }

        let html = '<table>';
        html += '<tr><th>Name</th><th>IP Address</th><th>Status</th><th>Actions</th></tr>';
        cameras.forEach(camera => {
            html += `
                <tr>
                    <td>${camera.name}</td>
                    <td>${camera.ip}</td>
                    <td>${camera.stream_active ? 'Streaming' : 'Idle'}</td>
                    <td>
                        <button class="btn-secondary edit-btn" data-id="${camera.id}">Edit</button>
                        <button class="btn-warning delete-btn" data-id="${camera.id}">Delete</button>
                    </td>
                </tr>
            `;
        });
        html += '</table>';
        cameraListContainer.innerHTML = html;
    };

    // --- Event Listeners ---
    cameraForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData(cameraForm);
        const cameraData = Object.fromEntries(formData.entries());
        // Ensure password is not sent if empty during edit
        if (cameraIdInput.value && !cameraData.password) {
            delete cameraData.password;
        }
        saveCamera(cameraData);
    });

    cameraListContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('edit-btn')) {
            const id = e.target.dataset.id;
            try {
                const response = await fetch(`/api/cameras/${id}`, {
                    headers: { 'X-Auth-Token': getAuthToken() }
                });
                if (!response.ok) throw new Error('Failed to fetch camera details');
                const camera = await response.json();

                modal.style.display = 'block';
                modalTitle.textContent = 'Edit Camera';
                cameraIdInput.value = camera.id;
                document.getElementById('camera-name').value = camera.name;
                document.getElementById('camera-ip').value = camera.ip;
                document.getElementById('camera-username').value = camera.username;
                document.getElementById('camera-onvif-port').value = camera.onvif_port || 80;
                // Password field is left blank for security, user can fill it to change it.
                document.getElementById('camera-password').value = '';

            } catch (error) {
                console.error('Error fetching camera for edit:', error);
                alert('Could not load camera details for editing.');
            }
        }
        if (e.target.classList.contains('delete-btn')) {
            const id = e.target.dataset.id;
            deleteCamera(id);
        }
    });


    // Initial load
    fetchCameras();
});

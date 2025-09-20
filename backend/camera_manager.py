import uuid
import logging
from datetime import datetime
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .stream_processor import StreamProcessor
    from .onvif_controller import ONVIFController
    from .recording_manager import RecordingManager
    from .settings_manager import SettingsManager

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, stream_processor: "StreamProcessor",
                 onvif_controller: "ONVIFController",
                 settings_manager: "SettingsManager"):
        self.cameras: Dict[str, dict] = {}
        self.stream_processor = stream_processor
        self.onvif_controller = onvif_controller
        self.settings_manager = settings_manager
        self.recording_manager: 'RecordingManager' = None  # Injected after init
        self._load_cameras_from_config()

    def _load_cameras_from_config(self):
        """Loads camera configurations from the settings file."""
        logger.info("Loading cameras from configuration...")
        camera_configs = self.settings_manager.get_camera_configs()
        for cam_config in camera_configs:
            self._add_camera_from_config(cam_config)

    def _add_camera_from_config(self, camera_config: dict):
        """Internal method to add a camera from config without resaving."""
        camera_id = camera_config.get('id')
        if not camera_id:
            logger.warning("Skipping camera from config with no ID.")
            return

        self.cameras[camera_id] = camera_config
        logger.info(f"Loaded camera '{camera_config.get('name', 'Unknown')}' from config.")

        self.onvif_controller.connect_camera(
            camera_id,
            camera_config['ip'],
            camera_config.get('onvif_port', 80),
            camera_config['username'],
            camera_config['password']
        )

    def add_camera(self, camera_config: dict) -> str:
        """Tests connection and adds a new camera, then saves to config."""
        camera_id = str(uuid.uuid4())

        # Test the connection first
        can_connect = self.onvif_controller.connect_camera(
            camera_id,
            camera_config['ip'],
            camera_config.get('onvif_port', 80),
            camera_config['username'],
            camera_config['password']
        )

        if not can_connect:
            logger.error(f"Could not connect to camera {camera_config.get('name')} at {camera_config.get('ip')}. Not saving.")
            return None

        # If connection is successful, proceed to add and save
        camera_config['id'] = camera_id
        camera_config['created_at'] = datetime.now().isoformat()

        if self.settings_manager.add_camera_config(camera_config):
            self._add_camera_from_config(camera_config)
            logger.info(f"Successfully connected, added, and saved new camera: {camera_config.get('name')}")
            return camera_id
        else:
            logger.error(f"Failed to save new camera to config: {camera_config.get('name')}")
            # Disconnect since we failed to save
            self.onvif_controller.disconnect_camera(camera_id)
            return None

    def add_manual_camera(self, camera_config: dict) -> str:
        """Adds a camera with manual configuration, with a connection test."""
        import cv2
        camera_id = str(uuid.uuid4())
        camera_config['id'] = camera_id
        camera_config['created_at'] = datetime.now().isoformat()
        camera_config['manual_setup'] = True

        # Construct RTSP URL if not provided
        if 'rtsp_url' not in camera_config or not camera_config['rtsp_url']:
            user = camera_config.get('username', '')
            pwd = camera_config.get('password', '')
            credentials = f"{user}:{pwd}@" if user and pwd else ""
            path = camera_config.get('rtsp_path', '/')
            rtsp_url = f"rtsp://{credentials}{camera_config['ip']}:{camera_config['rtsp_port']}{path}"
            camera_config['rtsp_url'] = rtsp_url
        else:
            rtsp_url = camera_config['rtsp_url']

        # Test the connection
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            logger.error(f"Could not open RTSP stream for manual camera: {rtsp_url}")
            cap.release()
            return None
        cap.release()

        if self.settings_manager.add_camera_config(camera_config):
            self._add_camera_from_config(camera_config)
            logger.info(f"Successfully added and saved new manual camera: {camera_config.get('name')}")
            return camera_id
        else:
            logger.error(f"Failed to save new manual camera to config: {camera_config.get('name')}")
            return None

    def update_camera(self, camera_id: str, camera_config: dict) -> bool:
        """Updates a camera's configuration."""
        if camera_id not in self.cameras:
            return False

        # Stop existing streams before updating
        self.stop_stream(camera_id)

        if self.settings_manager.update_camera_config(camera_id, camera_config):
            # Reload the camera from the updated config
            updated_config = self.settings_manager.get_camera_config(camera_id)
            if updated_config:
                self._add_camera_from_config(updated_config)
                logger.info(f"Successfully updated camera: {camera_config.get('name')}")
                return True

        logger.error(f"Failed to update camera config for ID: {camera_id}")
        return False

    def remove_camera(self, camera_id: str) -> bool:
        """Removes a camera from runtime and from the config file."""
        if camera_id in self.cameras:
            if camera_id in self.stream_processor.processes:
                self.stop_stream(camera_id)
            if self.recording_manager and camera_id in self.recording_manager.recording_processes:
                self.recording_manager.stop_recording(camera_id)

            # Remove from runtime
            del self.cameras[camera_id]
            self.onvif_controller.disconnect_camera(camera_id)

            # Remove from persistent config
            if self.settings_manager.remove_camera_config(camera_id):
                logger.info(f"Removed camera ID: {camera_id}")
                return True

        logger.warning(f"Attempted to remove non-existent camera ID: {camera_id}")
        return False

    def get_camera_status(self, camera_id: str) -> dict:
        """Gets the full status of a single camera."""
        if camera_id in self.cameras:
            camera = self.cameras[camera_id].copy()
            camera['stream_active'] = camera_id in self.stream_processor.processes
            if self.recording_manager:
                camera['recording'] = camera_id in self.recording_manager.recording_processes
            else:
                camera['recording'] = False
            return camera
        return {}

    def get_all_cameras(self) -> List[dict]:
        """Gets the full status of all cameras."""
        cameras_list = []
        for cam_id in self.cameras.keys():
            cameras_list.append(self.get_camera_status(cam_id))
        return cameras_list

    def start_stream(self, camera_id: str, profile_token: str = None) -> bool:
        if camera_id not in self.cameras:
            logger.error(f"Cannot start stream: camera ID {camera_id} not found.")
            return False

        if camera_id in self.stream_processor.processes:
            logger.warning(f"Stream for camera {camera_id} is already running.")
            return True

        camera_config = self.cameras[camera_id]

        # Use the saved profile token if it exists
        if not profile_token:
            profile_token = camera_config.get('profile_token')

        rtsp_uri = self.onvif_controller.get_stream_uri(camera_id, profile_token)
        if not rtsp_uri:
            rtsp_port = camera_config.get('rtsp_port', 554)
            rtsp_path = camera_config.get('rtsp_path', '/stream1')
            rtsp_uri = (f"rtsp://{camera_config['username']}:{camera_config['password']}"
                        f"@{camera_config['ip']}:{rtsp_port}{rtsp_path}")
            logger.warning(
                "Could not get RTSP URI from ONVIF for camera %s. Falling back to constructed URI: %s",
                camera_id, rtsp_uri
            )

        from pathlib import Path
        from config import HLS_OUTPUT_DIR
        output_dir = Path(HLS_OUTPUT_DIR) / camera_id
        logger.info(f"Attempting to start HLS stream for camera {camera_id} from {rtsp_uri}")

        success = self.stream_processor.start_hls_stream(
            rtsp_url=rtsp_uri,
            output_dir=output_dir,
            camera_id=camera_id,
            use_nvenc=self.settings_manager.get_setting('general.use_nvenc', True)
        )

        if success:
            self.cameras[camera_id]['status'] = 'streaming'
            logger.info(f"Successfully started stream for camera {camera_id}")
        else:
            self.cameras[camera_id]['status'] = 'error'
            logger.error(f"Failed to start stream for camera {camera_id}")

        return success

    def stop_stream(self, camera_id: str) -> bool:
        if camera_id not in self.stream_processor.processes:
            logger.warning("Attempted to stop a non-existent stream for camera %s", camera_id)
            return False

        success = self.stream_processor.stop_stream(camera_id)
        if success:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'connected'
            logger.info(f"Successfully stopped stream for camera {camera_id}")
        return success
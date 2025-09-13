import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, TYPE_CHECKING

from .stream_processor import StreamProcessor
from .onvif_controller import ONVIFController
from config import HLS_OUTPUT_DIR


if TYPE_CHECKING:
    from .recording_manager import RecordingManager

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, stream_processor: StreamProcessor, onvif_controller: ONVIFController):
        self.cameras: Dict[str, dict] = {}
        self.stream_processor = stream_processor
        self.onvif_controller = onvif_controller
        self.recording_manager: 'RecordingManager' = None

    def add_camera(self, camera_config: dict) -> str:
        camera_id = str(uuid.uuid4())
        camera_config['id'] = camera_id
        camera_config['created_at'] = datetime.now()
        # Initial status assumes we need to connect to get final status
        camera_config['status'] = 'disconnected'

        self.cameras[camera_id] = camera_config
        logger.info(f"Added camera '{camera_config.get('name', 'Unknown')}' with ID: {camera_id}")

        # Try to connect with ONVIF to get profiles right away
        # In a real app, this might be a separate step in the UI
        self.onvif_controller.connect_camera(
            camera_id,
            camera_config['ip'],
            camera_config.get('onvif_port', 80),
            camera_config['username'],
            camera_config['password']
        )

        return camera_id

    def remove_camera(self, camera_id: str) -> bool:
        if camera_id in self.cameras:
            if camera_id in self.stream_processor.processes:
                self.stop_stream(camera_id)
            del self.cameras[camera_id]
            self.onvif_controller.disconnect_camera(camera_id)
            logger.info(f"Removed camera ID: {camera_id}")
            return True
        return False

    def start_stream(self, camera_id: str, profile_token: str = "main") -> bool:
        if camera_id not in self.cameras:
            logger.error(f"Cannot start stream: camera ID {camera_id} not found.")
            return False

        if camera_id in self.stream_processor.processes:
            logger.warning(f"Stream for camera {camera_id} is already running.")
            return True

        camera_config = self.cameras[camera_id]

        # Get RTSP URI from ONVIF controller
        # In the future, this will use the profile_token to select the right stream
        rtsp_uri = self.onvif_controller.get_rtsp_uri(camera_id, profile_token)

        if not rtsp_uri:
            # As a fallback for non-ONVIF cameras, construct a potential RTSP URL
            # This is a guess and might not work for all cameras.
            rtsp_port = camera_config.get('rtsp_port', 554)
            rtsp_path = camera_config.get('rtsp_path', '/stream1')
            rtsp_uri = (f"rtsp://{camera_config['username']}:{camera_config['password']}"
                        f"@{camera_config['ip']}:{rtsp_port}{rtsp_path}")
            logger.warning(
                "Could not get RTSP URI from ONVIF for camera %s. Falling back to constructed URI: %s",
                camera_id, rtsp_uri
            )

        output_dir = Path(HLS_OUTPUT_DIR) / camera_id

        logger.info(f"Attempting to start HLS stream for camera {camera_id} from {rtsp_uri}")

        success = self.stream_processor.start_hls_stream(
            rtsp_url=rtsp_uri,
            output_dir=output_dir,
            camera_id=camera_id,
            use_nvenc=camera_config.get('use_nvenc', True)
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
            return False  # Return False as it wasn't running

        success = self.stream_processor.stop_stream(camera_id)
        if success:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'connected'  # or 'disconnected'
            logger.info(f"Successfully stopped stream for camera {camera_id}")
        return success

    def get_camera_status(self, camera_id: str) -> dict:
        if camera_id in self.cameras:
            camera = self.cameras[camera_id].copy()

            # Get stream and recording status from the respective managers
            camera['stream_active'] = camera_id in self.stream_processor.processes
            camera['recording'] = camera_id in self.recording_manager.recording_processes

            # Update status based on stream state if it's not already 'error'
            if camera['stream_active'] and camera['status'] != 'error':
                camera['status'] = 'streaming'
            elif not camera['stream_active'] and camera['status'] == 'streaming':
                # If stream processor doesn't have it, it's not streaming.
                # Revert to a more neutral status.
                camera['status'] = 'connected'

            return camera
        return {}

    def discover_cameras(self) -> List[dict]:
        """Uses ONVIF discovery to find cameras on the network."""
        logger.info("ONVIF camera discovery initiated.")
        discovered_devices = self.onvif_controller.discover()
        # This can be enhanced to return more details
        return discovered_devices

    def get_all_cameras(self) -> List[dict]:
        # Return a list of camera dicts, with updated status
        cameras_list = []
        for cam_id in self.cameras.keys():
            cameras_list.append(self.get_camera_status(cam_id))
        return cameras_list
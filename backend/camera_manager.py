import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, dict] = {}
        self.active_streams: Dict[str, dict] = {}
        
    def add_camera(self, camera_config: dict) -> str:
        camera_id = str(uuid.uuid4())
        camera_config['id'] = camera_id
        camera_config['created_at'] = datetime.now()
        camera_config['status'] = 'disconnected'
        
        self.cameras[camera_id] = camera_config
        logger.info(f"Added camera {camera_config.get('name', 'Unknown')} with ID: {camera_id}")
        return camera_id
    
    def remove_camera(self, camera_id: str) -> bool:
        if camera_id in self.cameras:
            if camera_id in self.active_streams:
                self.stop_stream(camera_id)
            del self.cameras[camera_id]
            logger.info(f"Removed camera ID: {camera_id}")
            return True
        return False
    
    def start_stream(self, camera_id: str, profile: str = "main") -> bool:
        if camera_id not in self.cameras:
            return False
        
        logger.info(f"Starting stream for camera {camera_id}, profile: {profile}")
        return True
    
    def stop_stream(self, camera_id: str) -> bool:
        if camera_id in self.active_streams:
            logger.info(f"Stopped stream for camera {camera_id}")
            return True
        return False
    
    def get_camera_status(self, camera_id: str) -> dict:
        if camera_id in self.cameras:
            camera = self.cameras[camera_id].copy()
            camera['stream_active'] = camera_id in self.active_streams
            return camera
        return {}
    
    def discover_cameras(self) -> List[dict]:
        discovered = []
        logger.info("Camera discovery initiated")
        return discovered
    
    def get_all_cameras(self) -> List[dict]:
        return list(self.cameras.values())
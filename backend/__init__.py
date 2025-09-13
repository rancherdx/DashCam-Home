"""
Camera Dashboard Backend Package
"""

__version__ = "1.0.0"
__author__ = "Camera Dashboard Team"

# Import main components for easier access
from .camera_manager import CameraManager
from .stream_processor import StreamProcessor
from .onvif_controller import ONVIFController
from .recording_manager import RecordingManager
from .motion_detector import MotionDetector
from .utils import (
    check_ffmpeg,
    guess_rtsp_url,
    validate_rtsp_url,
    setup_logging
)

# Package initialization
def init_package():
    """Initialize the backend package"""
    import logging
    from config import LOGS_DIR
    
    # Ensure logs directory exists
    import os
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Setup logging
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("Camera Dashboard backend package initialized")

# Export public API
__all__ = [
    'CameraManager',
    'StreamProcessor',
    'ONVIFController',
    'RecordingManager',
    'MotionDetector',
    'check_ffmpeg',
    'guess_rtsp_url',
    'validate_rtsp_url',
    'setup_logging',
    'init_package'
]

# Initialize when imported
init_package()
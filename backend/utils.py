import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

def check_ffmpeg() -> bool:
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def guess_rtsp_url(brand: str, ip: str, port: int, username: str, password: str) -> str:
    brand = brand.lower() if brand else ""
    
    if "hanwha" in brand or "samsung" in brand:
        return f"rtsp://{username}:{password}@{ip}:{port}/ONVIF/IF/profile2/media.SMP"
    elif "hikvision" in brand or "hik" in brand:
        return f"rtsp://{username}:{password}@{ip}:{port}/Streaming/Channels/101"
    elif "axis" in brand:
        return f"rtsp://{username}:{password}@{ip}:{port}/axis-media/media.amp"
    elif "dahua" in brand:
        return f"rtsp://{username}:{password}@{ip}:{port}/cam/realmonitor?channel=1&subtype=0"
    else:
        return f"rtsp://{username}:{password}@{ip}:{port}/stream1"

def validate_rtsp_url(url: str) -> bool:
    return url.startswith('rtsp://') and len(url) > 10

def setup_logging(log_level: str = "INFO"):
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/camera_dashboard.log"),
            logging.StreamHandler()
        ]
    )
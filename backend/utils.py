import logging
import logging.handlers
import os
import subprocess
from urllib.parse import urlparse

from config import LOGS_DIR

def setup_logging():
    """Sets up logging for the application."""
    log_file = os.path.join(LOGS_DIR, "camera_dashboard.log")

    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Set the formatter for the handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def check_ffmpeg():
    """Checks if ffmpeg is installed."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def validate_rtsp_url(rtsp_url):
    """Validates an RTSP URL."""
    # A simple validation by checking the scheme
    parsed_url = urlparse(rtsp_url)
    return parsed_url.scheme == "rtsp" and parsed_url.netloc != ""

def guess_rtsp_url(ip_address):
    """Guesses the RTSP URL for a given IP address."""
    # This is a placeholder. A real implementation would have a list of
    # common RTSP URL patterns for different camera manufacturers.
    return f"rtsp://{ip_address}:554/stream1"

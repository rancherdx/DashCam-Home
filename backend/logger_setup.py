import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOGS_DIR

def setup_logging():
    # Ensure logs directory exists
    os.makedirs(LOGS_DIR, exist_ok=True)

    # General application logger
    app_log_path = os.path.join(LOGS_DIR, 'app.log')
    app_handler = RotatingFileHandler(app_log_path, maxBytes=10*1024*1024, backupCount=5)
    app_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app_handler.setFormatter(app_formatter)

    # Root logger configuration
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.StreamHandler(), app_handler]
    )

    # --- Specific Loggers ---

    # Access logger for API requests
    access_logger = logging.getLogger('api.access')
    access_log_path = os.path.join(LOGS_DIR, 'access.log')
    access_handler = RotatingFileHandler(access_log_path, maxBytes=5*1024*1024, backupCount=3)
    access_formatter = logging.Formatter('%(asctime)s - %(message)s')
    access_handler.setFormatter(access_formatter)
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False # Do not propagate to root logger

    # Stream logger for stream events
    stream_logger = logging.getLogger('stream.events')
    stream_log_path = os.path.join(LOGS_DIR, 'streams.log')
    stream_handler = RotatingFileHandler(stream_log_path, maxBytes=5*1024*1024, backupCount=3)
    stream_formatter = logging.Formatter('%(asctime)s - %(message)s')
    stream_handler.setFormatter(stream_formatter)
    stream_logger.addHandler(stream_handler)
    stream_logger.setLevel(logging.INFO)
    stream_logger.propagate = False

    # Audit logger for user actions
    audit_logger = logging.getLogger('audit.events')
    audit_log_path = os.path.join(LOGS_DIR, 'audit.log')
    audit_handler = RotatingFileHandler(audit_log_path, maxBytes=5*1024*1024, backupCount=3)
    audit_formatter = logging.Formatter('%(asctime)s - %(message)s')
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    logger = logging.getLogger(__name__)
    logger.info("Logging configured with multiple handlers.")

def check_ffmpeg() -> bool:
    """Checks if FFmpeg is installed and accessible."""
    import subprocess
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

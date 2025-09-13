import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Storage settings
SNAPSHOT_RETENTION = timedelta(hours=7)
CLIP_RETENTION = timedelta(hours=7)
THUMBNAIL_REFRESH = 10  # seconds

# Camera settings
DEFAULT_RTSP_PORTS = [554, 8554, 10554]
DEFAULT_ONVIF_PORT = 80

# Stream settings
USE_NVENC = True
HLS_SEGMENT_TIME = 4
HLS_LIST_SIZE = 6

# Paths
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
SNAPSHOTS_DIR = os.path.join(STORAGE_DIR, "snapshots")
CLIPS_DIR = os.path.join(STORAGE_DIR, "clips")
THUMBNAILS_DIR = os.path.join(STORAGE_DIR, "thumbnails")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
HLS_OUTPUT_DIR = os.path.join(STORAGE_DIR, "streams")
os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

# Create directories
for directory in [STORAGE_DIR, SNAPSHOTS_DIR, CLIPS_DIR, THUMBNAILS_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)
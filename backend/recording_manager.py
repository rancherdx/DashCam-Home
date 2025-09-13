import logging
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .camera_manager import CameraManager
    from .settings_manager import SettingsManager

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit.events')


class RecordingManager:
    def __init__(self, snapshots_dir: str, clips_dir: str, thumbnails_dir: str, settings_manager: "SettingsManager"):
        self.snapshots_dir = Path(snapshots_dir)
        self.clips_dir = Path(clips_dir)
        self.thumbnails_dir = Path(thumbnails_dir)
        self.settings_manager = settings_manager
        self.camera_manager: "CameraManager" = None  # Injected after init

        self.recording_processes: Dict[str, subprocess.Popen] = {}

        self.cleanup_thread = threading.Thread(target=self._cleanup_old_files, daemon=True)
        self.cleanup_thread.start()

    def take_snapshot(self, camera_id: str) -> str:
        """Takes a snapshot from a camera stream using FFmpeg."""
        camera = self.camera_manager.get_camera_status(camera_id)
        if not camera:
            logger.error(f"Cannot take snapshot: camera {camera_id} not found.")
            return None

        rtsp_uri = self.camera_manager.onvif_controller.get_rtsp_uri(camera_id)
        if not rtsp_uri:
            rtsp_port = camera.get('rtsp_port', 554)
            rtsp_path = camera.get('rtsp_path', '/stream1')
            rtsp_uri = (f"rtsp://{camera['username']}:{camera['password']}"
                        f"@{camera['ip']}:{rtsp_port}{rtsp_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{timestamp}.jpg"
        filepath = self.snapshots_dir / filename

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_uri,
            "-vframes", "1",
            "-q:v", "2",  # High quality
            str(filepath)
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if process.returncode == 0:
                audit_logger.info(f"SNAPSHOT - Camera: {camera_id}, File: {filename}")
                return filename
            else:
                logger.error(f"FFmpeg failed to take snapshot for {camera_id}. Error: {process.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timed out while taking snapshot for {camera_id}.")
            return None
        except Exception as e:
            logger.error(f"Failed to save snapshot for {camera_id}: {e}")
            return None

    def start_recording(self, camera_id: str) -> str:
        """Starts a continuous recording for a camera stream."""
        if camera_id in self.recording_processes:
            logger.warning(f"Recording is already active for camera {camera_id}.")
            return None

        camera = self.camera_manager.get_camera_status(camera_id)
        if not camera:
            logger.error(f"Cannot start recording: camera {camera_id} not found.")
            return None

        rtsp_uri = self.camera_manager.onvif_controller.get_rtsp_uri(camera_id)
        if not rtsp_uri:
            rtsp_port = camera.get('rtsp_port', 554)
            rtsp_path = camera.get('rtsp_path', '/stream1')
            rtsp_uri = (f"rtsp://{camera['username']}:{camera['password']}"
                        f"@{camera['ip']}:{rtsp_port}{rtsp_path}")

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_uri,
            "-c", "copy",
            "-map", "0",
            "-f", "segment",
            "-segment_time", "600",
            "-segment_format", "mp4",
            "-strftime", "1",
            f"{str(self.clips_dir)}/{camera_id}_%Y%m%d-%H%M%S.mp4"
        ]

        try:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.recording_processes[camera_id] = process
            audit_logger.info(f"REC_START - Camera: {camera_id}")
            return f"{camera_id}_recording_active"
        except Exception as e:
            logger.error(f"Failed to start recording for {camera_id}: {e}")
            return None

    def stop_recording(self, camera_id: str) -> bool:
        """Stops an active recording process."""
        if camera_id not in self.recording_processes:
            logger.warning(f"No active recording to stop for camera {camera_id}.")
            return False

        process = self.recording_processes[camera_id]
        try:
            process.stdin.write(b'q')
            process.stdin.flush()
            process.wait(timeout=10)
            audit_logger.info(f"REC_STOP - Camera: {camera_id}")
        except (subprocess.TimeoutExpired, OSError):
            process.kill()
            logger.warning(f"Recording process for {camera_id} did not terminate gracefully, killing.")
        except Exception as e:
            logger.error(f"Error stopping recording for {camera_id}: {e}")

        del self.recording_processes[camera_id]
        return True

    def get_recordings(self, camera_id: str = None, hours: int = 7) -> List[dict]:
        recordings = []
        try:
            # Use retention period from settings, with 'hours' as a fallback
            retention_hours = self.settings_manager.get_setting('storage.retention_period_hours', hours)
            cutoff_time = datetime.now() - timedelta(hours=retention_hours)
            glob_pattern = f"{camera_id}_*.mp4" if camera_id else "*.mp4"
            for file in self.clips_dir.glob(glob_pattern):
                try:
                    file_mod_time = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_mod_time > cutoff_time:
                        recordings.append({
                            'filename': file.name,
                            'path': str(file),
                            'size': file.stat().st_size,
                            'created': file_mod_time.isoformat()
                        })
                except Exception as e:
                    logger.error(f"Could not process file {file.name}: {e}")
            return sorted(recordings, key=lambda x: x['created'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting recordings: {e}")
            return []

    def _cleanup_old_files(self):
        logger.info("Cleanup thread started.")
        while True:
            try:
                retention_hours = self.settings_manager.get_setting('storage.retention_period_hours', 7)
                if self.settings_manager.get_setting('storage.auto_cleanup', True):
                    cutoff_time = datetime.now() - timedelta(hours=retention_hours)
                    for directory in [self.snapshots_dir, self.clips_dir, self.thumbnails_dir]:
                        if not directory.exists():
                            continue
                        for file in directory.glob("*"):
                            try:
                                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_time:
                                    file.unlink()
                                    logger.info(f"Cleaned up old file: {file.name}")
                            except Exception as e:
                                logger.error(f"Error cleaning up file {file}: {e}")

                threading.Event().wait(3600)
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                threading.Event().wait(300)
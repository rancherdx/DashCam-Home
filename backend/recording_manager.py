import os
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

class RecordingManager:
    def __init__(self, snapshots_dir: str, clips_dir: str, thumbnails_dir: str):
        self.snapshots_dir = Path(snapshots_dir)
        self.clips_dir = Path(clips_dir)
        self.thumbnails_dir = Path(thumbnails_dir)
        
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_files, daemon=True)
        self.cleanup_thread.start()
    
    def take_snapshot(self, camera_id: str, image_data: bytes) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{timestamp}.jpg"
        filepath = self.snapshots_dir / filename
        
        try:
            with open(filepath, 'wb') as f:
                f.write(image_data)
            logger.info(f"Snapshot saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return None
    
    def start_recording(self, camera_id: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{timestamp}.mp4"
        return filename
    
    def get_recordings(self, camera_id: str = None, hours: int = 7) -> List[dict]:
        recordings = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for file in self.clips_dir.glob("*.mp4"):
            if camera_id and camera_id not in file.name:
                continue
                
            if file.stat().st_mtime > cutoff_time.timestamp():
                recordings.append({
                    'filename': file.name,
                    'path': str(file),
                    'size': file.stat().st_size,
                    'created': datetime.fromtimestamp(file.stat().st_mtime)
                })
        
        return sorted(recordings, key=lambda x: x['created'], reverse=True)
    
    def _cleanup_old_files(self):
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=7)
                
                for directory in [self.snapshots_dir, self.clips_dir, self.thumbnails_dir]:
                    for file in directory.glob("*"):
                        if file.stat().st_mtime < cutoff_time.timestamp():
                            file.unlink()
                            logger.info(f"Cleaned up old file: {file.name}")
                
                threading.Event().wait(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                threading.Event().wait(300)  # Wait 5 minutes on error
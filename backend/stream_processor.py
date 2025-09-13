# backend/stream_processor.py - Enhanced version
import subprocess
import threading
import logging
from pathlib import Path
from urllib.parse import urlparse
import secrets

logger = logging.getLogger(__name__)

class StreamProcessor:
    def __init__(self, cloudflare_enabled=False):
        self.processes = {}
        self.cloudflare_enabled = cloudflare_enabled
        self.stream_tokens = {}  # Store access tokens for streams
        
    def generate_stream_token(self, camera_id):
        """Generate a secure token for stream access"""
        token = secrets.token_urlsafe(16)
        self.stream_tokens[camera_id] = token
        return token
        
    def verify_stream_token(self, camera_id, token):
        """Verify a stream access token"""
        return self.stream_tokens.get(camera_id) == token
        
    def start_hls_stream(self, rtsp_url: str, output_dir: Path, camera_id: str, 
                        use_nvenc: bool = True, transport: str = "tcp") -> bool:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            index_file = output_dir / "index.m3u8"
            
            # For Cloudflare, we need to ensure proper CORS headers if serving directly
            # But better to serve through Flask with authentication
            
            cmd = [
                "ffmpeg", "-rtsp_transport", transport, 
                "-i", rtsp_url, "-hide_banner", "-loglevel", "warning"
            ]
            
            if use_nvenc:
                cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
                cmd.extend(["-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "2M"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-b:v", "2M"])
                
            # Add additional parameters for better HTTP streaming
            cmd.extend([
                "-c:a", "aac", "-b:a", "128k", 
                "-f", "hls",
                "-hls_time", "4", 
                "-hls_list_size", "6",
                "-hls_flags", "delete_segments+append_list",
                "-hls_segment_filename", str(output_dir / "seg%03d.ts"),
                "-hls_base_url", f"/streams/{camera_id}/",  # Important for relative paths
                str(index_file)
            ])
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.processes[camera_id] = process
            
            threading.Thread(target=self._monitor_process, args=(camera_id, process), daemon=True).start()
            
            logger.info(f"Started HLS stream for camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start stream for camera {camera_id}: {e}")
            return False
    
    # Rest of the class remains the same...
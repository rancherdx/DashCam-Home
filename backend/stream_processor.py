import subprocess
import threading
import logging
from pathlib import Path
import secrets
import time

logger = logging.getLogger(__name__)
stream_logger = logging.getLogger('stream.events')

class StreamProcessor:
    def __init__(self, cloudflare_enabled=False):
        self.processes = {}
        self.cloudflare_enabled = cloudflare_enabled
        self.stream_tokens = {}
        self.stream_start_times = {}

    def generate_stream_token(self, camera_id):
        token = secrets.token_urlsafe(16)
        self.stream_tokens[camera_id] = token
        return token

    def verify_stream_token(self, camera_id, token):
        return self.stream_tokens.get(camera_id) == token

    def start_hls_stream(self, rtsp_url: str, output_dir: Path, camera_id: str,
                         use_nvenc: bool = True, transport: str = "tcp") -> bool:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            index_file = output_dir / "index.m3u8"

            cmd = [
                "ffmpeg", "-rtsp_transport", transport,
                "-i", rtsp_url, "-hide_banner", "-loglevel", "warning"
            ]

            if use_nvenc:
                cmd.extend(["-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "2M"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-b:v", "2M"])

            cmd.extend([
                "-c:a", "aac", "-b:a", "128k",
                "-f", "hls", "-hls_time", "4", "-hls_list_size", "6",
                "-hls_flags", "delete_segments+append_list",
                "-hls_segment_filename", str(output_dir / "seg%03d.ts"),
                "-hls_base_url", f"/streams/{camera_id}/",
                str(index_file)
            ])

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.processes[camera_id] = process
            self.stream_start_times[camera_id] = time.time()

            threading.Thread(target=self._monitor_process, args=(camera_id, process), daemon=True).start()

            stream_logger.info(f"STREAM_START - Camera: {camera_id}, RTSP: {rtsp_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to start stream for camera {camera_id}: {e}")
            return False

    def stop_stream(self, camera_id: str) -> bool:
        if camera_id in self.processes:
            process = self.processes[camera_id]
            try:
                process.terminate()
                duration = time.time() - self.stream_start_times.get(camera_id, time.time())
                stream_logger.info(f"STREAM_STOP - Camera: {camera_id}, Duration: {duration:.2f}s")
            except Exception as e:
                logger.error(f"Error terminating process for camera {camera_id}: {e}")
                process.kill()

            if camera_id in self.processes:
                del self.processes[camera_id]
            if camera_id in self.stream_tokens:
                del self.stream_tokens[camera_id]
            if camera_id in self.stream_start_times:
                del self.stream_start_times[camera_id]
            return True
        return False

    def _monitor_process(self, camera_id: str, process: subprocess.Popen):
        process.wait()
        if camera_id in self.processes:
            duration = time.time() - self.stream_start_times.get(camera_id, time.time())
            stream_logger.error(f"STREAM_CRASH - Camera: {camera_id}, Code: {process.returncode}, Duration: {duration:.2f}s")
            del self.processes[camera_id]
            if camera_id in self.stream_tokens:
                del self.stream_tokens[camera_id]
            if camera_id in self.stream_start_times:
                del self.stream_start_times[camera_id]
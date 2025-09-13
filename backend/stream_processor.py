import subprocess
import threading
import logging
from pathlib import Path
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
                "-hls_base_url", f"/streams/{camera_id}/",
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

    def stop_stream(self, camera_id: str) -> bool:
        """Stops an active HLS stream process."""
        if camera_id in self.processes:
            process = self.processes[camera_id]
            try:
                process.terminate()  # Send SIGTERM
                logger.info(f"Sent terminate signal to FFmpeg process for camera {camera_id}.")
            except Exception as e:
                logger.error(f"Error terminating process for camera {camera_id}: {e}")
                process.kill()  # force kill

            # Clean up immediately from the main dictionary
            del self.processes[camera_id]
            if camera_id in self.stream_tokens:
                del self.stream_tokens[camera_id]

            return True
        else:
            logger.warning(f"Attempted to stop a non-existent stream for camera {camera_id}")
            return False

    def _monitor_process(self, camera_id: str, process: subprocess.Popen):
        """Monitors a subprocess, logs its output, and cleans up upon exit."""
        def log_output(pipe, log_level):
            try:
                for line in iter(pipe.readline, b''):
                    logger.log(log_level, f"FFMPEG (Cam {camera_id}): {line.decode().strip()}")
            finally:
                pipe.close()

        # Monitor stdout and stderr in separate threads to prevent blocking
        stdout_thread = threading.Thread(target=log_output, args=(process.stdout, logging.INFO))
        stderr_thread = threading.Thread(target=log_output, args=(process.stderr, logging.ERROR))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        process.wait()  # Wait for the process to complete

        stdout_thread.join()
        stderr_thread.join()

        # Check if it was stopped intentionally or if it crashed
        if camera_id in self.processes:
            logger.warning(
                "FFmpeg process for camera %s stopped unexpectedly with code %s.",
                camera_id, process.returncode
            )
            # Clean up resources if it wasn't a graceful stop via stop_stream
            del self.processes[camera_id]
            if camera_id in self.stream_tokens:
                del self.stream_tokens[camera_id]
        else:
            logger.info(f"FFmpeg process for camera {camera_id} has been stopped gracefully.")
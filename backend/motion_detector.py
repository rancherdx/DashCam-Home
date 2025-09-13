import cv2
import time
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .camera_manager import CameraManager
    from .recording_manager import RecordingManager
    from .settings_manager import SettingsManager

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit.events')

class MotionDetector:
    def __init__(self, camera_manager: "CameraManager", recording_manager: "RecordingManager", settings_manager: "SettingsManager"):
        self.camera_manager = camera_manager
        self.recording_manager = recording_manager
        self.settings_manager = settings_manager
        self.running = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.last_triggered = {}

    def start(self):
        """Starts the motion detection background thread."""
        if not self.running:
            self.running = True
            self.thread.start()
            logger.info("Motion detection service started.")

    def stop(self):
        """Stops the motion detection background thread."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        logger.info("Motion detection service stopped.")

    def _run(self):
        """The main loop for the motion detection service."""
        back_sub_algorithms = {}
        video_captures = {}

        while self.running:
            cameras = self.camera_manager.get_all_cameras()
            motion_settings = self.settings_manager.get_setting('motion', {})

            for camera in cameras:
                cam_id = camera.get('id')
                cam_motion_settings = motion_settings.get(cam_id, {})

                if not cam_motion_settings.get('enabled', False):
                    # If motion detection is disabled for this camera, release resources
                    if cam_id in video_captures:
                        video_captures[cam_id].release()
                        del video_captures[cam_id]
                        if cam_id in back_sub_algorithms:
                            del back_sub_algorithms[cam_id]
                    continue

                # Initialize capture and background subtractor if not already done
                if cam_id not in video_captures:
                    # Use a low-resolution stream for efficiency if available
                    rtsp_uri = self.camera_manager.onvif_controller.get_rtsp_uri(cam_id) # This could be enhanced
                    if not rtsp_uri:
                        continue

                    video_captures[cam_id] = cv2.VideoCapture(rtsp_uri)
                    back_sub_algorithms[cam_id] = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)
                    logger.info(f"Initialized motion detection for camera {cam_id}")

                cap = video_captures[cam_id]
                if not cap.isOpened():
                    continue

                ret, frame = cap.read()
                if not ret:
                    # If frame read fails, release and try to reconnect on the next cycle
                    cap.release()
                    del video_captures[cam_id]
                    if cam_id in back_sub_algorithms:
                        del back_sub_algorithms[cam_id]
                    continue

                # Apply background subtraction
                fg_mask = back_sub_algorithms[cam_id].apply(frame)

                # Basic noise reduction
                fg_mask = cv2.erode(fg_mask, None, iterations=2)
                fg_mask = cv2.dilate(fg_mask, None, iterations=2)

                # Find contours
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                motion_detected = False
                min_area = cam_motion_settings.get('min_area', 500)
                for contour in contours:
                    if cv2.contourArea(contour) > min_area:
                        motion_detected = True
                        break

                if motion_detected:
                    cooldown = cam_motion_settings.get('cooldown', 60)
                    last_seen = self.last_triggered.get(cam_id, 0)

                    if time.time() - last_seen > cooldown:
                        logger.info(f"Motion detected on camera {cam_id}. Triggering recording.")
                        audit_logger.info(f"MOTION_DETECTED - Camera: {cam_id}")
                        self.recording_manager.start_recording(cam_id)
                        self.last_triggered[cam_id] = time.time()

            time.sleep(0.1) # Process at ~10 FPS

        # Cleanup on exit
        for cap in video_captures.values():
            cap.release()
        logger.info("Motion detection loop finished.")
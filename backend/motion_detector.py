
import cv2
import numpy as np
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class MotionDetector:
    def __init__(self, sensitivity: float = 0.1, min_area: int = 500):
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2()
        self.motion_detected = False
        self.motion_callbacks = []
    
    def detect_motion(self, frame):
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply background subtraction
            fg_mask = self.background_subtractor.apply(gray)
            
            # Apply threshold
            _, thresh = cv2.threshold(fg_mask, 254, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > self.min_area:
                    motion_detected = True
                    break
            
            if motion_detected and not self.motion_detected:
                self._trigger_motion()
            
            self.motion_detected = motion_detected
            return motion_detected
            
        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return False
    
    def add_motion_callback(self, callback):
        self.motion_callbacks.append(callback)
    
    def _trigger_motion(self):
        timestamp = datetime.now()
        for callback in self.motion_callbacks:
            try:
                callback(timestamp)
            except Exception as e:
                logger.error(f"Motion callback error: {e}")
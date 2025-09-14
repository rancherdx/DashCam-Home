import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from onvif import ONVIFCamera
    ONVIF_AVAILABLE = True
except ImportError:
    ONVIF_AVAILABLE = False
    logger.warning("ONVIF support not available. Install onvif-zeep")

class ONVIFController:
    def __init__(self):
        self.clients: Dict[str, any] = {}

    def connect_camera(self, camera_id: str, host: str, port: int,
                      username: str, password: str) -> bool:
        if not ONVIF_AVAILABLE:
            return False

        try:
            client = ONVIFCamera(host, port, username, password)
            self.clients[camera_id] = client
            logger.info(f"Connected to ONVIF camera {camera_id} at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ONVIF camera {camera_id}: {e}")
            return False

    def get_stream_uri(self, camera_id: str, profile_token: str = None) -> Optional[str]:
        if camera_id not in self.clients:
            return None

        try:
            media_service = self.clients[camera_id].create_media_service()
            profiles = media_service.GetProfiles()

            if not profile_token:
                profile_token = profiles[0].token

            stream_uri = media_service.GetStreamUri({
                'StreamSetup': {
                    'Stream': 'RTP-Unicast',
                    'Transport': {'Protocol': 'RTSP'}
                },
                'ProfileToken': profile_token
            })

            return stream_uri.Uri
        except Exception as e:
            logger.error(f"Failed to get stream URI for camera {camera_id}: {e}")
            return None

    def get_profiles(self, camera_id: str) -> List[dict]:
        if camera_id not in self.clients:
            return []

        try:
            media_service = self.clients[camera_id].create_media_service()
            profiles = media_service.GetProfiles()

            return [{
                'token': profile.token,
                'name': profile.Name,
                'width': profile.VideoEncoderConfiguration.Resolution.Width,
                'height': profile.VideoEncoderConfiguration.Resolution.Height,
                'codec': profile.VideoEncoderConfiguration.Encoding
            } for profile in profiles]
        except Exception as e:
            logger.error(f"Failed to get profiles for camera {camera_id}: {e}")
            return []

    def ptz_control(self, camera_id: str, pan: float, tilt: float, zoom: float):
        if camera_id not in self.clients:
            return False

        try:
            ptz_service = self.clients[camera_id].create_ptz_service()
            status = ptz_service.GetStatus({'ProfileToken': self.get_profiles(camera_id)[0]['token']})

            ptz_service.ContinuousMove({
                'ProfileToken': self.get_profiles(camera_id)[0]['token'],
                'Velocity': {
                    'PanTilt': {'x': pan, 'y': tilt},
                    'Zoom': {'x': zoom}
                }
            })

            return True
        except Exception as e:
            logger.error(f"PTZ control failed for camera {camera_id}: {e}")
            return False

    def get_motion_detection_rules(self, camera_id: str, profile_token: str) -> List[dict]:
        """Gets motion detection rules for a specific profile."""
        if camera_id not in self.clients:
            return []

        try:
            analytics_service = self.clients[camera_id].create_analytics_service()
            rules = analytics_service.GetRules({'ConfigurationToken': profile_token})

            motion_rules = []
            for rule in rules:
                if 'Motion' in rule.Type:
                    # This is a simplified representation. The actual structure can be complex.
                    motion_rules.append({
                        'name': rule.Name,
                        'type': rule.Type,
                        'parameters': str(rule.Parameters) # Convert to string for simplicity
                    })
            return motion_rules
        except Exception as e:
            logger.error(f"Failed to get motion detection rules for camera {camera_id}: {e}")
            return []

    def disconnect_camera(self, camera_id: str):
        if camera_id in self.clients:
            # The onvif-zeep library doesn't have an explicit disconnect method,
            # so we just remove the client from our dictionary.
            del self.clients[camera_id]
            logger.info(f"Disconnected ONVIF client for camera {camera_id}")
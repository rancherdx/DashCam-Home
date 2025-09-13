import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from onvif import ONVIFCamera
    from wsdiscovery.discovery import WSDiscovery
    ONVIF_AVAILABLE = True
except ImportError:
    ONVIF_AVAILABLE = False
    logger.warning("ONVIF support not available. Install 'onvif-zeep' and 'wsdiscovery'.")


class ONVIFController:
    def __init__(self):
        self.clients: Dict[str, ONVIFCamera] = {}

    def connect_camera(self, camera_id: str, host: str, port: int,
                       username: str, password: str) -> bool:
        if not ONVIF_AVAILABLE:
            return False

        try:
            # The onvif-zeep library has a bug where it doesn't handle WSDL paths correctly
            # on some systems. Providing the path explicitly can help.
            import os
            from onvif.definition import SERVICES
            wsdl_dir = os.path.join(os.path.dirname(os.path.dirname(SERVICES['media']['wsdl'])), 'wsdl')

            client = ONVIFCamera(host, port, username, password, wsdl_dir=wsdl_dir)
            self.clients[camera_id] = client
            logger.info(f"Successfully connected to ONVIF camera {camera_id} at {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ONVIF camera {camera_id}: {e}")
            if camera_id in self.clients:
                del self.clients[camera_id]
            return False

    def disconnect_camera(self, camera_id: str):
        if camera_id in self.clients:
            # No explicit disconnect method in the library, just remove the client
            del self.clients[camera_id]
            logger.info(f"Disconnected from ONVIF camera {camera_id}")

    def get_rtsp_uri(self, camera_id: str, profile_token: str = None) -> Optional[str]:
        if camera_id not in self.clients:
            logger.warning(f"Cannot get RTSP URI: camera {camera_id} not connected.")
            return None

        try:
            media_service = self.clients[camera_id].create_media_service()
            profiles = media_service.GetProfiles()

            target_profile = None
            if profile_token:
                # Find profile by token if provided
                target_profile = next((p for p in profiles if p.token == profile_token), None)

            if not target_profile:
                # Default to the first profile if no token or token not found
                if profiles:
                    target_profile = profiles[0]
                else:
                    logger.error(f"No media profiles found for camera {camera_id}")
                    return None

            stream_setup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'TCP'}}
            uri_request = media_service.create_type('GetStreamUri')
            uri_request.ProfileToken = target_profile.token
            uri_request.StreamSetup = stream_setup

            stream_uri_response = media_service.GetStreamUri(uri_request)

            return stream_uri_response.MediaUri.Uri
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

    def ptz_control(self, camera_id: str, command: str, pan: float = 0.0, tilt: float = 0.0, zoom: float = 0.0):
        if camera_id not in self.clients:
            return False

        try:
            ptz_service = self.clients[camera_id].create_ptz_service()
            profiles = self.get_profiles(camera_id)
            if not profiles:
                logger.error(f"Cannot perform PTZ: No profiles found for camera {camera_id}")
                return False

            profile_token = profiles[0]['token']  # Use the first profile for now

            if command == 'move':
                ptz_service.ContinuousMove({
                    'ProfileToken': profile_token,
                    'Velocity': {
                        'PanTilt': {'x': pan, 'y': tilt},
                        'Zoom': {'x': zoom}
                    }
                })
            elif command == 'stop':
                ptz_service.Stop({
                    'ProfileToken': profile_token,
                    'PanTilt': True,
                    'Zoom': True
                })
            else:
                logger.warning(f"Unknown PTZ command: {command}")
                return False

            return True
        except Exception as e:
            logger.error(f"PTZ control failed for camera {camera_id}: {e}")
            return False

    def discover(self) -> List[dict]:
        if not ONVIF_AVAILABLE:
            return []

        try:
            wsd = WSDiscovery()
            wsd.start()
            services = wsd.searchServices(types=["http://www.onvif.org/ver10/device/wsdl/devicemgmt.wsdl"])
            wsd.stop()

            discovered_cameras = []
            for service in services:
                # XAddrs is a list of endpoint addresses, often just one
                ip_address = service.getXAddrs()[0].split('/')[2].split(':')[0]
                discovered_cameras.append({
                    'ip': ip_address,
                    'xaddrs': service.getXAddrs()
                })
            logger.info(f"Discovered {len(discovered_cameras)} ONVIF-compatible devices.")
            return discovered_cameras
        except Exception as e:
            logger.error(f"ONVIF discovery failed: {e}")
            return []
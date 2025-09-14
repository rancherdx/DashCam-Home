import json
import logging
import threading
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = Path(config_path)
        self._lock = threading.Lock()
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict:
        """Loads settings from the JSON file."""
        if not self.config_path.exists():
            logger.error(f"Configuration file not found at {self.config_path}. Please create it.")
            # Return a default structure to prevent crashes
            return {
                "general": {}, "storage": {}, "cloudflare": {}, "cameras": []
            }

        with self._lock:
            try:
                with open(self.config_path, 'r') as f:
                    settings = json.load(f)
                    logger.info("Successfully loaded settings.")
                    return settings
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading settings from {self.config_path}: {e}")
                return {
                    "general": {}, "storage": {}, "cloudflare": {}, "cameras": []
                }

    def _save_settings(self):
        """Saves the current settings to the JSON file."""
        with self._lock:
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(self.settings, f, indent=4)
                logger.info(f"Settings saved to {self.config_path}")
            except IOError as e:
                logger.error(f"Error saving settings to {self.config_path}: {e}")

    def get_all_settings(self) -> Dict:
        """Returns a copy of all current settings."""
        with self._lock:
            return self.settings.copy()

    def update_settings(self, new_settings: Dict):
        """
        Updates the settings with new values and saves them.
        This performs a deep merge for nested dictionaries.
        """
        with self._lock:
            for key, value in new_settings.items():
                if key in self.settings and isinstance(self.settings[key], dict) and isinstance(value, dict):
                    self.settings[key].update(value)
                else:
                    self.settings[key] = value
        self._save_settings()

    def get_camera_configs(self) -> List[Dict]:
        """Returns the list of camera configurations."""
        with self._lock:
            return self.settings.get('cameras', [])

    def add_camera_config(self, camera_config: Dict) -> bool:
        """Adds a new camera configuration and saves."""
        with self._lock:
            # Avoid adding duplicates based on name or IP
            existing_ips = {c.get('ip') for c in self.settings['cameras']}
            if camera_config.get('ip') in existing_ips:
                logger.warning(f"Camera with IP {camera_config.get('ip')} already exists.")
                return False

            self.settings['cameras'].append(camera_config)
        self._save_settings()
        return True

    def remove_camera_config(self, camera_id: str) -> bool:
        """Removes a camera configuration by its ID and saves."""
        with self._lock:
            initial_len = len(self.settings['cameras'])
            self.settings['cameras'] = [c for c in self.settings['cameras'] if c.get('id') != camera_id]
            removed = len(self.settings['cameras']) < initial_len

        if removed:
            self._save_settings()
            logger.info(f"Removed camera config with ID: {camera_id}")
        return removed

    def update_camera_config(self, camera_id: str, new_config: Dict) -> bool:
        """Updates an existing camera's configuration."""
        with self._lock:
            camera_found = False
            for i, cam in enumerate(self.settings['cameras']):
                if cam.get('id') == camera_id:
                    # Update the existing config with new values
                    self.settings['cameras'][i].update(new_config)
                    camera_found = True
                    break

        if camera_found:
            self._save_settings()
            logger.info(f"Updated camera config for ID: {camera_id}")
            return True
        else:
            logger.warning(f"Could not find camera with ID {camera_id} to update.")
            return False

    def get_setting(self, key_path: str, default=None):
        """
        Retrieves a nested setting using a dot-separated key path.
        Example: get_setting('storage.retention_period_hours')
        """
        with self._lock:
            keys = key_path.split('.')
            value = self.settings
            try:
                for key in keys:
                    value = value[key]
                return value
            except (KeyError, TypeError):
                return default

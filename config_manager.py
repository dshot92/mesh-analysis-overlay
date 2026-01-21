# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import shutil

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._init_paths()
        return cls._instance
    
    def _init_paths(self):
        self.addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_path = os.path.join(self.addon_dir, "CONFIG_DEFAULT.json")
        self.preference_path = os.path.join(self.addon_dir, "CONFIG_PREFERENCE.json")
        
        # Ensure preference file exists
        if not os.path.exists(self.preference_path):
            self.restore_factory_defaults()

    def load_config(self, use_preferences=True):
        """Load configuration. If use_preferences is True, loads from CONFIG_PREFERENCE.json, otherwise CONFIG_DEFAULT.json."""
        path = self.preference_path if use_preferences else self.default_path
        
        if not os.path.exists(path):
            if not use_preferences:
                # This should not happen if the addon is installed correctly
                return {}
            # Fallback to default if preference doesn't exist
            path = self.default_path
            
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If preference is corrupted, return default
            if use_preferences:
                return self.load_config(use_preferences=False)
            return {}

    def save_preferences(self, config_data):
        """Save configuration to CONFIG_PREFERENCE.json. Only specified keys will be updated if it's a partial update."""
        try:
            # We always save the full current state to preferences
            with open(self.preference_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            return True
        except IOError:
            return False

    def restore_factory_defaults(self):
        """Copy CONFIG_DEFAULT.json to CONFIG_PREFERENCE.json."""
        try:
            if os.path.exists(self.default_path):
                shutil.copy2(self.default_path, self.preference_path)
                return True
        except IOError:
            pass
        return False

    def get_metadata(self):
        """Retrieve the metadata (ID, Label, Description) for all features."""
        config = self.load_config(use_preferences=False)
        return config.get("metadata", {})

# Singleton instance
config_manager = ConfigManager()

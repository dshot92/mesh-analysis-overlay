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

        # Cached metadata to avoid disk I/O on every overlay update / panel draw.
        self._metadata_cache = None
        self._metadata_mtime = 0.0
        self._all_feature_ids_cache = None

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
        """Retrieve the metadata (ID, Label, Description) for all features.

        Cached in memory; reloaded only when CONFIG_DEFAULT.json mtime changes.
        Callers must treat the return value as read-only.
        """
        try:
            mtime = os.path.getmtime(self.default_path)
        except OSError:
            mtime = 0.0
        if self._metadata_cache is None or mtime != self._metadata_mtime:
            config = self.load_config(use_preferences=False)
            self._metadata_cache = config.get("metadata", {})
            self._metadata_mtime = mtime
            self._all_feature_ids_cache = None
        return self._metadata_cache

    def get_all_feature_ids(self):
        """Flat list of every feature id across categories. Cached."""
        if self._all_feature_ids_cache is None:
            metadata = self.get_metadata()
            ids = []
            for _category, features in metadata.items():
                for feature in features:
                    ids.append(feature["id"])
            self._all_feature_ids_cache = ids
        return self._all_feature_ids_cache

    def invalidate_metadata_cache(self):
        """Force reload of metadata on next get_metadata() call."""
        self._metadata_cache = None
        self._metadata_mtime = 0.0
        self._all_feature_ids_cache = None

    def apply_config_to_scene(self, props, config):
        """Apply colors + overlay_settings from a config dict to scene props.

        Used by restore-preferences flows and headless tests. Missing keys
        are ignored; returns True on success.
        """
        try:
            colors = config.get("colors", {})
            for feature_id, color in colors.items():
                prop_name = f"{feature_id}_color"
                if hasattr(props, prop_name):
                    try:
                        dst = getattr(props, prop_name)
                        # Blender FloatVectorProperty supports indexed assignment.
                        for i in range(min(4, len(color))):
                            try:
                                dst[i] = float(color[i])
                            except Exception:
                                pass
                    except Exception:
                        try:
                            setattr(props, prop_name, tuple(color))
                        except Exception:
                            pass
            settings = config.get("overlay_settings", {})
            for key in ("overlay_offset", "overlay_vertex_radius",
                        "overlay_edge_width", "non_planar_threshold"):
                if key in settings and hasattr(props, key):
                    try:
                        setattr(props, key, settings[key])
                    except Exception:
                        pass
            return True
        except Exception:
            return False

# Singleton instance
config_manager = ConfigManager()

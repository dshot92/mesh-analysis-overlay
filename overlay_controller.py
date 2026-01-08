# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import numpy as np
from typing import Dict, Set
from bpy.types import Object

from .analysis_engine import MeshAnalysisEngine
from .render_pipeline import RenderPipeline, PrimitiveType
from .feature_data import FEATURE_DATA


class OverlayController:
    """Main controller coordinating analysis and rendering for multiple objects"""

    def __init__(self):
        self.analysis_engine = MeshAnalysisEngine()
        self.render_pipeline = RenderPipeline()
        self.displayed_objects: Set[str] = set()
        self.is_running = False

    def start(self):
        if self.is_running:
            return

        self.is_running = True
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.start()
        self.update_all_selected()

    def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        self.render_pipeline.stop()
        self.displayed_objects.clear()

    def update_all_selected(self):
        if not self.is_running:
            return

        selected_meshes = [
            obj for obj in bpy.context.selected_objects if obj.type == "MESH"
        ]
        current_names = {obj.name for obj in selected_meshes}
        to_remove = self.displayed_objects - current_names
        for name in to_remove:
            self.render_pipeline.clear_object_data(name)
        self.displayed_objects = current_names

        for obj in selected_meshes:
            self.update_overlay(obj)

    def update_overlay(self, obj: Object, analysis_mode: str = "OBJECT"):
        """Update overlay for a specific object - called by handlers only"""
        if not self.is_running or not obj or obj.type != "MESH":
            return

        self.displayed_objects.add(obj.name)

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        enabled_features = []
        feature_colors = {}
        all_feature_ids = []

        # Get all possible feature IDs and enabled ones
        for category, features in FEATURE_DATA.items():
            for feature in features:
                f_id = feature["id"]
                all_feature_ids.append(f_id)
                if getattr(props, f"{f_id}_enabled", False):
                    enabled_features.append(f_id)
                    feature_colors[f_id] = tuple(getattr(props, f"{f_id}_color"))

        # Clear data for disabled features that might have been previously enabled
        for f_id in all_feature_ids:
            if f_id not in enabled_features:
                self.render_pipeline.update_feature_data(
                    obj.name,
                    f_id,
                    np.array([]),
                    np.array([]),
                    np.array([]),
                    PrimitiveType.POINTS,
                )

        # Get GPU-ready data from analysis engine (handles everything)
        gpu_results = self.analysis_engine.analyze_and_format_mesh(obj, enabled_features, feature_colors, analysis_mode)

        # Update render pipeline with formatted data
        for f_id in enabled_features:
            if f_id in gpu_results:
                gpu_data = gpu_results[f_id]
                self.render_pipeline.update_feature_data(
                    obj.name, f_id, gpu_data.vertices, gpu_data.normals, gpu_data.colors, gpu_data.primitive_type
                )
            else:
                # Clear feature data if not found
                self.render_pipeline.update_feature_data(
                    obj.name,
                    f_id,
                    np.array([]),
                    np.array([]),
                    np.array([]),
                    PrimitiveType.POINTS,
                )
                

    def get_mesh_stats(self, obj: Object) -> Dict[str, int]:
        return self.analysis_engine.get_mesh_stats(obj)

    def clear_all_cache(self):
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.clear_all()
        self.displayed_objects.clear()


# Global instance
overlay_controller = OverlayController()

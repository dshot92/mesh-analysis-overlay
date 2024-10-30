# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import logging

from gpu_extras.batch import batch_for_shader
from typing import List, Tuple
from mathutils import Vector
from bpy.types import Object

from .mesh_analyzer import MeshAnalyzer


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Add at the top level, before the GPUDrawer class
_GLOBAL_ANALYZER_CACHE = []
_GLOBAL_CACHE_SIZE = 5


class GPUDrawer:
    def __init__(self):
        logger.debug("=== GPUDrawer Initialization ===")
        self.shader = gpu.shader.from_builtin("FLAT_COLOR")
        self.batches = {}
        self.is_running = False
        self._handle = None
        self._current_analyzer = None
        logger.debug(f"Initial state:")
        logger.debug(f"- Is running: {self.is_running}")
        logger.debug(f"- Handle: {self._handle}")
        logger.debug(f"- Current analyzer: {self._current_analyzer}")

    def _get_analyzer(self, obj: Object) -> MeshAnalyzer:
        """Get or create MeshAnalyzer instance for object"""
        # Check if object already has an analyzer in cache
        for analyzer in _GLOBAL_ANALYZER_CACHE:
            if analyzer.obj == obj:
                logger.debug(f"✓ Cache hit for {obj.name}")
                self._current_analyzer = analyzer
                return analyzer

        logger.debug(f"× Cache miss for {obj.name}")
        # Create new analyzer
        self._current_analyzer = MeshAnalyzer(obj)

        # Add to cache, removing oldest if at capacity
        if len(_GLOBAL_ANALYZER_CACHE) >= _GLOBAL_CACHE_SIZE:
            _GLOBAL_ANALYZER_CACHE.pop(0)  # Remove oldest

        # Add new analyzer to end of list
        _GLOBAL_ANALYZER_CACHE.append(self._current_analyzer)
        return self._current_analyzer

    def update_feature_batch(
        self,
        feature: str,
        verts: List[Vector],
        normals: List[Vector],
        color: Tuple[float, float, float, float],
        primitive_type: str,
    ):
        if not verts:
            return

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset = props.overlay_offset if hasattr(props, "overlay_offset") else 0.0

        offset_verts = []
        for v, n in zip(verts, normals):
            normal = n.normalized()
            offset_pos = v + (normal * offset)
            offset_verts.append(offset_pos)

        # Create color array matching vertex count
        colors = [color] * len(offset_verts)

        try:
            batch = batch_for_shader(
                self.shader,
                primitive_type,
                {
                    "pos": offset_verts,
                    "color": colors,  # FLAT_COLOR shader requires per-vertex colors
                },
            )
            self.batches[feature] = {"batch": batch, "color": color}
        except Exception as e:
            logger.debug(f"[ERROR] Failed to create batch: {str(e)}")

    def draw(self):
        if not self.is_running:
            return

        obj = bpy.context.active_object
        if not obj or obj.type != "MESH":
            return

        # Set GPU state
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.face_culling_set("BACK")
        gpu.state.point_size_set(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_vertex_radius
        )
        gpu.state.line_width_set(
            bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_edge_width
        )

        # logger.debug("\n=== Draw Call ===")
        # logger.debug(f"Object: {obj.name}")
        # logger.debug(f"Batch count: {len(self.batches)}")

        if (
            not self.batches
            or self._current_analyzer is None
            or self._current_analyzer.obj != obj
        ):
            # logger.debug("Forcing batch update...")
            self.update_batches(obj)

        # logger.debug("Drawing batches...")
        self.shader.bind()
        for feature, batch_data in self.batches.items():
            # logger.debug(f"- Drawing {feature}")
            batch_data["batch"].draw(self.shader)

        # Reset GPU state
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")

    def _update_all_batches(self, obj):
        """Update all batches based on current object state"""
        if not obj or not self.is_running:
            return

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        analyzer = self._get_analyzer(obj)  # This is correct - using cached analyzer
        self.batches.clear()

        feature_configs = [
            (analyzer.face_features, "TRIS"),
            (analyzer.edge_features, "LINES"),
            (analyzer.vertex_features, "POINTS"),
        ]

        for feature_set, primitive_type in feature_configs:
            self._update_feature_set(feature_set, primitive_type, props, analyzer)

    def _update_feature_set(self, feature_set, primitive_type, props, analyzer):
        for feature in feature_set:
            if not getattr(props, f"show_{feature}", False):
                continue

            verts, normals = analyzer.analyze_feature(feature)
            if verts:
                color = tuple(getattr(props, f"{feature}_color"))
                self.update_feature_batch(
                    feature, verts, normals, color, primitive_type
                )

    def _handle_mode_change(self, obj):
        """Handle object mode changes"""
        if not obj or not self.is_running:
            return False

        # Force update when:
        # 1. Exiting edit mode
        # 2. Entering object mode
        # 3. Switching between edit/object modes
        if obj.mode in {"OBJECT", "EDIT"}:
            logger.debug(f"[DEBUG] Mode change detected: {obj.mode}")
            self._update_all_batches(obj)
            return True
        return False

    def start(self):
        logger.debug("\n=== Starting GPUDrawer ===")
        self.is_running = True
        if not self._handle:
            logger.debug("Adding draw handler...")
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            logger.debug(f"Draw handler added: {self._handle}")

        obj = bpy.context.active_object
        if obj and obj.type == "MESH":
            logger.debug(f"Initial update for {obj.name}")
            self.update_batches(obj)

    def stop(self):
        logger.debug("\n=== Stopping GPUDrawer ===")
        logger.debug(f"Current state:")
        logger.debug(f"- Is running: {self.is_running}")
        logger.debug(f"- Handle: {self._handle}")
        logger.debug(f"- Batch count: {len(self.batches)}")

        if not self.is_running:
            logger.debug("Already stopped")
            return

        self.is_running = False
        if self._handle:
            logger.debug("Removing draw handler...")
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        logger.debug("Cleaning up...")
        self.batches.clear()
        self._current_analyzer = None
        MeshAnalyzer._cache.clear()
        logger.debug("Cleanup complete")

    def update_batches(self, obj):
        logger.debug("\n=== Update Batches ===")
        logger.debug(f"Object: {obj.name if obj else 'None'}")
        logger.debug(f"Is running: {self.is_running}")

        if not obj or not self.is_running:
            logger.debug("× Skipping update - invalid state")
            return

        logger.debug("Getting analyzer...")
        analyzer = self._get_analyzer(obj)
        logger.debug(f"Current batch count: {len(self.batches)}")
        logger.debug("Clearing batches...")
        self.batches.clear()

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        # Update face overlays
        logger.debug("\nProcessing face features:")
        for feature in analyzer.face_features:
            if getattr(props, f"show_{feature}", False):
                logger.debug(f"- Analyzing {feature}")
                verts, normals = analyzer.analyze_feature(feature)
                if verts:
                    logger.debug(f"  ✓ Found {len(verts)} vertices")
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, verts, normals, color, "TRIS")

        # Update edge overlays
        logger.debug("\nProcessing edge features:")
        for feature in analyzer.edge_features:
            if getattr(props, f"show_{feature}", False):
                logger.debug(f"- Analyzing {feature}")
                verts, normals = analyzer.analyze_feature(feature)
                if verts:
                    logger.debug(f"  ✓ Found {len(verts)} vertices")
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, verts, normals, color, "LINES")

        # Update vertex overlays
        logger.debug("\nProcessing vertex features:")
        for feature in analyzer.vertex_features:
            if getattr(props, f"show_{feature}", False):
                logger.debug(f"- Analyzing {feature}")
                verts, normals = analyzer.analyze_feature(feature)
                if verts:
                    logger.debug(f"  ✓ Found {len(verts)} vertices")
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, verts, normals, color, "POINTS")

        logger.debug(f"\nFinal batch count: {len(self.batches)}")


# Create and export the drawer instance
drawer = GPUDrawer()
__all__ = ["drawer", "GPUDrawer"]

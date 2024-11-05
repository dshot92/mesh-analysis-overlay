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
        # Simply create a new analyzer instance
        self._current_analyzer = MeshAnalyzer(obj)
        return self._current_analyzer

    def update_feature_batch(
        self,
        feature: str,
        indices: List[int],
        color: Tuple[float, float, float, float],
        primitive_type: str,
    ):
        if not indices:
            return

        try:
            # Get batch directly from analyzer
            batch_data = self._current_analyzer.get_batch(
                feature, indices, primitive_type
            )
            if not batch_data:
                return

            # Create shader for offset rendering
            vertex_shader = """
                uniform mat4 viewMatrix;
                uniform mat4 windowMatrix;
                uniform vec3 viewOrigin;
                uniform float normal_offset;
                
                in vec3 pos;
                in vec3 normal;
                
                void main() {
                    vec3 world_pos = pos;
                    float offset_amount = distance(world_pos, viewOrigin) * normal_offset;
                    vec3 offset_pos = world_pos + (normal * offset_amount);
                    gl_Position = windowMatrix * viewMatrix * vec4(offset_pos, 1.0);
                }
            """

            fragment_shader = """
                uniform vec4 color;
                out vec4 fragColor;
                
                void main() {
                    fragColor = color;
                }
            """

            shader = gpu.types.GPUShader(vertex_shader, fragment_shader)

            # Create batch with the shader
            batch = batch_for_shader(
                shader,
                primitive_type,
                {"pos": batch_data["positions"], "normal": batch_data["normals"]},
            )

            self.batches[feature] = {"batch": batch, "shader": shader, "color": color}

        except (AttributeError, IndexError, ReferenceError) as e:
            print(f"Error in update_feature_batch: {e}")
            self.batches.clear()
            return

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

        if (
            not self.batches
            or self._current_analyzer is None
            or self._current_analyzer.obj != obj
        ):
            self.update_batches(obj)

        # Draw batches
        for feature, batch_data in self.batches.items():
            shader = batch_data["shader"]
            shader.bind()

            # Set uniforms for the shader
            matrix = bpy.context.region_data.perspective_matrix
            shader.uniform_float("viewMatrix", bpy.context.region_data.view_matrix)
            shader.uniform_float("windowMatrix", bpy.context.region_data.window_matrix)
            shader.uniform_float(
                "viewOrigin", bpy.context.region_data.view_matrix.inverted().translation
            )
            shader.uniform_float(
                "normal_offset",
                bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_offset,
            )
            shader.uniform_float("color", batch_data["color"])

            batch_data["batch"].draw(shader)

        # Reset GPU state
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")

    def _update_feature_set(self, feature_set, primitive_type, props, analyzer):
        for feature in feature_set:
            if not getattr(props, f"{feature}_enabled", False):
                continue

            # Use MeshAnalyzer's feature sets directly
            if (
                (primitive_type == "TRIS" and feature in MeshAnalyzer.face_features)
                or (primitive_type == "LINES" and feature in MeshAnalyzer.edge_features)
                or (
                    primitive_type == "POINTS"
                    and feature in MeshAnalyzer.vertex_features
                )
            ):
                indices = analyzer.analyze_feature(feature)
                if indices:
                    color = tuple(getattr(props, f"{feature}_color"))
                    self.update_feature_batch(feature, indices, color, primitive_type)

    def _update_all_batches(self, obj):
        if not obj or not self.is_running:
            return

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        analyzer = self._get_analyzer(obj)
        self.batches.clear()

        feature_configs = [
            (MeshAnalyzer.face_features, "TRIS"),
            (MeshAnalyzer.edge_features, "LINES"),
            (MeshAnalyzer.vertex_features, "POINTS"),
        ]

        for feature_set, primitive_type in feature_configs:
            self._update_feature_set(feature_set, primitive_type, props, analyzer)

    def _handle_mode_change(self, obj):
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
        logger.debug("Cleanup complete")

    def get_primitive_type(self, feature: str) -> str:
        if feature in MeshAnalyzer.face_features:
            return "TRIS"
        elif feature in MeshAnalyzer.edge_features:
            return "LINES"
        elif feature in MeshAnalyzer.vertex_features:
            return "POINTS"
        return None

    def update_batches(self, obj, features=None):
        logger.debug("\n=== Update Batches ===")
        logger.debug(f"Object: {obj.name if obj else 'None'}")
        logger.debug(f"Updating features: {features if features else 'all'}")

        if not obj or not self.is_running:
            logger.debug("× Skipping update - invalid state")
            return

        analyzer = self._get_analyzer(obj)
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

        if not features:
            # Full update - clear all batches and update everything
            self._update_all_batches(obj)
        else:
            # Clear only specified features
            for feature in features:
                if feature in self.batches:
                    del self.batches[feature]

                # Only update the specified feature
                if getattr(props, f"{feature}_enabled", False):
                    indices = analyzer.analyze_feature(feature)
                    if indices:
                        color = tuple(getattr(props, f"{feature}_color"))
                        primitive_type = self.get_primitive_type(feature)
                        self.update_feature_batch(
                            feature, indices, color, primitive_type
                        )

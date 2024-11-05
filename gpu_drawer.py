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
            obj = bpy.context.active_object
            if not obj or obj.type != "MESH":
                return

            analyzer = MeshAnalyzer.get_analyzer(obj)
            batch_data = analyzer.get_batch(feature, indices, primitive_type)
            if not batch_data:
                return

            # Use different shaders based on primitive type
            if primitive_type == "POINTS":
                vertex_shader = """
                    uniform mat4 viewMatrix;
                    uniform mat4 windowMatrix;
                    uniform vec3 viewOrigin;
                    uniform float normal_offset;
                    
                    in vec3 pos;
                    in vec3 normal;

                    void main()
                    {
                        vec3 world_pos = pos;
                        float offset_amount = distance(world_pos, viewOrigin) * normal_offset;
                        vec3 offset_pos = world_pos + (normal * offset_amount);
                        gl_Position = windowMatrix * viewMatrix * vec4(offset_pos, 1.0);
                    }
                """

                fragment_shader = """
                    uniform vec4 color;
                    out vec4 fragColor;

                    void main()
                    {
                        vec2 center = vec2(0.5, 0.5);
                        float radius = 0.5;
                        vec2 position = gl_PointCoord - center;
                        float distance = length(position);
                        
                        if (distance > radius)
                        {
                            discard;
                        }
                        
                        fragColor = color;
                    }
                """
                shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
                batch = batch_for_shader(
                    shader,
                    primitive_type,
                    {"pos": batch_data["positions"], "normal": batch_data["normals"]},
                )
            else:
                # Original shader for edges and faces
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

        # Draw existing batches
        for feature, batch_data in self.batches.items():
            shader = batch_data["shader"]
            shader.bind()

            # Set uniforms based on primitive type
            if feature in MeshAnalyzer.vertex_features:
                # For vertex shader (points)
                shader.uniform_float("viewMatrix", bpy.context.region_data.view_matrix)
                shader.uniform_float(
                    "windowMatrix", bpy.context.region_data.window_matrix
                )
                shader.uniform_float(
                    "viewOrigin",
                    bpy.context.region_data.view_matrix.inverted().translation,
                )
                shader.uniform_float(
                    "normal_offset",
                    bpy.context.scene.Mesh_Analysis_Overlay_Properties.overlay_offset,
                )
            else:
                # For edge/face shader
                shader.uniform_float("viewMatrix", bpy.context.region_data.view_matrix)
                shader.uniform_float(
                    "windowMatrix", bpy.context.region_data.window_matrix
                )
                shader.uniform_float(
                    "viewOrigin",
                    bpy.context.region_data.view_matrix.inverted().translation,
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

    def start(self):
        logger.debug("\n=== Starting GPUDrawer ===")
        self.is_running = True
        if not self._handle:
            logger.debug("Adding draw handler...")
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            logger.debug(f"Draw handler added: {self._handle}")

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
        logger.debug("Cleanup complete")

    def get_primitive_type(self, feature: str) -> str:
        if feature in MeshAnalyzer.face_features:
            return "TRIS"
        elif feature in MeshAnalyzer.edge_features:
            return "LINES"
        elif feature in MeshAnalyzer.vertex_features:
            return "POINTS"
        return None

    # def update_batches(self, obj, features=None):
    #     logger.debug("\n=== Update Batches ===")
    #     logger.debug(f"Object: {obj.name if obj else 'None'}")
    #     logger.debug(f"Updating features: {features if features else 'all'}")

    #     if not obj or not self.is_running:
    #         logger.debug("× Skipping update - invalid state")
    #         return

    #     analyzer = self._get_analyzer(obj)
    #     props = bpy.context.scene.Mesh_Analysis_Overlay_Properties

    #     if not features:
    #         # Full update - clear all batches and update everything
    #         self._update_all_batches(obj)
    #     else:
    #         # Clear only specified features
    #         for feature in features:
    #             if feature in self.batches:
    #                 del self.batches[feature]

    #             # Only update the specified feature
    #             if getattr(props, f"{feature}_enabled", False):
    #                 indices = analyzer.analyze_feature(feature)
    #                 if indices:
    #                     color = tuple(getattr(props, f"{feature}_color"))
    #                     primitive_type = self.get_primitive_type(feature)
    #                     self.update_feature_batch(
    #                         feature, indices, color, primitive_type
    #                     )

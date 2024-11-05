# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import logging

from .feature_data import FEATURE_DATA

from gpu_extras.batch import batch_for_shader
from typing import List, Tuple

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
        self.current_obj = None

    def update_feature_batch(
        self,
        feature: str,
        indices: List[int],
        color: Tuple[float, float, float, float],
        primitive_type: str,
    ):
        print(f"Updating batch for {feature} with {len(indices)} indices")
        if not indices:
            print("No indices to draw")
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
                    uniform float normal_offset;
                    
                    in vec3 pos;
                    in vec3 normal;

                    void main()
                    {
                        vec3 world_pos = pos;
                        vec3 offset_pos = world_pos + (normal * normal_offset);
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
                    uniform float normal_offset;
                    
                    in vec3 pos;
                    in vec3 normal;
                    
                    void main() {
                        vec3 world_pos = pos;
                        vec3 offset_pos = world_pos + (normal * normal_offset);
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

        # Handle object switching
        if obj != self.current_obj:
            self.handle_object_switch(obj)
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

            shader.uniform_float("viewMatrix", bpy.context.region_data.view_matrix)
            shader.uniform_float("windowMatrix", bpy.context.region_data.window_matrix)
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

    def handle_object_switch(self, new_obj):
        self.current_obj = new_obj

        # Get analyzer for new object
        analyzer = MeshAnalyzer.get_analyzer(new_obj)

        # Clear current batches
        self.batches.clear()

        # Update analysis and batches for enabled features
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        for category in FEATURE_DATA.values():
            for feature in category:
                if getattr(props, f"{feature['id']}_enabled", False):
                    indices = analyzer.analyze_feature(feature["id"])
                    if indices:
                        primitive_type = MeshAnalyzer.get_primitive_type(feature["id"])
                        color = tuple(getattr(props, f"{feature['id']}_color"))
                        self.update_feature_batch(
                            feature["id"], indices, color, primitive_type
                        )

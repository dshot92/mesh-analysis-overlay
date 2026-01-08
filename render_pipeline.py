# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import numpy as np
from typing import Dict, Set
from gpu_extras.batch import batch_for_shader
from bpy.types import Object

from dataclasses import dataclass
from enum import Enum


class PrimitiveType(Enum):
    POINTS = "POINTS"
    LINES = "LINES"
    TRIS = "TRIS"


@dataclass
class RenderData:
    """GPU-ready render data for a feature"""

    vertices: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive_type: PrimitiveType
    count: int = 0

    def __post_init__(self):
        self.count = len(self.vertices)


class RenderPipeline:
    """Modern rendering pipeline using native POINT shaders"""

    def __init__(self):
        # Shaders for different primitive types
        self.shaders = {
            PrimitiveType.TRIS: None,
            PrimitiveType.LINES: None,
            PrimitiveType.POINTS: None,
        }
        # Nested dict: obj_name -> feature_id -> RenderData
        self.render_data: Dict[str, Dict[str, RenderData]] = {}
        # Nested dict: obj_name -> feature_id -> GPU Batch
        self.gpu_batches: Dict[str, Dict[str, any]] = {}
        self.is_running = False
        self._handle = None
        # Track objects that need batch rebuilding
        self._dirty_objects: Set[str] = set()

    def _ensure_shaders(self):
        """Initialize specialized shaders using official builtins"""
        if self.shaders[PrimitiveType.TRIS] is None:
            # Standard smooth color for triangles
            self.shaders[PrimitiveType.TRIS] = gpu.shader.from_builtin("FLAT_COLOR")

            # Polyline shader for consistent width
            self.shaders[PrimitiveType.LINES] = gpu.shader.from_builtin( "POLYLINE_FLAT_COLOR")

            # Native Point shader for vertices
            # In Blender 4.x/5.x, POINT_FLAT_COLOR is the correct builtin
            self.shaders[PrimitiveType.POINTS] = gpu.shader.from_builtin( "POINT_FLAT_COLOR")

    def start(self):
        """Start the render pipeline"""
        if self.is_running:
            return

        self.is_running = True
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), "WINDOW", "POST_VIEW"
        )

    def stop(self):
        """Stop the render pipeline"""
        if not self.is_running:
            return

        self.is_running = False
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        self.clear_all()

    def clear_all(self):
        """Clear all render data"""
        self.render_data.clear()
        self.gpu_batches.clear()
        self._dirty_objects.clear()

    def update_feature_colors_only(self, obj_name: str, feature_id: str, new_color: tuple):
        """Efficient color-only update without rebuilding GPU batches"""
        if obj_name not in self.render_data:
            return
        
        obj_render_data = self.render_data[obj_name]
        if feature_id not in obj_render_data:
            return
        
        render_data = obj_render_data[feature_id]
        
        # Update colors in place - this is the key optimization
        render_data.colors[:] = np.full_like(render_data.colors, new_color, dtype=np.float32)
        
        # Update GPU batch if it exists
        if obj_name in self.gpu_batches and feature_id in self.gpu_batches[obj_name]:
            # Get current offset value
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            offset_val = props.overlay_offset
            
            # Recreate batch with new colors (more efficient than full rebuild)
            self._ensure_shaders()
            offset_verts = render_data.vertices + render_data.normals * offset_val
            
            batch = batch_for_shader(
                self.shaders[render_data.primitive_type],
                render_data.primitive_type.value,
                {"pos": offset_verts, "color": render_data.colors},
            )
            
            self.gpu_batches[obj_name][feature_id] = batch

    def clear_object_data(self, obj_name: str):
        """Remove data for a specific object"""
        if obj_name in self.render_data:
            del self.render_data[obj_name]
        if obj_name in self.gpu_batches:
            del self.gpu_batches[obj_name]
        if obj_name in self._dirty_objects:
            self._dirty_objects.remove(obj_name)

    def update_feature_data(
        self,
        obj_name: str,
        feature: str,
        vertices: np.ndarray,
        normals: np.ndarray,
        colors: np.ndarray,
        primitive_type: PrimitiveType,
    ):
        """Update render data for a specific object and feature"""
        if obj_name not in self.render_data:
            self.render_data[obj_name] = {}

        if len(vertices) == 0:
            if feature in self.render_data[obj_name]:
                del self.render_data[obj_name][feature]
            if obj_name in self.gpu_batches and feature in self.gpu_batches[obj_name]:
                del self.gpu_batches[obj_name][feature]
            return

        self.render_data[obj_name][feature] = RenderData(
            vertices=vertices.astype(np.float32),
            normals=normals.astype(np.float32),
            colors=colors.astype(np.float32),
            primitive_type=primitive_type,
        )
        self._dirty_objects.add(obj_name)

    def _update_batches(self):
        """Rebuild GPU batches using native primitives"""
        if not self._dirty_objects:
            return

        self._ensure_shaders()

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        offset_val = props.overlay_offset

        for obj_name in list(self._dirty_objects):
            if obj_name not in self.render_data:
                continue

            if obj_name not in self.gpu_batches:
                self.gpu_batches[obj_name] = {}

            for feature, data in self.render_data[obj_name].items():
                offset_verts = data.vertices + data.normals * offset_val

                batch = batch_for_shader(
                    self.shaders[data.primitive_type],
                    data.primitive_type.value,
                    {"pos": offset_verts, "color": data.colors},
                )

                self.gpu_batches[obj_name][feature] = batch

        self._dirty_objects.clear()

    def _draw(self):
        """Main draw callback"""
        if not self.is_running:
            return

        selected_objs = [
            obj for obj in bpy.context.selected_objects if obj.type == "MESH"
        ]
        if not selected_objs:
            return

        if self._dirty_objects:
            self._update_batches()
        self._ensure_shaders()

        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        v_radius = props.overlay_vertex_radius
        region_3d = bpy.context.region_data
        view_matrix = region_3d.view_matrix
        proj_matrix = region_3d.window_matrix
        viewport_size = gpu.state.viewport_get()[2:]

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.face_culling_set("BACK")

        # 1. DRAW TRIS (Faces)
        if self.shaders[PrimitiveType.TRIS]:
            shader = self.shaders[PrimitiveType.TRIS]
            shader.bind()
            self._draw_for_type(
                shader, PrimitiveType.TRIS, selected_objs, view_matrix, proj_matrix
            )

        # 2. DRAW LINES (Edges)
        if self.shaders[PrimitiveType.LINES]:
            shader = self.shaders[PrimitiveType.LINES]
            shader.bind()
            
            # Use only working uniforms from console output
            shader.uniform_float("viewportSize", viewport_size)
            shader.uniform_float("lineWidth", props.overlay_edge_width)
            
            self._draw_for_type(
                shader, PrimitiveType.LINES, selected_objs, view_matrix, proj_matrix
            )

        # 3. DRAW POINTS (Native Vertex indicators)
        if self.shaders[PrimitiveType.POINTS]:
            shader = self.shaders[PrimitiveType.POINTS]
            shader.bind()

            # Use only working uniforms from console output
            shader.uniform_float("size", v_radius)
            
            # Fallback for state-based sizing
            gpu.state.point_size_set(v_radius)

            self._draw_for_type(
                shader, PrimitiveType.POINTS, selected_objs, view_matrix, proj_matrix
            )

        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")

    def _draw_for_type(
        self, shader, prim_type, selected_objs, view_matrix, proj_matrix
    ):
        """Helper to draw batches of a specific type for all objects"""
        for obj in selected_objs:
            obj_batches = self.gpu_batches.get(obj.name, {})
            obj_data = self.render_data.get(obj.name, {})

            mvp = proj_matrix @ view_matrix @ obj.matrix_world

            # Use working MVP uniform (confirmed by console output)
            shader.uniform_float("ModelViewProjectionMatrix", mvp)

            for feature_id, batch in obj_batches.items():
                data = obj_data.get(feature_id)
                if data and data.primitive_type == prim_type:
                    batch.draw(shader)
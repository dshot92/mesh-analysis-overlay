# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import gpu
import mathutils

from typing import Dict, List, Optional, Tuple, Any
from bpy.types import Object, Scene
from gpu_extras.batch import batch_for_shader

from .mesh_analyzer import MeshAnalyzer


class GPUDrawer:
    def __init__(self) -> None:
        self._initialize_state()
        self._initialize_gpu()
        # Initialize toggle states dict based on primitive configs
        self.toggle_states = {
            flag_name: False
            for _, (flag_name, _) in self._get_primitive_configs().items()
        }
        # Track which overlays have been analyzed
        self.analyzed_overlays = set()

    def _initialize_state(self) -> None:
        self.is_running: bool = False
        self.mesh_analyzer: MeshAnalyzer = MeshAnalyzer()
        self.active_object: Optional[Object] = None
        # Track last known offset value
        self.last_offset: float = 0.0

    def _initialize_gpu(self) -> None:
        self.shader = gpu.shader.from_builtin("FLAT_COLOR")
        self.handle: Optional[Any] = None
        self.batches: Dict[str, Optional[Any]] = {}

    @property
    def scene_props(self) -> Any:
        return bpy.context.scene.Mesh_Analysis_Overlay_Properties

    def _update_single_visibility(self, flag_name: str) -> None:
        setattr(self, flag_name, getattr(self.scene_props, flag_name))

    def _get_primitive_configs(self) -> Dict[str, Tuple[str, str]]:
        configs = {}

        # Face data (all use TRIS primitive)
        for key in self.mesh_analyzer.face_data.keys():
            configs[key] = (f"show_{key}_faces", "TRIS")

        # Edge data (all use LINES primitive)
        for key in self.mesh_analyzer.edge_data.keys():
            configs[key] = (f"show_{key}_edges", "LINES")

        # Vertex data (all use POINTS primitive)
        for key in self.mesh_analyzer.vertex_data.keys():
            configs[key] = (f"show_{key}_vertices", "POINTS")

        return configs

    def update_visibility(self) -> None:
        # Check if offset has changed
        current_offset = self.scene_props.overlay_offset
        if current_offset != self.last_offset:
            self.last_offset = current_offset
            # Recreate batches with new offset
            if self._is_valid_mesh_object(bpy.context.active_object):
                self._create_all_batches(bpy.context.scene)
                self._force_viewport_redraw()
                return

        # Update toggle states from scene properties
        for key, (flag_name, _) in self._get_primitive_configs().items():
            new_state = getattr(self.scene_props, flag_name, False)
            if new_state != self.toggle_states[flag_name]:
                self.toggle_states[flag_name] = new_state
                setattr(self, flag_name, new_state)

                # If enabling and batch doesn't exist yet, analyze
                if new_state and key not in self.batches:
                    obj = bpy.context.active_object
                    if self._is_valid_mesh_object(obj):
                        self._analyze_mesh(obj)
                        self._force_viewport_redraw()

    def _force_viewport_redraw(self) -> None:
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def draw(self) -> None:
        self.update_visibility()
        obj = bpy.context.active_object

        # Check for edit mode changes
        if obj and obj.mode == "EDIT":
            self.batches.clear()
            self._analyze_mesh(obj)
        elif obj != self.active_object and self._is_valid_mesh_object(obj):
            self.batches.clear()
            self._analyze_mesh(obj)

        if self._is_valid_mesh_object(obj):
            self._setup_gpu_state()
            for key, (flag, _) in self._get_primitive_configs().items():
                if (
                    getattr(self, flag, False)
                    and key in self.batches
                    and self.batches[key]
                ):
                    self._draw_element(key, self._get_primitive_type(key))

    def _is_valid_mesh_object(self, obj: Optional[Object]) -> bool:
        return obj is not None and obj.type == "MESH"

    def _should_reanalyze_mesh(self, obj: Optional[Object]) -> bool:
        # Check if object changed and is valid
        return (
            obj is not None
            and obj != self.active_object
            and self._is_valid_mesh_object(obj)
        )

    def _analyze_mesh(self, obj: Object) -> None:
        self.active_object = obj
        self.mesh_analyzer.analyze_mesh(obj)
        self._create_all_batches(bpy.context.scene)

    def _setup_gpu_state(self) -> None:
        self.shader.bind()
        gpu.state.blend_set("ALPHA")
        gpu.state.face_culling_set("BACK")
        gpu.state.depth_test_set("LESS")

    def _draw_element(self, batch_key: str, primitive_type: str) -> None:
        if not self.batches.get(batch_key):
            return

        self._set_primitive_attributes(primitive_type)
        self.batches[batch_key].draw(self.shader)

    def _set_primitive_attributes(self, primitive_type: str) -> None:
        if primitive_type == "POINTS":
            gpu.state.point_size_set(self.scene_props.overlay_vertex_radius)
        elif primitive_type == "LINES":
            gpu.state.line_width_set(self.scene_props.overlay_edge_width)

    def _create_all_batches(self, scene: Scene) -> None:
        self.batches = {}

        # Process each data type
        for key, (flag_name, _) in self._get_primitive_configs().items():
            if not getattr(self, flag_name, False):
                continue

            # Get the appropriate data and color based on the type
            if key in self.mesh_analyzer.face_data:
                data = self.mesh_analyzer.face_data[key]
                color = getattr(self.scene_props, f"{key}_faces_color")
            elif key in self.mesh_analyzer.edge_data:
                data = self.mesh_analyzer.edge_data[key]
                color = getattr(self.scene_props, f"{key}_edges_color")
            else:  # vertex data
                data = self.mesh_analyzer.vertex_data[key]
                color = getattr(self.scene_props, f"{key}_vertices_color")

            if data and data[0]:  # Check if we have vertices
                self.batches[key] = self._create_batch(key, data, color)

    def _create_batch(
        self,
        key: str,
        data: Tuple[List[mathutils.Vector], List[mathutils.Vector]],
        color: Tuple[float, float, float, float],
    ) -> Any:
        vertices, normals = data
        if not vertices or len(vertices) == 0:
            return None

        # Get primitive type
        primitive_type = self._get_primitive_type(key)

        # Apply offset using the stored normals
        offset_vertices = []
        for v, n in zip(vertices, normals):
            offset_vertices.append(v + (n * self.scene_props.overlay_offset))

        colors = [color] * len(offset_vertices)

        return batch_for_shader(
            self.shader, primitive_type, {"pos": offset_vertices, "color": colors}
        )

    def _get_primitive_type(self, key: str) -> str:
        if key in self.mesh_analyzer.edge_data:
            return "LINES"
        elif key in self.mesh_analyzer.vertex_data:
            return "POINTS"
        return "TRIS"

    def _handle_mesh_update(self, scene, depsgraph) -> None:
        obj = bpy.context.active_object
        if obj and obj.mode == "EDIT":
            self.batches.clear()
            self._analyze_mesh(obj)

    def start(self) -> None:
        if self.is_running:
            return

        # Register the draw handler and mesh update handler
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw, (), "WINDOW", "POST_VIEW"
        )
        bpy.app.handlers.depsgraph_update_post.append(self._handle_mesh_update)
        self._initial_analysis()
        self.is_running = True
        self._force_viewport_redraw()

    def _initial_analysis(self) -> None:
        obj = bpy.context.active_object
        if self._is_valid_mesh_object(obj):
            self._analyze_mesh(obj)

    def stop(self) -> None:
        if not self.is_running:
            return
        if self.handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            bpy.app.handlers.depsgraph_update_post.remove(self._handle_mesh_update)
        self.handle = None
        self.is_running = False
        self.active_object = None
        self.batches = {}

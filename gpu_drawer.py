# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
import gpu

from typing import Dict, List, Optional, Tuple, Any
from bpy.types import Object, Scene
from gpu_extras.batch import batch_for_shader

from .mesh_analyzer import MeshAnalyzer


class GPUDrawer:
    def __init__(self) -> None:
        self._initialize_state()
        self._initialize_gpu()

    def _initialize_state(self) -> None:
        self.is_running: bool = False
        self.mesh_analyzer: MeshAnalyzer = MeshAnalyzer()
        self.active_object: Optional[Object] = None

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
        # Update based on dynamic configs
        for key, (flag_name, _) in self._get_primitive_configs().items():
            setattr(self, flag_name, getattr(self.scene_props, flag_name, True))

    def draw(self) -> None:
        self.update_visibility()
        obj = bpy.context.active_object

        if self._should_reanalyze_mesh(obj):
            self._analyze_mesh(obj)

        if self._is_valid_mesh_object(obj):
            self._setup_gpu_state()
            # Use dynamic configs instead of PRIMITIVE_CONFIGS
            for key, (flag, primitive) in self._get_primitive_configs().items():
                if getattr(self, flag, False):  # Default to False if flag doesn't exist
                    self._draw_element(key, primitive)

    def _is_valid_mesh_object(self, obj: Optional[Object]) -> bool:
        return obj is not None and obj.type == "MESH"

    def _should_reanalyze_mesh(self, obj: Optional[Object]) -> bool:
        return obj != self.active_object and self._is_valid_mesh_object(obj)

    def _analyze_mesh(self, obj: Object) -> None:
        self.active_object = obj
        self.mesh_analyzer.analyze_mesh(obj)
        self._create_all_batches(bpy.context.scene)

    def _setup_gpu_state(self) -> None:
        self.shader.bind()
        gpu.state.blend_set("ALPHA")
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

        # Face data
        for key in self.mesh_analyzer.face_data:
            vertices = self.mesh_analyzer.face_data[key]
            if vertices:
                # Add _faces suffix for face colors
                color = getattr(self.scene_props, f"{key}_faces_color")
                self.batches[key] = self._create_batch(key, vertices, color)

        # Edge data
        for key in self.mesh_analyzer.edge_data:
            vertices = self.mesh_analyzer.edge_data[key]
            if vertices:
                color = getattr(self.scene_props, f"{key}_edges_color")
                self.batches[key] = self._create_batch(key, vertices, color)

        # Vertex data
        for key in self.mesh_analyzer.vertex_data:
            vertices = self.mesh_analyzer.vertex_data[key]
            if vertices:
                # Add _vertices suffix for vertex colors
                color = getattr(self.scene_props, f"{key}_vertices_color")
                self.batches[key] = self._create_batch(key, vertices, color)

    def _create_batch(
        self, key: str, vertices: List[Any], color: Tuple[float, float, float, float]
    ) -> Any:
        if not vertices:
            return None

        # Get primitive type based on which data dictionary contains the key
        primitive_type = "TRIS"  # default
        if key in self.mesh_analyzer.edge_data:
            primitive_type = "LINES"
        elif key in self.mesh_analyzer.vertex_data:
            primitive_type = "POINTS"

        colors = [color] * len(vertices)

        return batch_for_shader(
            self.shader, primitive_type, {"pos": vertices, "color": colors}
        )

    def depsgraph_update(self, scene: Scene, depsgraph: Any) -> None:
        if not self._should_process_update():
            return

        obj = bpy.context.active_object
        self._update_mesh_if_needed(obj, scene)
        self._create_all_batches(scene)
        self._redraw_viewport()

    def _should_process_update(self) -> bool:
        obj = bpy.context.active_object
        return self.is_running and self._is_valid_mesh_object(obj)

    def _update_mesh_if_needed(self, obj: Object, scene: Scene) -> None:
        if obj.mode == "EDIT":
            obj.update_from_editmode()
        self.mesh_analyzer.analyze_mesh(obj)

    def _redraw_viewport(self) -> None:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

    def start(self) -> None:
        if self.is_running:
            return

        self._register_handlers()
        self._initial_analysis()
        self.is_running = True

    def _register_handlers(self) -> None:
        self.handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw, (), "WINDOW", "POST_VIEW"
        )
        bpy.app.handlers.depsgraph_update_post.append(self.depsgraph_update)

    def _initial_analysis(self) -> None:
        obj = bpy.context.active_object
        if self._is_valid_mesh_object(obj):
            self._analyze_mesh(obj)
            self._redraw_viewport()

    def stop(self) -> None:
        if not self.is_running:
            return

        self._unregister_handlers()
        self._cleanup_state()

    def _unregister_handlers(self) -> None:
        if self.handle:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
        if self.depsgraph_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(self.depsgraph_update)

    def _cleanup_state(self) -> None:
        self.handle = None
        self.is_running = False
        self.active_object = None
        self.batches = {}

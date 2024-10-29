# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import mathutils
from typing import Dict, List, Optional, Tuple, Any
from bpy.types import Object
from gpu_extras.batch import batch_for_shader
from .mesh_analyzer import MeshAnalyzer


class GPUDrawer:
    def __init__(self) -> None:
        self.is_running: bool = False
        self.active_object: Optional[Object] = None
        self.last_offset: float = 0.0
        self.shader = gpu.shader.from_builtin("FLAT_COLOR")
        self.handle: Optional[Any] = None
        self.batches: Dict[str, Optional[Any]] = {}
        self.toggle_states = {}

    @property
    def scene_props(self) -> Any:
        return bpy.context.scene.Mesh_Analysis_Overlay_Properties

    def draw(self) -> None:
        obj = bpy.context.active_object
        if not self._is_valid_mesh_object(obj):
            return

        if obj != self.active_object or not self.batches:
            self._initialize_for_new_object(obj)

        self._handle_toggle_changes()
        self._handle_offset_changes()
        self._draw_batches()

    def start(self) -> None:
        if not self.is_running:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), "WINDOW", "POST_VIEW"
            )
            self.is_running = True

    def stop(self) -> None:
        if self.is_running and self.handle:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            self.handle = None
            self.is_running = False
            self.active_object = None
            self.batches = {}

    def _initialize_for_new_object(self, obj: Object) -> None:
        self.active_object = obj
        self.batches = {}

        # Initialize toggle states and create batches for enabled features
        for key, (flag_name, _) in self._get_feature_configs().items():
            current_state = getattr(self.scene_props, flag_name, False)
            self.toggle_states[flag_name] = current_state
            setattr(self, flag_name, current_state)

            if current_state:
                self._create_batch_for_feature(key)

    def _get_feature_configs(self) -> Dict[str, Tuple[str, str]]:
        """Returns {feature_key: (property_name, primitive_type)}"""
        if not self._is_valid_mesh_object(bpy.context.active_object):
            return {}

        configs = {}
        for prop_name in dir(self.scene_props):
            if not prop_name.startswith("show_"):
                continue

            if prop_name.endswith("_faces"):
                key = prop_name[5:-6]
                configs[key] = (prop_name, "TRIS")
            elif prop_name.endswith("_edges"):
                key = prop_name[5:-6]
                configs[key] = (prop_name, "LINES")
            elif prop_name.endswith("_vertices"):
                key = prop_name[5:-9]
                configs[key] = (prop_name, "POINTS")

        return configs

    def _handle_toggle_changes(self) -> None:
        for key, (flag_name, _) in self._get_feature_configs().items():
            current_state = getattr(self.scene_props, flag_name, False)
            if current_state != self.toggle_states.get(flag_name, False):
                self.toggle_states[flag_name] = current_state
                setattr(self, flag_name, current_state)
                if current_state:
                    self._create_batch_for_feature(key)
                elif key in self.batches:
                    del self.batches[key]

    def _handle_offset_changes(self) -> None:
        current_offset = self.scene_props.overlay_offset
        if current_offset != self.last_offset:
            self._update_vertex_positions(current_offset)
            self.last_offset = current_offset

    def _draw_batches(self) -> None:
        self._setup_gpu_state()
        for key, (flag_name, primitive_type) in self._get_feature_configs().items():
            if (
                getattr(self.scene_props, flag_name, False)
                and key in self.batches
                and self.batches[key]
            ):
                self._draw_batch(key, primitive_type)

    def _create_batch_for_feature(self, key: str) -> None:
        prop_name, _ = self._get_feature_configs()[key]
        if not getattr(self, prop_name, False):
            return

        suffix = prop_name.split("_")[-1]
        color = getattr(self.scene_props, f"{key}_{suffix}_color")
        data = self._get_mesh_data(key)

        if data and data[0]:
            batch = self._create_batch(key, data, color)
            if batch:
                self.batches[key] = batch

    def _create_batch(
        self,
        key: str,
        data: Tuple[List[mathutils.Vector], List[mathutils.Vector]],
        color: Tuple[float, float, float, float],
    ) -> Any:
        vertices, normals = data
        if not vertices:
            return None

        self.batches[f"{key}_data"] = (vertices, normals, color)
        primitive_type = self._get_feature_configs()[key][1]

        offset_vertices = [
            v + (n * self.scene_props.overlay_offset) for v, n in zip(vertices, normals)
        ]
        colors = [color] * len(offset_vertices)

        return batch_for_shader(
            self.shader, primitive_type, {"pos": offset_vertices, "color": colors}
        )

    def _update_vertex_positions(self, current_offset: float) -> None:
        for key, (flag, primitive_type) in self._get_feature_configs().items():
            if not getattr(self, flag, False):
                continue

            data_key = f"{key}_data"
            if data_key not in self.batches or key not in self.batches:
                continue

            vertices, normals, color = self.batches[data_key]
            offset_vertices = [
                v + (n * current_offset) for v, n in zip(vertices, normals)
            ]
            colors = [color] * len(offset_vertices)
            self.batches[key] = batch_for_shader(
                self.shader, primitive_type, {"pos": offset_vertices, "color": colors}
            )

    def _get_mesh_data(self, key: str) -> Tuple[List, List]:
        try:
            if not self._is_valid_mesh_object(self.active_object):
                return ([], [])

            analyzer = MeshAnalyzer(self.active_object)
            for data_dict in [
                analyzer.vertex_data,
                analyzer.edge_data,
                analyzer.face_data,
            ]:
                if key in data_dict:
                    return data_dict[key]
        except ValueError:
            pass
        return ([], [])

    def _setup_gpu_state(self) -> None:
        self.shader.bind()
        gpu.state.blend_set("ALPHA")
        gpu.state.face_culling_set("BACK")
        gpu.state.depth_test_set("LESS")

    def _draw_batch(self, key: str, primitive_type: str) -> None:
        if primitive_type == "POINTS":
            gpu.state.point_size_set(self.scene_props.overlay_vertex_radius)
        elif primitive_type == "LINES":
            gpu.state.line_width_set(self.scene_props.overlay_edge_width)
        self.batches[key].draw(self.shader)

    @staticmethod
    def _is_valid_mesh_object(obj: Optional[Object]) -> bool:
        return obj is not None and obj.type == "MESH"

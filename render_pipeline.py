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
        try:
            self.count = len(self.vertices)
        except Exception:
            self.count = 0


class RenderPipeline:
    """Batched rendering pipeline using merged per-type GPU batches.

    Public API is unchanged (update_feature_data / update_feature_colors_only /
    clear_object_data / clear_all). Internally, features sharing a primitive
    type are merged into a single GPU batch per (object, primitive type),
    cutting draw calls from N_features to at most 3 per object and halving
    CPU offset temporaries.
    """

    def __init__(self):
        # Shaders for different primitive types
        self.shaders = {
            PrimitiveType.TRIS: None,
            PrimitiveType.LINES: None,
            PrimitiveType.POINTS: None,
        }
        # Nested dict: obj_name -> feature_id -> RenderData
        self.render_data: Dict[str, Dict[str, RenderData]] = {}
        # Merged batches: obj_name -> PrimitiveType -> GPU Batch
        # (changed from per-feature to per-type merging; only used internally)
        self.gpu_batches: Dict[str, Dict[any, any]] = {}
        self.is_running = False
        self._handle = None
        # Track objects that need batch rebuilding
        self._dirty_objects: Set[str] = set()
        # Draw-time caches to avoid per-frame Python scans.
        self._xray_cached: bool = False
        self._xray_frame: int = 0

    def _ensure_shaders(self):
        """Initialize specialized shaders using official builtins"""
        if self.shaders[PrimitiveType.TRIS] is None:
            # Standard smooth color for triangles
            self.shaders[PrimitiveType.TRIS] = gpu.shader.from_builtin("FLAT_COLOR")

            # Polyline shader for consistent width
            self.shaders[PrimitiveType.LINES] = gpu.shader.from_builtin("POLYLINE_FLAT_COLOR")

            # Native Point shader for vertices
            # In Blender 4.x/5.x, POINT_FLAT_COLOR is the correct builtin
            self.shaders[PrimitiveType.POINTS] = gpu.shader.from_builtin("POINT_FLAT_COLOR")

    def start(self):
        """Start the render pipeline"""
        if self.is_running:
            return

        self.is_running = True
        # Vulkan/Metal compat: control point size per-shader via the
        # `size` uniform. When program_point_size is False (default),
        # point_size_set() overwrites that uniform, so keep it enabled.
        try:
            if hasattr(gpu.state, "program_point_size_set"):
                gpu.state.program_point_size_set(True)
        except Exception:
            pass
        try:
            if hasattr(gpu.platform, "backend_type_get"):
                print(f"[Mesh Analysis Overlay] GPU backend: {gpu.platform.backend_type_get()}")
        except Exception:
            pass
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

        # Restore default so other add-ons relying on point_size_set keep working.
        try:
            if hasattr(gpu.state, "program_point_size_set"):
                gpu.state.program_point_size_set(False)
        except Exception:
            pass

        self.clear_all()

    def clear_all(self):
        """Clear all render data"""
        self.render_data.clear()
        self.gpu_batches.clear()
        self._dirty_objects.clear()

    def update_feature_colors_only(self, obj_name: str, feature_id: str, new_color: tuple):
        """Efficient color-only update without immediate GPU rebuild.

        Updates the stored colors in place and defers the merged batch rebuild
        to _update_batches (runs once before the next draw). This coalesces
        rapid slider drags into a single rebuild.
        """
        if obj_name not in self.render_data:
            return

        obj_render_data = self.render_data[obj_name]
        if feature_id not in obj_render_data:
            return

        render_data = obj_render_data[feature_id]

        try:
            # In-place update avoids reallocating the color array.
            render_data.colors[:] = new_color
        except Exception:
            try:
                render_data.colors = np.full((len(render_data.vertices), 4), new_color, dtype=np.float32)
            except Exception:
                return

        self._dirty_objects.add(obj_name)

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

        try:
            v_len = len(vertices)
        except Exception:
            v_len = 0
        if v_len == 0:
            if feature in self.render_data[obj_name]:
                del self.render_data[obj_name][feature]
                # Defer merged-batch rebuild; _update_batches drops empty types.
                self._dirty_objects.add(obj_name)
            if not self.render_data[obj_name]:
                # No features left: drop batches immediately to avoid stale draws.
                if obj_name in self.gpu_batches:
                    del self.gpu_batches[obj_name]
                self._dirty_objects.discard(obj_name)
            return

        # Avoid copies when arrays are already float32 contiguous.
        try:
            v_arr = np.ascontiguousarray(vertices, dtype=np.float32)
            n_arr = np.ascontiguousarray(normals, dtype=np.float32)
            c_arr = np.ascontiguousarray(colors, dtype=np.float32)
        except Exception:
            return
        # Guard ragged inputs (stale topology): trim to common length.
        try:
            n = min(len(v_arr), len(n_arr), len(c_arr))
            if n == 0:
                return
            if len(v_arr) != n or len(n_arr) != n or len(c_arr) != n:
                print(f"[Mesh Analysis Overlay] trimmed ragged {obj_name}:{feature} "
                      f"to {n} (was {len(v_arr)}/{len(n_arr)}/{len(c_arr)})")
            if len(v_arr) != n:
                v_arr = v_arr[:n]
            if len(n_arr) != n:
                n_arr = n_arr[:n]
            if len(c_arr) != n:
                c_arr = c_arr[:n]
        except Exception:
            pass

        self.render_data[obj_name][feature] = RenderData(
            vertices=v_arr,
            normals=n_arr,
            colors=c_arr,
            primitive_type=primitive_type,
        )
        self._dirty_objects.add(obj_name)

    def _update_batches(self):
        """Rebuild merged GPU batches (one per object per primitive type)."""
        from .utils import prof as _profR
        with _profR("render.batches"):
            return self._update_batches_inner()

    def _update_batches_inner(self):
        """Inner (timed by wrapper)."""
        if not self._dirty_objects:
            return

        self._ensure_shaders()

        try:
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            offset_val = float(props.overlay_offset)
        except Exception:
            offset_val = 0.0

        summaries = []
        for obj_name in list(self._dirty_objects):
            obj_features = self.render_data.get(obj_name)
            if not obj_features:
                if obj_name in self.gpu_batches:
                    del self.gpu_batches[obj_name]
                summaries.append(f"{obj_name}[cleared]")
                continue

            # Group by primitive type.
            grouped: Dict[PrimitiveType, list] = {}
            for _fid, data in obj_features.items():
                try:
                    if len(data.vertices) == 0:
                        continue
                except Exception:
                    continue
                grouped.setdefault(data.primitive_type, []).append(data)

            if obj_name not in self.gpu_batches:
                self.gpu_batches[obj_name] = {}
            merged = self.gpu_batches[obj_name]
            # Drop stale primitive types no longer present.
            for stale in [k for k in list(merged.keys()) if k not in grouped]:
                del merged[stale]

            for prim_type, datas in grouped.items():
                try:
                    if len(datas) == 1:
                        d = datas[0]
                        # Single temp for offset; batch_for_shader copies to GPU.
                        if offset_val != 0.0:
                            offset_verts = d.vertices + d.normals * offset_val
                        else:
                            offset_verts = d.vertices
                        batch = batch_for_shader(
                            self.shaders[prim_type],
                            prim_type.value,
                            {"pos": offset_verts, "color": d.colors},
                        )
                    else:
                        v_cat = np.concatenate([d.vertices for d in datas], axis=0)
                        n_cat = np.concatenate([d.normals for d in datas], axis=0)
                        c_cat = np.concatenate([d.colors for d in datas], axis=0)
                        if offset_val != 0.0:
                            # out= not usable (needs same shape out); single temp.
                            offset_verts = v_cat + n_cat * offset_val
                        else:
                            offset_verts = v_cat
                        batch = batch_for_shader(
                            self.shaders[prim_type],
                            prim_type.value,
                            {"pos": offset_verts, "color": c_cat},
                        )
                    merged[prim_type] = batch
                except Exception:
                    # Keep previous batch on failure to avoid flicker.
                    continue
            try:
                parts = []
                for _pt, _ds in grouped.items():
                    try:
                        _nv = sum(len(_d.vertices) for _d in _ds)
                    except Exception:
                        _nv = 0
                    parts.append(f"{_pt.name}:{_nv}v/{len(_ds)}f")
                summaries.append(f"{obj_name}[" + "+".join(parts) + "]")
            except Exception:
                pass

        try:
            from .utils import prof_event as _bev
            if summaries:
                _bev("batches rebuilt: " + ", ".join(summaries))
        except Exception:
            pass
        self._dirty_objects.clear()

    def _is_xray_enabled(self) -> bool:
        """Cached X-ray check (area scan at most every 30 draws)."""
        self._xray_frame += 1
        if self._xray_frame % 30 == 1:
            try:
                xray = False
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                if getattr(getattr(space, "shading", None), "show_xray", False):
                                    xray = True
                                    break
                        if xray:
                            break
                self._xray_cached = xray
            except Exception:
                pass
        return self._xray_cached

    def _draw(self):
        """Main draw callback"""
        if not self.is_running:
            return

        try:
            selected_objs = [
                obj for obj in bpy.context.selected_objects if obj.type == "MESH"
            ]
        except Exception:
            return
        if not selected_objs:
            return

        if self._dirty_objects:
            self._update_batches()
        self._ensure_shaders()

        try:
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            v_radius = props.overlay_vertex_radius
            edge_width = props.overlay_edge_width
        except Exception:
            return
        try:
            region_3d = bpy.context.region_data
            view_matrix = region_3d.view_matrix
            proj_matrix = region_3d.window_matrix
        except Exception:
            return
        try:
            viewport_size = gpu.state.viewport_get()[2:]
        except Exception:
            viewport_size = (1920, 1080)

        # Precompute MVP once per object (was 3x per object before).
        mvp_cache = {}
        for obj in selected_objs:
            try:
                mvp_cache[obj.name] = proj_matrix @ view_matrix @ obj.matrix_world
            except Exception:
                continue

        gpu.state.blend_set("ALPHA")

        xray_enabled = self._is_xray_enabled()

        if xray_enabled:
            gpu.state.depth_test_set("NONE")
            gpu.state.face_culling_set("NONE")  # Disable face culling to see back faces
        else:
            gpu.state.depth_test_set("LESS_EQUAL")
            gpu.state.face_culling_set("BACK")  # Enable back face culling by default

        # 1. DRAW TRIS (Faces) — single merged batch per object.
        if self.shaders[PrimitiveType.TRIS]:
            shader = self.shaders[PrimitiveType.TRIS]
            shader.bind()
            self._draw_for_type(
                shader, PrimitiveType.TRIS, selected_objs, mvp_cache
            )

        # 2. DRAW LINES (Edges)
        if self.shaders[PrimitiveType.LINES]:
            shader = self.shaders[PrimitiveType.LINES]
            shader.bind()

            # Use only working uniforms from console output
            shader.uniform_float("viewportSize", viewport_size)
            shader.uniform_float("lineWidth", edge_width)

            self._draw_for_type(
                shader, PrimitiveType.LINES, selected_objs, mvp_cache
            )

        # 3. DRAW POINTS (Native Vertex indicators)
        if self.shaders[PrimitiveType.POINTS]:
            shader = self.shaders[PrimitiveType.POINTS]
            shader.bind()

            # Vulkan/Metal-safe: size via uniform only. Do NOT call
            # gpu.state.point_size_set() here: when program_point_size is
            # False it overwrites this uniform, and it is ignored/emulated
            # on Vulkan/Metal.
            try:
                if hasattr(gpu.state, "program_point_size_set"):
                    gpu.state.program_point_size_set(True)
            except Exception:
                pass
            shader.uniform_float("size", v_radius)

            self._draw_for_type(
                shader, PrimitiveType.POINTS, selected_objs, mvp_cache
            )

        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")

    def _draw_for_type(
        self, shader, prim_type, selected_objs, mvp_cache
    ):
        """Helper to draw merged batches of a specific type for all objects."""
        for obj in selected_objs:
            try:
                batch = self.gpu_batches.get(obj.name, {}).get(prim_type)
            except Exception:
                continue
            if batch is None:
                continue
            mvp = mvp_cache.get(obj.name)
            if mvp is None:
                continue
            try:
                # Use working MVP uniform (confirmed by console output)
                shader.uniform_float("ModelViewProjectionMatrix", mvp)
                batch.draw(shader)
            except Exception:
                continue

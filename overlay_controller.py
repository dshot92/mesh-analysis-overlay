# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import numpy as np
from typing import Dict, Set, List, Optional
from bpy.types import Object

from .analysis_engine import MeshAnalysisEngine
from .render_pipeline import RenderPipeline, PrimitiveType
from .config_manager import config_manager
from .utils import (
    get_updated_bmesh_from_depsgraph,
    free_bmesh_if_owned,
    collect_enabled_features,
    note_overlay_start,
    note_overlay_stop,
    prof,
    prof_event,
    prof_scope,
)


def _clear_panel_stats_cache():
    try:
        from .panels import Mesh_Analysis_Overlay_Panel
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    except Exception:
        pass


def _same_arrays(a, b) -> bool:
    try:
        if a is b:
            return True
        if a.shape != b.shape:
            return False
        if a.size == 0:
            return True
        return bool(np.array_equal(a, b))
    except Exception:
        return False


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
        _clear_panel_stats_cache()
        try:
            note_overlay_start()
        except Exception:
            pass
        self.update_all_selected()

    def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        try:
            note_overlay_stop()
        except Exception:
            pass
        self.render_pipeline.stop()
        self.displayed_objects.clear()
        _clear_panel_stats_cache()

    def update_all_selected(self):
        with prof_scope("update_all"):
            return self._update_all_selected_inner()

    def _update_all_selected_inner(self):
        if not self.is_running:
            return

        try:
            selected_meshes = [
                obj for obj in bpy.context.selected_objects if obj.type == "MESH"
            ]
        except Exception:
            return
        current_names = {obj.name for obj in selected_meshes}
        to_remove = self.displayed_objects - current_names
        try:
            added = current_names - self.displayed_objects
            if added or to_remove:
                prof_event(
                    "selection changed: +"
                    + ",".join(sorted(added) if added else ["-"])
                    + " -"
                    + ",".join(sorted(to_remove) if to_remove else ["-"])
                )
            try:
                modes = []
                for o in selected_meshes:
                    try:
                        modes.append(f"{o.name}[{o.mode}]")
                    except Exception:
                        pass
                prof_event(f"selected(n={len(modes)}): {', '.join(sorted(modes)) if modes else '(none)'}")
            except Exception:
                pass
        except Exception:
            pass
        for name in to_remove:
            self.render_pipeline.clear_object_data(name)
            # Drop stale analysis cache for deselected objects to bound memory.
            try:
                self.analysis_engine.invalidate_cache(name)
            except Exception:
                pass
        self.displayed_objects = current_names

        for obj in selected_meshes:
            self.update_overlay(obj)

    def _push_if_changed(self, obj_name: str, f_id: str, gpu_data, present: dict) -> bool:
        """Push to render pipeline only when content actually changed.

        Returns True when a pipeline update was issued. Identical vertices /
        normals / colors are skipped, making repeat update_all_selected() calls
        with no mesh change a no-op (no batch rebuilds).
        """
        try:
            v_len = len(gpu_data.vertices)
        except Exception:
            v_len = 0
        if v_len == 0:
            if f_id in present:
                self.render_pipeline.update_feature_data(
                    obj_name, f_id,
                    np.zeros((0,), dtype=np.float32),
                    np.zeros((0,), dtype=np.float32),
                    np.zeros((0,), dtype=np.float32),
                    PrimitiveType.POINTS,
                )
                return True
            return False
        old = present.get(f_id)
        if old is not None:
            try:
                if (
                    _same_arrays(old.vertices, gpu_data.vertices)
                    and _same_arrays(old.normals, gpu_data.normals)
                    and _same_arrays(old.colors, gpu_data.colors)
                    and old.primitive_type == gpu_data.primitive_type
                ):
                    return False
            except Exception:
                pass
        self.render_pipeline.update_feature_data(
            obj_name, f_id, gpu_data.vertices, gpu_data.normals, gpu_data.colors,
            gpu_data.primitive_type,
        )
        return True

    def update_overlay(self, obj: Object):
        with prof_scope("overlay"):
            return self._update_overlay_inner(obj)

    def _update_overlay_inner(self, obj: Object):
        """Update overlay for a specific object - called by handlers only"""
        if not self.is_running or not obj or obj.type != "MESH":
            return

        self.displayed_objects.add(obj.name)

        try:
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        except Exception:
            return
        metadata = config_manager.get_metadata()
        enabled_features, feature_colors, _all_ids = collect_enabled_features(props, metadata)

        # Clear only stale features actually present (was: 14 empty pushes/object).
        try:
            present = self.render_pipeline.render_data.get(obj.name, {})
            for f_id in list(present.keys()):
                if f_id not in enabled_features:
                    self.render_pipeline.update_feature_data(
                        obj.name,
                        f_id,
                        np.zeros((0,), dtype=np.float32),
                        np.zeros((0,), dtype=np.float32),
                        np.zeros((0,), dtype=np.float32),
                        PrimitiveType.POINTS,
                    )
        except Exception:
            pass

        if not enabled_features:
            return

        # Get the most updated bmesh for this object (fallback for manual updates)
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            return
        try:
            bm = get_updated_bmesh_from_depsgraph(obj, depsgraph)
        except Exception:
            return

        try:
            # Get GPU-ready data from analysis engine with the pre-created bmesh
            gpu_results = self.analysis_engine.analyze_and_format_mesh_with_bmesh(
                obj, enabled_features, feature_colors, bm
            )

            present_after = self.render_pipeline.render_data.get(obj.name, {}) or {}
            initial_present = dict(present_after)
            for f_id in enabled_features:
                if f_id in gpu_results:
                    self._push_if_changed(obj.name, f_id, gpu_results[f_id], initial_present)
                else:
                    if f_id in initial_present:
                        self.render_pipeline.update_feature_data(
                            obj.name,
                            f_id,
                            np.zeros((0,), dtype=np.float32),
                            np.zeros((0,), dtype=np.float32),
                            np.zeros((0,), dtype=np.float32),
                            PrimitiveType.POINTS,
                        )
        finally:
            free_bmesh_if_owned(obj, bm)


    def get_mesh_stats(self, obj: Object) -> Dict[str, int]:
        return self.analysis_engine.get_mesh_stats(obj)

    def get_feature_counts(self, obj: Object, features: Optional[List[str]] = None) -> Dict[str, int]:
        """Return element counts per feature (uses cache, single BMesh on miss)."""
        if obj is None or getattr(obj, "type", None) != "MESH":
            return {}
        if features is None:
            try:
                features = list(self.analysis_engine.feature_types.keys())
            except Exception:
                return {}
        if not features:
            return {}
        counts: Dict[str, int] = {}
        missing: List[str] = []
        for f_id in features:
            try:
                cached = self.analysis_engine.get_cached_result(obj.name, f_id)
            except Exception:
                cached = None
            if cached is not None:
                try:
                    counts[f_id] = len(cached.indices)
                except Exception:
                    counts[f_id] = 0
            else:
                missing.append(f_id)
        if missing:
            bm = None
            try:
                depsgraph = bpy.context.evaluated_depsgraph_get()
            except Exception:
                depsgraph = None
            try:
                if depsgraph is not None:
                    bm = get_updated_bmesh_from_depsgraph(obj, depsgraph)
                if bm is not None:
                    res = self.analysis_engine.analyze_mesh(obj, missing, bm)
                    for f_id in missing:
                        r = res.get(f_id)
                        if r is not None:
                            try:
                                counts[f_id] = len(r.indices)
                            except Exception:
                                counts[f_id] = 0
                        else:
                            cached = self.analysis_engine.get_cached_result(obj.name, f_id)
                            counts[f_id] = len(cached.indices) if cached is not None else 0
                else:
                    for f_id in missing:
                        counts[f_id] = 0
            except Exception:
                for f_id in missing:
                    if f_id not in counts:
                        counts[f_id] = 0
            finally:
                if bm is not None:
                    free_bmesh_if_owned(obj, bm)
        return counts

    def clear_all_cache(self):
        self.analysis_engine.clear_all_cache()
        self.render_pipeline.clear_all()
        self.displayed_objects.clear()
        _clear_panel_stats_cache()


# Global instance
overlay_controller = OverlayController()

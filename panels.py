# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from typing import Dict

from .overlay_controller import overlay_controller
from .config_manager import config_manager
from .utils import get_updated_bmesh_from_depsgraph, free_bmesh_if_owned


class Mesh_Analysis_Overlay_Panel(bpy.types.Panel):
    bl_label = "Mesh Analysis Overlay"
    bl_idname = "VIEW3D_PT_mesh_analysis_overlay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Edit"

    _stats_cache = {}  # Class variable to store statistics

    @classmethod
    def clear_stats_cache(cls):
        """Clear the statistics cache"""
        cls._stats_cache.clear()

    def draw(self, context):
        layout = self.layout
        props = context.scene.Mesh_Analysis_Overlay_Properties
        factor = 0.85

        # Toggle button for overlay
        row = layout.row()
        row.operator(
            "view3d.mesh_analysis_overlay",
            text="Show Mesh Overlay",
            icon="OVERLAY",
            depress=overlay_controller.is_running,
        )

        # Draw feature panels
        metadata = config_manager.get_metadata()
        for category, features in metadata.items():
            header, panel = layout.panel(f"{category}_panel", default_closed=False)
            header.label(text=category.title())
            if panel:
                for feature in features:
                    row = panel.row(align=True)
                    split = row.split(factor=factor)
                    split.prop(props, f"{feature['id']}_enabled", text=feature["label"])
                    split.prop(props, f"{feature['id']}_color", text="")
                    op = split.operator(
                        "view3d.select_feature_elements",
                        text="",
                        icon="RESTRICT_SELECT_OFF",
                    )
                    op.feature = feature["id"]

        # Statistics panel
        header, panel = layout.panel("statistics_panel", default_closed=False)
        header.label(text="Statistics")

        if panel:
            self.draw_statistics(context, panel)

        # Offset settings
        header, panel = layout.panel("panel_settings", default_closed=True)
        header.label(text="Overlay Settings")

        if panel:
            panel.prop(props, "overlay_offset", text="Overlay Offset")
            panel.prop(props, "overlay_edge_width", text="Overlay Edge Width")
            panel.prop(props, "overlay_vertex_radius", text="Overlay Vertex Radius")
            panel.prop(props, "non_planar_threshold", text="Non-Planar Threshold")

            # Reset to preferences (CONFIG_PREFERENCE.json)
            row = panel.row()
            row.operator("mesh_analysis.restore_preferences", text="Restore Preferences", icon="LOOP_BACK")

        # Profiling (timers)
        header, panel = layout.panel("profiling_panel", default_closed=True)
        header.label(text="Profiling")
        if panel:
            panel.prop(props, "profiling", text="Profiling", toggle=True)

    def draw_statistics(self, context, panel):
        """Draw statistics for all selected mesh objects.

        Reuses engine cache first; allocates at most one BMesh per object and
        only when some active feature is missing from cache. This avoids the
        previous per-category BMesh + full re-analysis on every UI redraw.
        """
        if not overlay_controller.is_running:
            panel.label(text="Enable overlay to see statistics")
            return

        try:
            selected_meshes = [
                obj for obj in context.selected_objects if obj.type == "MESH"
            ]
        except Exception:
            return
        if not selected_meshes:
            panel.label(text="Select a mesh to see statistics")
            return

        try:
            props = context.scene.Mesh_Analysis_Overlay_Properties
        except Exception:
            return
        analysis_engine = overlay_controller.analysis_engine

        try:
            metadata = config_manager.get_metadata()
        except Exception:
            return

        for obj in selected_meshes:
            # Get cached stats or calculate new ones
            if obj.name not in self._stats_cache:
                stats: Dict = {"features": {}}

                # Collect all active features across categories once.
                active_by_category = {}
                all_active = []
                for category, features in metadata.items():
                    active = [
                        feature["id"]
                        for feature in features
                        if getattr(props, f"{feature['id']}_enabled", False)
                    ]
                    if active:
                        active_by_category[category] = [f for f in features if f["id"] in active]
                        all_active.extend(active)

                if all_active:
                    # Fast path: all counts already cached (steady state, no BMesh).
                    missing = [
                        fid for fid in all_active
                        if analysis_engine.get_cached_result(obj.name, fid) is None
                    ]
                    # Note: missing from cache may also mean "zero hits" (engine
                    # only caches non-empty). Fall through to one analysis to
                    # distinguish zero vs stale.
                    if not missing:
                        for category, features in active_by_category.items():
                            stats["features"][category.title()] = {
                                feature["label"]: len(
                                    analysis_engine.get_cached_result(obj.name, feature["id"]).indices
                                )
                                for feature in features
                            }
                    else:
                        # Single BMesh + single batched analysis per object.
                        try:
                            depsgraph = bpy.context.evaluated_depsgraph_get()
                        except Exception:
                            depsgraph = None
                        bm = None
                        try:
                            if depsgraph is not None:
                                bm = get_updated_bmesh_from_depsgraph(obj, depsgraph)
                            if bm is not None:
                                analysis_results = analysis_engine.analyze_mesh(
                                    obj, all_active, bm
                                )
                            else:
                                analysis_results = {}
                        except Exception:
                            analysis_results = {}
                        finally:
                            if bm is not None:
                                free_bmesh_if_owned(obj, bm)
                        for category, features in active_by_category.items():
                            cat_stats = {}
                            for feature in features:
                                res = analysis_results.get(feature["id"])
                                if res is not None:
                                    try:
                                        cat_stats[feature["label"]] = len(res.indices)
                                    except Exception:
                                        cat_stats[feature["label"]] = 0
                                else:
                                    # Check cache (may have been fresh without re-analysis)
                                    cached = analysis_engine.get_cached_result(obj.name, feature["id"])
                                    if cached is not None:
                                        try:
                                            cat_stats[feature["label"]] = len(cached.indices)
                                        except Exception:
                                            cat_stats[feature["label"]] = 0
                                    else:
                                        cat_stats[feature["label"]] = 0
                            stats["features"][category.title()] = cat_stats

                self._stats_cache[obj.name] = stats

            # Draw statistics from cache
            stats = self._stats_cache[obj.name]
            if not stats["features"]:
                continue

            box = panel.box()
            row = box.row()
            row.label(text=obj.name, icon="MESH_DATA")

            for category_title, features in stats["features"].items():
                if not features:
                    continue

                col = box.column(align=True)
                col.label(text=f"{category_title}:")
                for label, count in features.items():
                    r = col.row()
                    r.separator()
                    r.label(text=label)
                    r.label(text=str(count))


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        try:
            bpy.utils.register_class(bl_class)
        except Exception:
            pass


def unregister():
    for bl_class in reversed(classes):
        try:
            bpy.utils.unregister_class(bl_class)
        except Exception:
            pass

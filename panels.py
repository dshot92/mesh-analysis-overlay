# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from typing import Dict

from .overlay_controller import overlay_controller
from .config_manager import config_manager
from .utils import collect_enabled_by_category, register_classes, unregister_classes


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
            panel.prop(props, "profiling", text="Profiling", toggle=True)
            row = panel.row()
            row.operator("mesh_analysis.restore_preferences", text="Restore Preferences", icon="LOOP_BACK")

    def draw_statistics(self, context, panel):
        """Draw statistics for all selected mesh objects.

        Uses OverlayController.get_feature_counts (engine cache + single BMesh
        on miss) grouped by category. Panel-level _stats_cache avoids recompute
        on every UI redraw.
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

        try:
            metadata = config_manager.get_metadata()
        except Exception:
            return

        for obj in selected_meshes:
            # Collect all active features across categories once.
            # Done before the cache check so the cache key reflects the
            # current toggle set: toggling a feature must recompute even
            # when the object selection did not change.
            active_by_category, all_active = collect_enabled_by_category(props, metadata)

            try:
                threshold = float(getattr(props, "non_planar_threshold", 0.0))
            except Exception:
                threshold = 0.0
            cache_key = (tuple(sorted(all_active)), threshold)
            cached = self._stats_cache.get(obj.name)
            if cached is not None and cached.get("_key") == cache_key:
                stats = cached
            else:
                # Get cached stats or calculate new ones
                stats: Dict = {"features": {}, "_key": cache_key}

                if all_active:
                    counts = overlay_controller.get_feature_counts(obj, all_active)
                    for category, features in active_by_category.items():
                        cat_stats = {}
                        for feature in features:
                            try:
                                cat_stats[feature["label"]] = int(counts.get(feature["id"], 0))
                            except Exception:
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
    register_classes(classes)


def unregister():
    unregister_classes(classes)

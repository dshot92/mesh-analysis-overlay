# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .operators import drawer
from .mesh_analyzer import MeshAnalyzer
from .feature_data import FEATURE_DATA


class Mesh_Analysis_Overlay_Panel(bpy.types.Panel):
    bl_label = "Mesh Analysis Overlay"
    bl_idname = "VIEW3D_PT_mesh_analysis_overlay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mesh Analysis Overlay"

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
            depress=drawer.is_running,
        )

        # Info text
        ROW_SCALE = 0.5
        ALIGNMENT = "LEFT"
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="Overlay data is cached.", icon="INFO")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="Refresh by:")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="• Toggling Overlay off/on")
        row = layout.row()
        row.scale_y = ROW_SCALE
        row.alignment = ALIGNMENT
        row.label(text="• Toggling Edit Mode off/on")

        # Draw feature panels
        for category, features in FEATURE_DATA.items():
            header, panel = layout.panel(f"{category}_panel", default_closed=False)
            header.label(text=category.title())
            if panel:
                for feature in features:
                    row = panel.row(align=True)
                    split = row.split(factor=factor)
                    split.prop(props, f"{feature['id']}_enabled", text=feature["label"])
                    split.prop(props, f"{feature['id']}_color", text="")
                    split.operator(
                        "view3d.select_feature_elements",
                        text="",
                        icon="RESTRICT_SELECT_OFF",
                    ).feature = feature["id"]

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

    def draw_statistics(self, context, panel):
        """Draw statistics using cached values when possible"""
        if not (
            drawer.is_running
            and context.active_object
            and context.active_object.type == "MESH"
        ):
            panel.label(text="Enable overlay to see statistics")
            return

        obj = context.active_object
        props = context.scene.Mesh_Analysis_Overlay_Properties

        # Get cached stats or calculate new ones
        if obj.name not in self._stats_cache:
            analyzer = MeshAnalyzer.get_analyzer(obj)
            stats = {"mode": context.mode, "features": {}}

            # Use FEATURE_DATA order for consistency
            for category, features in FEATURE_DATA.items():
                active_features = [
                    feature["id"]
                    for feature in features
                    if getattr(props, f"{feature['id']}_enabled", False)
                ]
                if active_features:
                    stats["features"][category.title()] = {
                        feature: len(analyzer.analyze_feature(feature))
                        for feature in active_features
                    }

            self._stats_cache[obj.name] = stats

        # Draw statistics from cache
        stats = self._stats_cache[obj.name]
        box = panel.box()

        # Draw in same order as FEATURE_DATA
        for category in FEATURE_DATA.keys():
            category_title = category.title()
            if (
                category_title in stats["features"]
                and stats["features"][category_title]
            ):
                col = box.column(align=True)
                col.label(text=f"{category_title}:")
                for feature_name, count in stats["features"][category_title].items():
                    row = col.row()
                    row.label(text=feature_name.replace("_", " ").title())
                    row.label(text=str(count))


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

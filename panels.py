# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .overlay_controller import overlay_controller
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
            depress=overlay_controller.is_running,
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
        """Draw statistics for all selected mesh objects"""
        if not overlay_controller.is_running:
            panel.label(text="Enable overlay to see statistics")
            return

        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes:
            panel.label(text="Select a mesh to see statistics")
            return

        props = context.scene.Mesh_Analysis_Overlay_Properties
        analysis_engine = overlay_controller.analysis_engine

        for obj in selected_meshes:
            # Get cached stats or calculate new ones
            if obj.name not in self._stats_cache:
                stats = {"features": {}}

                for category, features in FEATURE_DATA.items():
                    active_features = [
                        feature["id"]
                        for feature in features
                        if getattr(props, f"{feature['id']}_enabled", False)
                    ]
                    if active_features:
                        analysis_results = analysis_engine.analyze_mesh(obj, active_features)
                        stats["features"][category.title()] = {
                            feature["label"]: len(analysis_results[feature["id"]].indices) 
                            if feature["id"] in analysis_results else 0
                            for feature in features if feature["id"] in active_features
                        }
                
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
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

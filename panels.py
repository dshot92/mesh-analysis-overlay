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

    @classmethod
    def draw_statistics(cls, context, layout):
        if not drawer.is_running:
            layout.label(text="Enable overlay to see statistics")
            return

        obj = context.active_object
        if not obj or obj.type != "MESH":
            return

        props = context.scene.Mesh_Analysis_Overlay_Properties

        # Check if any feature is enabled
        any_enabled = False
        for category, features in FEATURE_DATA.items():
            for feature in features:
                if getattr(props, f"{feature['id']}_enabled", False):
                    any_enabled = True
                    break
            if any_enabled:
                break

        if not any_enabled:
            layout.label(text="Select features to see statistics")
            return

        analyzer = MeshAnalyzer(obj)
        stats = analyzer.update_statistics()

        # Draw feature statistics following FEATURE_DATA order
        for category, features in FEATURE_DATA.items():
            has_enabled_features = False
            for feature in features:
                feature_id = feature["id"]
                if (
                    getattr(props, f"{feature_id}_enabled", False)
                    and stats["features"].get(category.title(), {}).get(feature_id, 0)
                    > 0
                ):
                    has_enabled_features = True
                    break

            if has_enabled_features:
                box = layout.box()
                box.label(text=category.title())
                col = box.column()
                for feature in features:
                    feature_id = feature["id"]
                    count = (
                        stats["features"].get(category.title(), {}).get(feature_id, 0)
                    )
                    if getattr(props, f"{feature_id}_enabled", False):
                        row = col.row()
                        row.label(text=f"{feature['label']}:")
                        row.label(text=str(count))

    def draw(self, context):
        layout = self.layout
        props = context.scene.Mesh_Analysis_Overlay_Properties
        factor = 0.85

        # Toggle and update buttons side by side
        row = layout.row(align=True)
        split = row.split(factor=0.75)
        split.operator(
            "view3d.mesh_analysis_overlay",
            text="Show Overlay",
            icon="OVERLAY",
            depress=drawer.is_running,
        )
        split.operator(
            "view3d.update_mesh_analysis_overlay",
            text="",
            icon="FILE_REFRESH",
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


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

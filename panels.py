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

    # @classmethod
    # def draw_statistics(cls, context, layout):
    #     obj = context.active_object
    #     if not obj or obj.type != "MESH":
    #         return

    #     analyzer = MeshAnalyzer(obj)
    #     stats = {
    #         "mesh": {
    #             "Vertices": len(obj.data.vertices),
    #             "Edges": len(obj.data.edges),
    #             "Faces": len(obj.data.polygons),
    #         },
    #         "features": {
    #             "Vertices": {
    #                 feature: len(analyzer.analyze_feature(feature))
    #                 for feature in MeshAnalyzer.vertex_features
    #             },
    #             "Edges": {
    #                 feature: len(analyzer.analyze_feature(feature))
    #                 for feature in MeshAnalyzer.edge_features
    #             },
    #             "Faces": {
    #                 feature: len(analyzer.analyze_feature(feature))
    #                 for feature in MeshAnalyzer.face_features
    #             },
    #         },
    #     }

    # Draw statistics UI...

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

        # # Statistics panel
        # header, panel = layout.panel("statistics_panel", default_closed=False)
        # header.label(text="Statistics")

        # if panel:
        #     self.draw_statistics(context, panel)

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

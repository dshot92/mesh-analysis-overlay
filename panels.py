# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .operators import drawer
from .mesh_analyzer import MeshAnalyzer


class Mesh_Analysis_Overlay_Panel(bpy.types.Panel):
    bl_label = "Mesh Analysis Overlay"
    bl_idname = "VIEW3D_PT_mesh_analysis_overlay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mesh Analysis Overlay"

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

        # Faces panel
        header, panel = layout.panel("faces_panel", default_closed=False)
        header.label(text="Faces")
        if panel:
            # Triangles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "tri_faces_enabled", text="Triangles")
            split.prop(props, "tri_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "tri_faces"

            # Quads row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "quad_faces_enabled", text="Quads")
            split.prop(props, "quad_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "quad_faces"

            # N-gons row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "ngon_faces_enabled", text="N-Gons")
            split.prop(props, "ngon_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "ngon_faces"

            # Non-planar faces row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "non_planar_faces_enabled", text="Non-Planar Faces")
            split.prop(props, "non_planar_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_planar_faces"

            # Degenerate faces row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "degenerate_faces_enabled", text="Degenerate Faces")
            split.prop(props, "degenerate_faces_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "degenerate_faces"

        # Edges panel
        header, panel = layout.panel("edges_panel", default_closed=False)
        header.label(text="Edges")
        if panel:
            # Non-manifold edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "non_manifold_e_edges_enabled", text="Non-Manifold Edges")
            split.prop(props, "non_manifold_e_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_manifold_e_edges"

            # Sharp edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "sharp_edges_enabled", text="Sharp Edges")
            split.prop(props, "sharp_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "sharp_edges"

            # Seam edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "seam_edges_enabled", text="Seam Edges")
            split.prop(props, "seam_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "seam_edges"

            # Boundary edges
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "boundary_edges_enabled", text="Boundary Edges")
            split.prop(props, "boundary_edges_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "boundary_edges"

        # Vertices panel
        header, panel = layout.panel("vertices_panel", default_closed=False)
        header.label(text="Vertices")
        if panel:
            # Singles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "single_vertices_enabled", text="Single Vertices")
            split.prop(props, "single_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "single_vertices"

            # Non-manifold vertices row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(
                props, "non_manifold_v_vertices_enabled", text="Non-Manifold Vertices"
            )
            split.prop(props, "non_manifold_v_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "non_manifold_v_vertices"

            # N-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "n_pole_vertices_enabled", text="N-Poles (3)")
            split.prop(props, "n_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "n_pole_vertices"

            # E-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "e_pole_vertices_enabled", text="E-Poles (5)")
            split.prop(props, "e_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "e_pole_vertices"

            # High-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "high_pole_vertices_enabled", text="High-Poles (6+)")
            split.prop(props, "high_pole_vertices_color", text="")
            split.operator(
                "view3d.select_feature_elements", text="", icon="RESTRICT_SELECT_OFF"
            ).feature = "high_pole_vertices"

        # Statistics panel
        header, panel = layout.panel("statistics_panel", default_closed=False)
        header.label(text="Statistics")

        if panel:
            if (
                drawer.is_running
                and context.active_object
                and context.active_object.type == "MESH"
            ):
                analyzer = MeshAnalyzer.get_analyzer(context.active_object)

                # Check if any overlay is enabled
                active_faces = [
                    f
                    for f in analyzer.face_features
                    if getattr(props, f"{f}_enabled", False)
                ]
                active_edges = [
                    f
                    for f in analyzer.edge_features
                    if getattr(props, f"{f}_enabled", False)
                ]
                active_vertices = [
                    f
                    for f in analyzer.vertex_features
                    if getattr(props, f"{f}_enabled", False)
                ]

                if not any([active_faces, active_edges, active_vertices]):
                    box = panel.box()
                    box.label(text="No overlay enabled")
                else:
                    # Create a single box for all statistics
                    box = panel.box()

                    # Faces stats
                    if active_faces:
                        col = box.column(align=True)
                        col.label(text="Faces:")
                        face_order = [
                            "tri_faces",
                            "quad_faces",
                            "ngon_faces",
                            "non_planar_faces",
                            "degenerate_faces",
                        ]
                        for feature in face_order:
                            if feature in active_faces:
                                count = len(analyzer.analyze_feature(feature))
                                row = col.row()
                                row.label(text=feature.replace("_", " ").title())
                                row.label(text=str(count))

                    # Edges stats
                    if active_edges:
                        col = box.column(align=True)
                        col.label(text="Edges:")
                        edge_order = [
                            "non_manifold_e_edges",
                            "sharp_edges",
                            "seam_edges",
                            "boundary_edges",
                        ]
                        for feature in edge_order:
                            if feature in active_edges:
                                count = len(analyzer.analyze_feature(feature))
                                row = col.row()
                                row.label(text=feature.replace("_", " ").title())
                                row.label(text=str(count))

                    # Vertices stats
                    if active_vertices:
                        col = box.column(align=True)
                        col.label(text="Vertices:")
                        vertex_order = [
                            "single_vertices",
                            "non_manifold_v_vertices",
                            "n_pole_vertices",
                            "e_pole_vertices",
                            "high_pole_vertices",
                        ]
                        for feature in vertex_order:
                            if feature in active_vertices:
                                count = len(analyzer.analyze_feature(feature))
                                row = col.row()
                                row.label(text=feature.replace("_", " ").title())
                                row.label(text=str(count))
            else:
                panel.label(text="Enable overlay to see statistics")

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

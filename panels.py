# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .operators import drawer


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
        ROW_SCALE = 0.35
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
            split.prop(props, "show_tri_faces", text="Triangles")
            split.prop(props, "tri_faces_color", text="")

            # Quads row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_quad_faces", text="Quads")
            split.prop(props, "quad_faces_color", text="")

            # N-gons row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_ngon_faces", text="N-Gons")
            split.prop(props, "ngon_faces_color", text="")

            # Non-planar faces row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_non_planar_faces", text="Non-Planar Faces")
            split.prop(props, "non_planar_faces_color", text="")

        # Edges panel
        header, panel = layout.panel("edges_panel", default_closed=False)
        header.label(text="Edges")
        if panel:
            # Non-manifold edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_non_manifold_e_edges", text="Non-Manifold Edges")
            split.prop(props, "non_manifold_e_edges_color", text="")

            # Sharp edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_sharp_edges", text="Sharp Edges")
            split.prop(props, "sharp_edges_color", text="")

            # Seam edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_seam_edges", text="Seam Edges")
            split.prop(props, "seam_edges_color", text="")

            # Boundary edges row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_boundary_edges", text="Boundary Edges")
            split.prop(props, "boundary_edges_color", text="")

        # Vertices panel
        header, panel = layout.panel("vertices_panel", default_closed=False)
        header.label(text="Vertices")
        if panel:
            # Singles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_single_vertices", text="Single Vertices")
            split.prop(props, "single_vertices_color", text="")

            # Non-manifold vertices row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(
                props, "show_non_manifold_v_vertices", text="Non-Manifold Vertices"
            )
            split.prop(props, "non_manifold_v_vertices_color", text="")

            # N-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_n_pole_vertices", text="N-Poles (3)")
            split.prop(props, "n_pole_vertices_color", text="")

            # E-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_e_pole_vertices", text="E-Poles (5)")
            split.prop(props, "e_pole_vertices_color", text="")

            # High-poles row
            row = panel.row(align=True)
            split = row.split(factor=factor)
            split.prop(props, "show_high_pole_vertices", text="High-Poles (6+)")
            split.prop(props, "high_pole_vertices_color", text="")

        # Offset settings
        header, panel = layout.panel("panel_settings", default_closed=True)
        header.label(text="Overlay Settings")

        if panel:
            panel.prop(props, "overlay_offset", text="Overlay Offset")
            panel.prop(props, "overlay_edge_width", text="Overlay Edge Width")
            panel.prop(props, "overlay_vertex_radius", text="Overlay Vertex Radius")


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

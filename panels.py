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

        layout.label(text="Faces")
        # Triangles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_tri_faces", text="Triangles")
        split.prop(props, "tri_faces_color", text="")

        # Quads row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_quad_faces", text="Quads")
        split.prop(props, "quad_faces_color", text="")

        # N-gons row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_ngon_faces", text="N-Gons")
        split.prop(props, "ngon_faces_color", text="")

        # Non-planar faces row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_non_planar_faces", text="Non-Planar Faces")
        split.prop(props, "non_planar_faces_color", text="")

        layout.label(text="Edges")
        # Non-manifold edges row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_non_manifold_e_edges", text="Non-Manifold Edges")
        split.prop(props, "non_manifold_e_edges_color", text="")

        # Sharp edges row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_sharp_edges", text="Sharp Edges")
        split.prop(props, "sharp_edges_color", text="")

        # Seam edges row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_seam_edges", text="Seam Edges")
        split.prop(props, "seam_edges_color", text="")

        # Boundary edges row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_boundary_edges", text="Boundary Edges")
        split.prop(props, "boundary_edges_color", text="")

        layout.label(text="Vertices")
        # Singles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_single_vertices", text="Single Vertices")
        split.prop(props, "single_vertices_color", text="")

        # Non-manifold vertices row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_non_manifold_v_vertices", text="Non-Manifold Vertices")
        split.prop(props, "non_manifold_v_vertices_color", text="")

        # N-poles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_n_pole_vertices", text="N-Poles (3)")
        split.prop(props, "n_pole_vertices_color", text="")

        # E-poles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_e_pole_vertices", text="E-Poles (5)")
        split.prop(props, "e_pole_vertices_color", text="")

        # High-poles row
        row = layout.row(align=True)
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


class MeshAnalysisOverlayPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    non_planar_threshold: bpy.props.FloatProperty(
        name="Non-Planar Threshold",
        description="Threshold angle for non-planar face detection",
        default=0.0001,
        min=0.0,
        max=1.0,
        precision=5,
    )

    debug_print: bpy.props.BoolProperty(
        name="Debug Print", description="Enable debug print statements", default=False
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "non_planar_threshold")
        layout.prop(self, "debug_print")


classes = (
    Mesh_Analysis_Overlay_Panel,
    MeshAnalysisOverlayPreferences,
)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

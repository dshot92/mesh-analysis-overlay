# SPDX-License-Identifier: GPL-3.0-or-later

# ----------------------------------------------------------
# Author: Daniele Stochino (dshot92)
# ----------------------------------------------------------

import bpy
from . import operators  # Keep this import


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
            depress=operators.drawer.is_running,
        )

        layout.label(text="Faces")
        # Triangles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_tris", text="Triangles")
        split.prop(props, "tris_color", text="")

        # Quads row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_quads", text="Quads")
        split.prop(props, "quads_color", text="")

        # N-gons row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_ngons", text="N-Gons")
        split.prop(props, "ngons_color", text="")

        layout.label(text="Edges")
        # Replace the single non-manifold row with two separate rows
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_non_manifold_edges", text="Non-Manifold Edges")
        split.prop(props, "non_manifold_edges_color", text="")

        # Add after the non-manifold edges row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_sharp_edges", text="Sharp Edges")
        split.prop(props, "sharp_edges_color", text="")

        layout.label(text="Vertices")
        # Add after poles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_singles", text="Single Vertices")
        split.prop(props, "singles_color", text="")

        # Non-manifold verts row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_non_manifold_verts", text="Non-Manifold Vertices")
        split.prop(props, "non_manifold_verts_color", text="")

        # Add pole type rows after the existing poles section
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_n_poles", text="N-Poles (3)")
        split.prop(props, "n_poles_color", text="")

        # E-poles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_e_poles", text="E-Poles (5)")
        split.prop(props, "e_poles_color", text="")

        # High-poles row
        row = layout.row(align=True)
        split = row.split(factor=factor)
        split.prop(props, "show_high_poles", text="High-Poles (6+)")
        split.prop(props, "high_poles_color", text="")

        # Offset settings
        header, panel = layout.panel("panel_settings", default_closed=True)
        header.label(text="Overlay Settings")

        if panel:
            panel.prop(props, "overlay_face_offset", text="Overlay Face Offset")
            panel.prop(props, "overlay_edge_width", text="Overlay Edge Width")
            panel.prop(props, "overlay_vertex_radius", text="Overlay Vertex Radius")


classes = (Mesh_Analysis_Overlay_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

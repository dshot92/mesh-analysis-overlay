# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from . import gpu_drawer  # Change the import


class GPU_Overlay_Topology_Panel(bpy.types.Panel):
    bl_label = "GPU Overlay Topology"
    bl_idname = "VIEW3D_PT_gpu_overlay_topology"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GPU Overlay Topology"

    def draw(self, context):
        layout = self.layout
        props = context.scene.GPU_Topology_Overlay_Properties

        # Toggle button for overlay
        row = layout.row()
        row.operator(
            "view3d.gpu_overlay_topology",
            text="GPU Overlay",
            icon="OVERLAY",
            depress=gpu_drawer.drawer.is_running,
        )

        # Polygon type toggles with color pickers
        box = layout.box()
        box.label(text="Show Polygons:")

        # Triangles row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_tris", text="Triangles")
        split.prop(props, "tris_color", text="")

        # Quads row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_quads", text="Quads")
        split.prop(props, "quads_color", text="")

        # N-gons row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_ngons", text="N-Gons")
        split.prop(props, "ngons_color", text="")

        # Add after n-gons row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_poles", text="Poles")
        split.prop(props, "poles_color", text="")

        # Add after poles row
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_singles", text="Single Vertices")
        split.prop(props, "singles_color", text="")

        # Replace the single non-manifold row with two separate rows
        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_non_manifold_edges", text="Non-Manifold Edges")
        split.prop(props, "non_manifold_edges_color", text="")

        row = box.row(align=True)
        split = row.split(factor=0.7)
        split.prop(props, "show_non_manifold_verts", text="Non-Manifold Vertices")
        split.prop(props, "non_manifold_verts_color", text="")

        # Add after the non-manifold edges color control
        row = box.row(align=True)

        # Offset settings
        box = layout.box()
        box.label(text="Overlay Settings:")
        box.prop(props, "overlay_face_offset", text="Overlay Face Offset")
        box.prop(props, "overlay_vertex_radius", text="Overlay Vertex Radius")
        box.prop(props, "overlay_edge_width", text="Overlay Edge Width")


classes = (GPU_Overlay_Topology_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

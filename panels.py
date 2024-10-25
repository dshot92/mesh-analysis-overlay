# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from .gpu_drawer import GPUDrawer


class GPU_Overlay_Topology_Panel(bpy.types.Panel):
    bl_label = "GPU Overlay Topology"
    bl_idname = "VIEW3D_PT_gpu_overlay_topology"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GPU Overlay Topology"

    def draw(self, context):
        layout = self.layout

        drawer = GPUDrawer()
        props = context.scene.GPU_Topology_Overlay_Properties

        # Toggle button for overlay
        row = layout.row()
        if drawer.is_running:
            row.operator(
                "view3d.gpu_overlay_topology", text="Hide Overlay", icon="HIDE_ON"
            )
        else:
            row.operator(
                "view3d.gpu_overlay_topology", text="Show Overlay", icon="HIDE_OFF"
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

        # Offset settings
        box = layout.box()
        box.label(text="Offset Settings:")
        box.prop(props, "poly_offset", text="Overlay Face Offset")


classes = (GPU_Overlay_Topology_Panel,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)


def unregister():
    for bl_class in reversed(classes):
        bpy.utils.unregister_class(bl_class)

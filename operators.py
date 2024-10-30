# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .gpu_drawer import drawer


class Mesh_Analysis_Overlay(bpy.types.Operator):
    bl_idname = "view3d.mesh_analysis_overlay"
    bl_label = "Toggle Mesh Analysis Overlay"
    bl_description = (
        "Toggle the display of the Mesh Analysis Overlay in the 3D viewport"
    )

    def execute(self, context):
        print("[DEBUG-OP] Operator executed")
        if drawer.is_running:
            print("[DEBUG-OP] Stopping drawer")
            drawer.stop()
        else:
            print("[DEBUG-OP] Starting drawer")
            drawer.start()

        print("[DEBUG-OP] Forcing viewport redraw")
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
        return {"FINISHED"}


classes = (Mesh_Analysis_Overlay,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if drawer:
        drawer.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

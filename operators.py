# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh

from .gpu_drawer import GPUDrawer
from .mesh_analyzer import MeshAnalyzer


drawer = GPUDrawer()


class Mesh_Analysis_Overlay(bpy.types.Operator):
    bl_idname = "view3d.mesh_analysis_overlay"
    bl_label = "Toggle Mesh Analysis Overlay"
    bl_description = (
        "Toggle the display of the Mesh Analysis Overlay in the 3D viewport"
    )

    def execute(self, context):
        if drawer.is_running:
            drawer.stop()
        else:
            drawer.start()

            obj = context.active_object
            if obj and obj.type == "MESH":
                drawer.handle_object_switch(obj)

        return {"FINISHED"}


class Select_Feature_Elements(bpy.types.Operator):
    bl_idname = "view3d.select_feature_elements"
    bl_label = "Select Feature Elements"
    bl_description = (
        "Select mesh elements of this type. \nShift/Ctrl to extend/subtract selection."
    )
    bl_options = {"REGISTER", "UNDO"}

    feature: bpy.props.StringProperty()
    mode: bpy.props.EnumProperty(
        items=[
            ("SET", "Set", "Set selection"),
            ("ADD", "Add", "Add to selection"),
            ("SUB", "Subtract", "Subtract from selection"),
        ],
        default="SET",
    )

    def invoke(self, context, event):
        if event.shift:
            self.mode = "ADD"
        elif event.ctrl:
            self.mode = "SUB"
        else:
            self.mode = "SET"
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, "No active mesh object")
            return {"CANCELLED"}

        if obj.mode != "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(type="VERT")

        if self.mode == "SET":
            bpy.ops.mesh.select_all(action="DESELECT")

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        analyzer = MeshAnalyzer.get_analyzer(obj)
        indices = analyzer.analyze_feature(self.feature)
        feature_type = analyzer.get_feature_type(self.feature)

        # Select elements based on feature type
        if feature_type == "FACE":
            for idx in indices:
                if idx < len(bm.faces):
                    bm.faces[idx].select = self.mode != "SUB"
        elif feature_type == "EDGE":
            for idx in indices:
                if idx < len(bm.edges):
                    bm.edges[idx].select = self.mode != "SUB"
        elif feature_type == "VERT":
            for idx in indices:
                if idx < len(bm.verts):
                    bm.verts[idx].select = self.mode != "SUB"

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


class Update_Mesh_Analysis_Overlay(bpy.types.Operator):
    bl_idname = "view3d.update_mesh_analysis_overlay"
    bl_label = "Update Mesh Analysis Overlay"
    bl_description = "Refresh the Mesh Analysis Overlay data"

    @classmethod
    def poll(cls, context):
        if not context.active_object:
            cls.poll_message_set("No active object selected")
            return False

        if context.active_object.type != "MESH":
            cls.poll_message_set("Active object must be a mesh")
            return False

        if context.mode != "OBJECT":
            cls.poll_message_set("Must be in Object mode to refresh")
            return False

        return True

    def execute(self, context):
        if drawer.is_running:
            drawer.stop()
            drawer.start()

            obj = context.active_object
            if obj and obj.type == "MESH":
                drawer.handle_object_switch(obj)

            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

        return {"FINISHED"}


classes = (
    Mesh_Analysis_Overlay,
    Select_Feature_Elements,
    Update_Mesh_Analysis_Overlay,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if drawer:
        drawer.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

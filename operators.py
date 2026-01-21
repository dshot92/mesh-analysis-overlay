# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty

from .overlay_controller import overlay_controller
from .config_manager import config_manager
from .utils import get_updated_bmesh_from_depsgraph
from .analysis_engine import FeatureType

class MESH_ANALYSIS_OT_restore_preferences(bpy.types.Operator):
    """Restore current scene properties from user preferences (reloads CONFIG_PREFERENCE.json)"""
    bl_idname = "mesh_analysis.restore_preferences"
    bl_label = "Restore Preferences"
    
    def execute(self, context):
        if not hasattr(context.scene, 'Mesh_Analysis_Overlay_Properties'):
            return {'CANCELLED'}
            
        props = context.scene.Mesh_Analysis_Overlay_Properties
        
        # Reload current user preferences from CONFIG_PREFERENCE.json
        config = config_manager.load_config(use_preferences=True)
        
        # Apply colors to scene props
        colors = config.get("colors", {})
        for feature_id, color in colors.items():
            prop_name = f"{feature_id}_color"
            if hasattr(props, prop_name):
                color_array = getattr(props, prop_name)
                for i in range(4):
                    color_array[i] = color[i]
        
        # Apply settings to scene props
        settings = config.get("overlay_settings", {})
        props.overlay_offset = settings.get("overlay_offset", 0.01)
        props.overlay_vertex_radius = settings.get("overlay_vertex_radius", 5.0)
        props.overlay_edge_width = settings.get("overlay_edge_width", 5.0)
        props.non_planar_threshold = settings.get("non_planar_threshold", 0.0)
        
        self.report({'INFO'}, "Restored from preferences")
        return {'FINISHED'}


class Mesh_Analysis_Overlay(Operator):
    bl_idname = "view3d.mesh_analysis_overlay"
    bl_label = "Toggle Mesh Analysis Overlay"
    bl_description = (
        "Toggle the display of the Mesh Analysis Overlay in the 3D viewport"
    )

    def execute(self, context):
        if overlay_controller.is_running:
            overlay_controller.stop()
        else:
            overlay_controller.start()
            # Initial update for all selected objects
            overlay_controller.update_all_selected()

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
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

        # Ensure we are in Edit Mode for selection
        was_edit = obj.mode == "EDIT"
        if not was_edit:
            bpy.ops.object.mode_set(mode="EDIT")
            # Default to vertex select if we had to switch
            bpy.ops.mesh.select_mode(type="VERT")

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Use the controller's engine to benefit from caching
        analysis_engine = overlay_controller.analysis_engine
        analysis_results = analysis_engine.analyze_mesh(obj, [self.feature], bm)

        if self.feature not in analysis_results:
            # Still update in case user expects a clear on 'SET'
            if self.mode == "SET":
                for item_list in [bm.faces, bm.edges, bm.verts]:
                    for item in item_list:
                        item.select = False
                bmesh.update_edit_mesh(mesh)
            self.report({"INFO"}, f"No {self.feature} elements found")
            return {"FINISHED"}

        result = analysis_results[self.feature]
        indices = result.indices
        feature_type = result.feature_type

        # 1. Handle selection reset for "SET" mode
        if self.mode == "SET":
            for v in bm.verts:
                v.select = False
            for e in bm.edges:
                e.select = False
            for f in bm.faces:
                f.select = False

        # 2. Apply selection change
        select_val = self.mode != "SUB"

        if feature_type == FeatureType.FACE:
            for idx in indices:
                if idx < len(bm.faces):
                    bm.faces[idx].select = select_val
            # Sync edge/vert selection for faces
            bm.select_flush(select_val)
        elif feature_type == FeatureType.EDGE:
            for idx in indices:
                if idx < len(bm.edges):
                    bm.edges[idx].select = select_val
            bm.select_flush(select_val)
        elif feature_type == FeatureType.VERTEX:
            for idx in indices:
                if idx < len(bm.verts):
                    bm.verts[idx].select = select_val
            bm.select_flush(select_val)

        # 3. CRITICAL: Push changes back to the mesh
        bmesh.update_edit_mesh(mesh)

        # Trigger overlay update if in edit mode to reflect potentially changed visibility (though usually selection doesn't change geometry)
        overlay_controller.update_overlay(obj)

        return {"FINISHED"}


classes = (
    MESH_ANALYSIS_OT_restore_preferences,
    Mesh_Analysis_Overlay,
    Select_Feature_Elements,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if overlay_controller.is_running:
        overlay_controller.stop()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

from .mesh_analyzer import MeshAnalyzer
from .operators import drawer
import bpy
from bpy.app.handlers import persistent


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    if not drawer or not drawer.is_running:
        return

    obj = context.active_object
    if obj and obj.type == "MESH":
        # Get the name of the changed property
        for prop_name in dir(self):
            if prop_name.endswith("_enabled"):
                feature = prop_name[:-8]  # Remove "_enabled" suffix
                MeshAnalyzer.update_analysis(obj, [feature])

    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def update_non_planar_threshold(self, context):
    if not drawer or not drawer.is_running:
        return

    obj = context.active_object
    if obj and obj.type == "MESH":
        # Clear non-planar cache and batch
        analyzer = MeshAnalyzer.get_analyzer(obj)
        if hasattr(analyzer, "_cache"):
            analyzer._cache.pop("non_planar", None)
        if "non_planar" in drawer.batches:
            del drawer.batches["non_planar"]

        # Force immediate batch update
        indices = analyzer.analyze_feature("non_planar")
        if indices:
            props = context.scene.Mesh_Analysis_Overlay_Properties
            color = tuple(props.non_planar_color)
            drawer.update_feature_batch("non_planar", indices, color, "TRIS")

    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


@persistent
def handle_mode_changes(scene):
    if not hasattr(handle_mode_changes, "last_mode"):
        handle_mode_changes.last_mode = "OBJECT"

    if not bpy.context.active_object:
        return

    obj = bpy.context.active_object
    if obj.type != "MESH":
        return

    # Only trigger when specifically changing from EDIT to OBJECT mode
    current_mode = obj.mode
    if current_mode == "OBJECT" and handle_mode_changes.last_mode == "EDIT":
        if drawer and drawer.is_running:
            # Only clear cache for the current object
            MeshAnalyzer._clear_cache_for_object(obj.name)
            MeshAnalyzer.update_analysis(obj)

        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    handle_mode_changes.last_mode = current_mode


def register():
    bpy.app.handlers.depsgraph_update_post.append(handle_mode_changes)


def unregister():
    if handle_mode_changes in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(handle_mode_changes)

import bpy

from bpy.app.handlers import persistent
from .overlay_controller import overlay_controller
from .panels import Mesh_Analysis_Overlay_Panel


@persistent
def update_analysis_overlay(scene, depsgraph):
    """Primary depsgraph callback. Optimized for real-time Edit Mode tracking."""
    if not overlay_controller.is_running:
        return

    # 1. Update selection state
    current_names = {
        obj.name for obj in bpy.context.selected_objects if obj.type == "MESH"
    }
    selection_changed = current_names != overlay_controller.displayed_objects

    if selection_changed:
        overlay_controller.update_all_selected()

    # 2. Identify objects needing a geometry/analysis update
    dirty_objects = set()

    # In Edit Mode, we are more aggressive: any depsgraph update while
    # the object is displayed means we should check for changes.
    for name in overlay_controller.displayed_objects:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue

        # In Edit Mode, the modeling buffer is live, so we treat it as potentially dirty
        # whenever Blender notifies us of a change in the viewport.
        if obj.mode == "EDIT":
            dirty_objects.add(obj)
            continue

        # For Object Mode, check for any updates that might affect the mesh
        for update in depsgraph.updates:
            if update.id == obj or update.id == obj.data:
                if update.is_updated_geometry or update.is_updated_transform:
                    dirty_objects.add(obj)
                    break
        
        # Always update objects with modifiers to ensure depsgraph changes are reflected
        if obj not in dirty_objects and obj.modifiers and obj.mode != "EDIT":
            dirty_objects.add(obj)

    # 3. Process all dirty objects
    if dirty_objects:
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        for obj in dirty_objects:
            overlay_controller.handle_geometry_change(obj)

    # 4. Trigger redraws
    if dirty_objects or selection_changed:
        tag_redraw_viewports()


def update_overlay_enabled_toggles(self, context):
    """Callback for feature property toggles."""
    if not overlay_controller.is_running:
        return
    # Just refresh selection/visibility - engine handles caching
    overlay_controller.update_all_selected()
    if context and hasattr(context, "area") and context.area:
        context.area.tag_redraw()


def update_overlay_properties(self, context):
    """Callback for visual property updates (offset, size, etc.)"""
    if not overlay_controller.is_running:
        return
    overlay_controller.handle_property_change()


def tag_redraw_viewports():
    """Trigger redraw for all 3D viewports"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def register():
    if update_analysis_overlay not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)


def unregister():
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)

import bpy
import logging
import bmesh

from bpy.app.handlers import persistent
from .overlay_controller import overlay_controller
from .analysis_engine import MeshAnalysisEngine
from .feature_data import FEATURE_DATA
from .panels import Mesh_Analysis_Overlay_Panel

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Used as a callback for depsgraph updates
@persistent
def update_analysis_overlay(scene, depsgraph):
    if bpy.context.mode == "EDIT_MESH":
        return
    if not overlay_controller.is_running:
        return
    
    # Check if active object changed (selection change)
    active_obj = bpy.context.active_object
    if active_obj and active_obj.type == "MESH":
        if active_obj != overlay_controller.current_object:
            logger.debug(f"Selection change: {active_obj.name}")
            overlay_controller.update_overlay(active_obj)
            return
    logger.debug("\n=== Depsgraph Update Handler ===")
    logger.debug(f"Total updates: {len(depsgraph.updates)}")

    # Get evaluated depsgraph objects
    for update in depsgraph.updates:
        # Check if update is for a mesh object
        if isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
            obj = update.id
            logger.debug(f"Object updated: {obj.name} ({obj.type})")
            logger.debug(f"Geometry updated: {update.is_updated_geometry}")
            logger.debug(f"Transform updated: {update.is_updated_transform}")

            # Handle both geometry and transform updates
            if obj.type == "MESH" and update.is_updated_geometry:
                # Clear statistics cache when geometry changes
                Mesh_Analysis_Overlay_Panel.clear_stats_cache()
                logger.debug(f"*** GEOMETRY CHANGE DETECTED ***")
                logger.debug(f"Updating overlay for geometry change")
                overlay_controller.handle_geometry_change(obj)


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    if not overlay_controller.is_running:
        return
    logger.debug("\n=== Toggle Enabled Update Handler ===")

    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            # Clear statistics cache when features are toggled
            Mesh_Analysis_Overlay_Panel.clear_stats_cache()
            overlay_controller.handle_property_change()
    
    if context and context.area:
        context.area.tag_redraw()


# Used as a callback for offset property updates in properties.py
def update_overlay_offset(self, context):
    """Callback for when offset property changes"""
    if not overlay_controller.is_running:
        return
    logger.debug("\n=== Offset Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            overlay_controller.handle_property_change()
    
    if context and context.area:
        context.area.tag_redraw()


def update_non_planar_threshold(self, context):
    """Specific handler for non-planar threshold updates"""
    if not overlay_controller.is_running:
        return

    logger.debug("\n=== Non-Planar Threshold Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            overlay_controller.analysis_engine.invalidate_cache(obj.name, ["non_planar_faces"])
            overlay_controller.handle_property_change("non_planar_faces")
    
    if context and context.area:
        context.area.tag_redraw()


@bpy.app.handlers.depsgraph_update_post.append
def update_mesh_analysis_stats(scene, depsgraph):
    # Only process if there are updates to objects
    if not depsgraph.updates:
        return

    # Check for relevant mesh updates
    for update in depsgraph.updates:
        if (
            isinstance(update.id, bpy.types.Object)
            and update.id.type == "MESH"
            and update.id.name in Mesh_Analysis_Overlay_Panel._stats_cache
        ):
            # Clear cache for this object to force recalculation
            del Mesh_Analysis_Overlay_Panel._stats_cache[update.id.name]


@persistent
def handle_edit_mode_changes(scene, depsgraph):
    """Handler for when the edit mode changes
    Avoids index error when trying to select deleted element before a refresh
    """
    if bpy.context.mode != "EDIT_MESH":
        return

    for update in depsgraph.updates:
        if not isinstance(update.id, bpy.types.Object) or update.id.type != "MESH":
            continue

        obj = update.id
        if not obj or not update.is_updated_geometry:
            continue

        bm = bmesh.from_edit_mesh(obj.data)
        stats = overlay_controller.get_mesh_stats(obj)

        # Check if elements were deleted
        if (
            len(bm.verts) < stats["verts"]
            or len(bm.edges) < stats["edges"]
            or len(bm.faces) < stats["faces"]
        ):
            Mesh_Analysis_Overlay_Panel.clear_stats_cache()
            overlay_controller.analysis_engine.invalidate_cache(obj.name)
            if overlay_controller.is_running:
                overlay_controller.handle_geometry_change(obj)


def register():
    logger.debug("\n=== Registering Handlers ===")
    bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)
    if update_mesh_analysis_stats not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_mesh_analysis_stats)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)
    if update_mesh_analysis_stats in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_mesh_analysis_stats)

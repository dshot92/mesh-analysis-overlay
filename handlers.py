import bpy
import logging

from bpy.app.handlers import persistent
from .mesh_analyzer import MeshAnalyzer
from .operators import drawer
from .panels import Mesh_Analysis_Overlay_Panel

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Used as a callback for depsgraph updates
@persistent
def mesh_analysis_depsgraph_update(scene, depsgraph):
    if bpy.context.mode == "EDIT_MESH":
        return
    if not drawer or not drawer.is_running:
        return
    logger.debug("\n=== Depsgraph Update Handler ===")

    # Get evaluated depsgraph objects
    for update in depsgraph.updates:
        # Check if update is for a mesh object
        if isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
            obj = update.id
            logger.debug(f"Object updated: {obj.name} ({obj.type})")
            logger.debug(f"Geometry updated: {update.is_updated_geometry}")

            if obj.type == "MESH" and update.is_updated_geometry:
                # Clear statistics cache when geometry changes
                Mesh_Analysis_Overlay_Panel.clear_stats_cache()
                logger.debug(f"Updating drawer batches for features")
                drawer.update_batches(obj)


# Used as a callback for property updates in properties.py
def toggle_enabled_update(self, context):
    if not drawer or not drawer.is_running:
        return
    logger.debug("\n=== Toggle Enabled Update Handler ===")
    # if context and context.active_object:
    # logger.debug(f"Active object: {context.active_object.name}")

    if context and context.active_object:
        obj = context.active_object
    if obj and obj.type == "MESH":
        # Clear statistics cache when features are toggled
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        drawer.update_batches(obj)
    # if context and context.area:
    #     context.area.tag_redraw()


# Used as a callback for offset property updates in properties.py
def offset_update(self, context):
    """Callback for when offset property changes"""
    if not drawer or not drawer.is_running:
        return
    logger.debug("\n=== Offset Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            drawer.update_batches(obj)
    # if context and context.area:
    #     context.area.tag_redraw()


def non_planar_threshold_update(self, context):
    """Specific handler for non-planar threshold updates"""
    if not drawer or not drawer.is_running:
        return

    logger.debug("\n=== Non-Planar Threshold Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            MeshAnalyzer.invalidate_cache(obj.name, ["non_planar_faces"])
            drawer.update_batches(obj, ["non_planar_faces"])
    # if context and context.area:
    #     context.area.tag_redraw()


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


def register():
    logger.debug("\n=== Registering Handlers ===")
    bpy.app.handlers.depsgraph_update_post.append(mesh_analysis_depsgraph_update)
    if update_mesh_analysis_stats not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_mesh_analysis_stats)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if mesh_analysis_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(mesh_analysis_depsgraph_update)
    if update_mesh_analysis_stats in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_mesh_analysis_stats)

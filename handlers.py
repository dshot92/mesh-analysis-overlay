import bpy
import logging
import bmesh

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
def update_analysis_overlay(scene, depsgraph):
    if bpy.context.mode == "EDIT_MESH":
        return
    if not drawer or not drawer.is_running:
        return

    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
            obj = update.id
            if update.is_updated_geometry:
                # Clear caches when geometry changes
                MeshAnalyzer._analysis_cache.clear()
                MeshAnalyzer._batch_cache.clear()
                MeshAnalyzer.update_analysis(obj)


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    if not drawer or not drawer.is_running:
        return

    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            # Don't clear cache, just update the analysis
            MeshAnalyzer.update_analysis(obj)


# Used as a callback for offset property updates in properties.py
def update_overlay_offset(self, context):
    """Callback for when offset property changes"""
    if not drawer or not drawer.is_running:
        return
    logger.debug("\n=== Offset Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            MeshAnalyzer.update_analysis(obj)
    # if context and context.area:
    #     context.area.tag_redraw()


def update_non_planar_threshold(self, context):
    """Specific handler for non-planar threshold updates"""
    if not drawer or not drawer.is_running:
        return

    logger.debug("\n=== Non-Planar Threshold Update Handler ===")
    if context and context.active_object:
        obj = context.active_object
        if obj and obj.type == "MESH":
            MeshAnalyzer.update_analysis(obj, ["non_planar_faces"])
    # if context and context.area:
    #     context.area.tag_redraw()


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

        if drawer and drawer.is_running:
            MeshAnalyzer.update_analysis(obj)


def register():
    logger.debug("\n=== Registering Handlers ===")
    bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)

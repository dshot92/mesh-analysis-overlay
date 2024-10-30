import bpy
import logging

from bpy.app.handlers import persistent
from .mesh_analyzer import MeshAnalyzer
from .gpu_drawer import drawer

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
    logger.debug("\n=== Depsgraph Update Handler ===")
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object):
            obj = update.id
            logger.debug(f"Object updated: {obj.name} ({obj.type})")
            logger.debug(f"Geometry updated: {update.is_updated_geometry}")

            if obj.type == "MESH" and update.is_updated_geometry:
                logger.debug(f"Invalidating cache for: {obj.name}")
                MeshAnalyzer.invalidate_cache(obj.name)
                if drawer and drawer.is_running:
                    logger.debug("Updating drawer batches")
                    drawer.update_batches(obj)


# Used as a callback for property updates in properties.py
def property_update(self, context):
    logger.debug("\n=== Property Update Handler ===")
    if context and context.active_object:
        logger.debug(f"Active object: {context.active_object.name}")

    if drawer and drawer.is_running:
        obj = context.active_object
        if obj and obj.type == "MESH":
            # pass
            drawer.batches.clear()
            logger.debug("Updating drawer batches")
            drawer.update_batches(obj)


# Used as a callback for offset property updates in properties.py
def offset_update(self, context):
    """Callback for when offset property changes"""
    if context and context.area:
        context.area.tag_redraw()
    if drawer and drawer.is_running:
        obj = context.active_object
        if obj and obj.type == "MESH":
            drawer.update_batches(obj)


def register():
    logger.debug("\n=== Registering Handlers ===")
    bpy.app.handlers.depsgraph_update_post.append(mesh_analysis_depsgraph_update)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if mesh_analysis_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(mesh_analysis_depsgraph_update)

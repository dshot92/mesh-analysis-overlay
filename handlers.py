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


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    pass
    # if not drawer or not drawer.is_running:
    #     return

    # if context and context.active_object:
    #     obj = context.active_object
    #     if obj and obj.type == "MESH":
    #         # Don't clear cache, just update the analysis
    #         context.area.tag_redraw()
    #         # MeshAnalyzer.update_analysis(obj)


def update_non_planar_threshold(self, context):
    pass
    # """Specific handler for non-planar threshold updates"""
    # if not drawer or not drawer.is_running:
    #     return

    # if context and context.active_object:
    #     obj = context.active_object
    #     if obj and obj.type == "MESH":
    #         # Clear only analysis cache for non-planar faces
    #         if "non_planar_faces" in MeshAnalyzer._analysis_cache:
    #             del MeshAnalyzer._analysis_cache["non_planar_faces"]
    #         MeshAnalyzer.update_analysis(obj, ["non_planar_faces"])


# @persistent
# def update_analysis_overlay(scene, depsgraph):
#     # Check for object selection changes
#     for update in depsgraph.updates:
#         if isinstance(update.id, bpy.types.Object):
#             obj = update.id
#             if obj == bpy.context.active_object and obj.type == "MESH":
#                 # If drawer isn't running, start it
#                 if not drawer.is_running:
#                     drawer.start()

#                 # Clear existing batches and update for new object
#                 drawer.batches.clear()
#                 MeshAnalyzer.update_analysis(obj)
#                 break

#     # If no mesh object is selected and drawer is running, stop it
#     if not bpy.context.active_object or bpy.context.active_object.type != "MESH":
#         if drawer.is_running:
#             drawer.stop()


def register():
    logger.debug("\n=== Registering Handlers ===")
    # bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    # if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
    #     bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)

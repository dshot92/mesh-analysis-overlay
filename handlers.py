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
    if not overlay_controller.is_running:
        return
    
    # 1. Handle selection changes
    current_selected = {obj.name for obj in bpy.context.selected_objects if obj.type == "MESH"}
    if current_selected != overlay_controller.displayed_objects:
        logger.debug(f"Selection change detected")
        overlay_controller.update_all_selected()
        return

    # 2. Handle geometry and topology updates
    needs_update = False
    
    # Check if any updated ID is a mesh we are currently displaying
    for update in depsgraph.updates:
        # Check Mesh datablocks (Topological edits)
        if isinstance(update.id, bpy.types.Mesh):
            # Find if any displayed object uses this mesh
            for obj_name in overlay_controller.displayed_objects:
                obj = bpy.data.objects.get(obj_name)
                if obj and obj.data == update.id:
                    if obj.mode == 'EDIT':
                        obj.update_from_editmode()
                    needs_update = True
                    break
        
        # Check Object ID (Transformations/General updates)
        elif isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
            if update.id.name in overlay_controller.displayed_objects:
                if update.id.mode == 'EDIT':
                    update.id.update_from_editmode()
                needs_update = True
                break

    if needs_update:
        logger.debug("*** AUTOMATIC GEOMETRY REFRESH ***")
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        overlay_controller.update_all_selected()
        
        # Force redraw of all 3D viewports
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()


# Used as a callback for feature toggles
def update_overlay_enabled_toggles(self, context):
    if not overlay_controller.is_running:
        return
    logger.debug("\n=== Toggle Enabled Update Handler ===")

    Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    overlay_controller.update_all_selected()
    
    if context and context.area:
        context.area.tag_redraw()


# Used as a callback for visual property updates
def update_overlay_offset(self, context):
    if not overlay_controller.is_running:
        return
        
    logger.debug("\n=== Visual Property Update Handler ===")
    overlay_controller.handle_property_change()
    
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def update_non_planar_threshold(self, context):
    if not overlay_controller.is_running:
        return

    logger.debug("\n=== Non-Planar Threshold Update Handler ===")
    Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    
    for obj_name in list(overlay_controller.displayed_objects):
        overlay_controller.analysis_engine.invalidate_cache(obj_name, ["non_planar_faces"])
    
    overlay_controller.update_all_selected()
    
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def register():
    logger.debug("\n=== Registering Handlers ===")
    if update_analysis_overlay not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)

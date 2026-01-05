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
    
    # Selection change detection (any mesh selection change)
    current_selected = {obj.name for obj in bpy.context.selected_objects if obj.type == "MESH"}
    if current_selected != overlay_controller.displayed_objects:
        logger.debug(f"Selection change detected")
        overlay_controller.update_all_selected()
        return

    # Handle geometry updates for all selected meshes
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object) and update.id.type == "MESH":
            obj = update.id
            if obj.name in overlay_controller.displayed_objects and update.is_updated_geometry:
                # Clear statistics cache when geometry changes
                Mesh_Analysis_Overlay_Panel.clear_stats_cache()
                
                # In Edit Mode, we need to ensure the mesh data is up to date for analysis
                if obj.mode == 'EDIT':
                    obj.update_from_editmesh()
                
                logger.debug(f"*** GEOMETRY CHANGE DETECTED: {obj.name} ***")
                overlay_controller.handle_geometry_change(obj)
                
                # Signal redraw
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()


# Used as a callback for property updates in properties.py
def update_overlay_enabled_toggles(self, context):
    if not overlay_controller.is_running:
        return
    logger.debug("\n=== Toggle Enabled Update Handler ===")

    # Clear statistics cache when features are toggled
    Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    
    # Update overlays for all selected meshes
    overlay_controller.update_all_selected()
    
    if context and context.area:
        context.area.tag_redraw()


# Used as a callback for offset/visual property updates (offset, width, radius)
def update_overlay_offset(self, context):
    """Callback for when visual properties (offset, edge width, vertex radius) change"""
    if not overlay_controller.is_running:
        return
        
    logger.debug("\n=== Visual Property Update Handler ===")
    overlay_controller.handle_property_change()
    
    # Redraw all 3D viewports
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def update_non_planar_threshold(self, context):
    """Specific handler for non-planar threshold updates"""
    if not overlay_controller.is_running:
        return

    logger.debug("\n=== Non-Planar Threshold Update Handler ===")
    
    # Clear statistics cache
    Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    
    # Invalidate non-planar cache for all currently tracked objects
    for obj_name in list(overlay_controller.displayed_objects):
        overlay_controller.analysis_engine.invalidate_cache(obj_name, ["non_planar_faces"])
    
    # Trigger full update for all selected meshes
    overlay_controller.update_all_selected()
    
    # Redraw all 3D viewports
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


@persistent
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
    if update_analysis_overlay not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)
    if update_mesh_analysis_stats not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_mesh_analysis_stats)


def unregister():
    logger.debug("\n=== Unregistering Handlers ===")
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)
    if update_mesh_analysis_stats in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_mesh_analysis_stats)

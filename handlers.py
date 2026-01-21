import bpy
import numpy as np

from bpy.app.handlers import persistent
from .overlay_controller import overlay_controller
from .panels import Mesh_Analysis_Overlay_Panel
from .config_manager import config_manager
from .render_pipeline import PrimitiveType
from .utils import get_updated_bmesh_from_depsgraph


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

    # 2. For REAL-TIME edit mode, always update if any edit mode object is displayed
    edit_mode_objects = []
    for name in overlay_controller.displayed_objects:
        obj = bpy.data.objects.get(name)
        if obj and obj.mode == "EDIT":
            edit_mode_objects.append(obj)
    
    # CRITICAL: In edit mode, ALWAYS update regardless of depsgraph changes
    # This ensures real-time tracking as the user edits, including undo operations
    if edit_mode_objects:
        dirty_objects = edit_mode_objects
    else:
        # For object mode, use the original logic
        dirty_objects = set()
        for name in overlay_controller.displayed_objects:
            obj = bpy.data.objects.get(name)
            if not obj:
                continue

            # For objects with modifiers, always update to ensure we get the most current state
            has_modifiers = len(obj.modifiers) > 0
            if has_modifiers:
                dirty_objects.add(obj)
                continue

            # For Object Mode, check for any updates that might affect the mesh
            for update in depsgraph.updates:
                if update.id == obj or update.id == obj.data:
                    if update.is_updated_geometry or update.is_updated_transform:
                        dirty_objects.add(obj)
                        break

    # 3. Process all dirty objects - HANDLER drives the analysis flow
    if dirty_objects:
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        for obj in dirty_objects:
            # Invalidate cache and trigger analysis
            overlay_controller.analysis_engine.invalidate_cache(obj.name)
            
            # Get enabled features and colors
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            enabled_features = []
            feature_colors = {}
            
            metadata = config_manager.get_metadata()
            for category, features in metadata.items():
                for feature in features:
                    f_id = feature["id"]
                    if getattr(props, f"{f_id}_enabled", False):
                        enabled_features.append(f_id)
                        feature_colors[f_id] = tuple(getattr(props, f"{f_id}_color"))
            
            # Get the most updated mesh from depsgraph here in handlers
            bm = get_updated_bmesh_from_depsgraph(obj, depsgraph)
            
            try:
                # Perform analysis and get GPU data with the pre-created bmesh
                gpu_results = overlay_controller.analysis_engine.analyze_and_format_mesh_with_bmesh(
                    obj, enabled_features, feature_colors, bm
                )
                
                # Update render pipeline with results
                for f_id in enabled_features:
                    if f_id in gpu_results:
                        gpu_data = gpu_results[f_id]
                        overlay_controller.render_pipeline.update_feature_data(
                            obj.name, f_id, gpu_data.vertices, gpu_data.normals, gpu_data.colors, gpu_data.primitive_type
                        )
                    else:
                        # Clear feature data if not found
                        overlay_controller.render_pipeline.update_feature_data(
                            obj.name,
                            f_id,
                            np.array([]),
                            np.array([]),
                            np.array([]),
                            PrimitiveType.POINTS,
                        )
            finally:
                # Clean up bmesh - edit mode bmesh is managed by Blender
                # but if we created a copy (for modifiers), we need to free it
                if obj.mode == "EDIT" and len(obj.modifiers) > 0:
                    # For edit mode with modifiers, we created a copy, so free it
                    bm.free()
                elif obj.mode != "EDIT":
                    # For object mode, we created the bmesh, so free it
                    bm.free()
                # For edit mode without modifiers, Blender manages the bmesh, don't free

    # 4. Trigger redraws - more aggressive for edit mode
    if dirty_objects or selection_changed:
        # Force immediate viewport redraw for edit mode objects
        if edit_mode_objects:
            # Tag all 3D viewports for immediate redraw - most aggressive approach
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        else:
            # Standard redraw for object mode
            tag_redraw_viewports()
    elif edit_mode_objects:
        # Even if no dirty objects detected, still redraw viewports if in edit mode
        # This ensures the overlay stays visible during editing and captures undo operations
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()


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
    
    # Check if this is the non_planar_threshold property - it affects analysis
    # Try multiple ways to detect the property change
    property_name = None
    if hasattr(context, 'property'):
        property_name = context.property
        # Handle tuple format: (scene, 'property_path', -1)
        if isinstance(property_name, tuple) and len(property_name) >= 2:
            property_name = property_name[1]
            # Extract just the property name from the full path
            if '.' in property_name:
                property_name = property_name.split('.')[-1]
    elif hasattr(context, 'property_name'):
        property_name = context.property_name
    
    # Check if this is a color property change - more robust detection
    is_color_property = (
        property_name and 
        (
            property_name.endswith('_color') or 
            'color' in property_name.lower()
        )
    )
    
    # Always invalidate non_planar_faces cache when threshold might have changed
    # This is a bit aggressive but ensures updates work
    threshold_changed = (
        property_name == 'non_planar_threshold'
    )
    
    if threshold_changed:
        # Invalidate cache for non_planar_faces feature since threshold changed
        for obj_name in overlay_controller.displayed_objects:
            overlay_controller.analysis_engine.invalidate_cache(obj_name, ['non_planar_faces'])
        # Trigger analysis update
        overlay_controller.update_all_selected()
    elif is_color_property:
        # For color changes, use optimized real-time update without reanalysis
        _update_colors_realtime(property_name)
    else:
        # For other visual properties (offset, sizes), we need to rebuild GPU batches
        # Mark all displayed objects as dirty to force batch rebuild
        for obj_name in overlay_controller.displayed_objects:
            overlay_controller.render_pipeline._dirty_objects.add(obj_name)
        # Trigger redraw
        tag_redraw_viewports()


def _update_colors_realtime(changed_property_name: str):
    """Optimized real-time color update without triggering reanalysis"""
    props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
    
    # Extract feature ID from property name (e.g., "tri_faces_color" -> "tri_faces")
    if changed_property_name.endswith('_color'):
        feature_id = changed_property_name[:-6]  # Remove "_color" suffix
    else:
        # Fallback: try to find matching feature by checking all color properties
        feature_id = None
        for obj_name in overlay_controller.displayed_objects:
            if obj_name in overlay_controller.render_pipeline.render_data:
                for existing_feature_id in overlay_controller.render_pipeline.render_data[obj_name].keys():
                    if hasattr(props, f"{existing_feature_id}_color"):
                        feature_id = existing_feature_id
                        break
                if feature_id:
                    break
    
    if not feature_id:
        return
    
    # Get the new color for this feature
    new_color = tuple(getattr(props, f"{feature_id}_color"))
    
    # Update colors for all displayed objects that have this feature using the efficient method
    for obj_name in overlay_controller.displayed_objects:
        overlay_controller.render_pipeline.update_feature_colors_only(obj_name, feature_id, new_color)
    
    # Trigger redraw to show color changes immediately
    tag_redraw_viewports()


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

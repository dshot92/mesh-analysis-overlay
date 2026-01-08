import bpy
import numpy as np

from bpy.app.handlers import persistent
from .overlay_controller import overlay_controller
from .panels import Mesh_Analysis_Overlay_Panel
from .feature_data import FEATURE_DATA


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

        # Determine the analysis mode
        analysis_mode = _get_analysis_mode(obj)

        # In Edit Mode, the modeling buffer is live, so we treat it as potentially dirty
        # whenever Blender notifies us of a change in the viewport.
        if obj.mode == "EDIT":
            dirty_objects.add((obj, analysis_mode))
            continue

        # For Object Mode, check for any updates that might affect the mesh
        for update in depsgraph.updates:
            if update.id == obj or update.id == obj.data:
                if update.is_updated_geometry or update.is_updated_transform:
                    dirty_objects.add((obj, analysis_mode))
                    break
        
        # Only update objects with modifiers if there are actual geometry/transform changes
        # Don't trigger analysis for property-only changes like colors
        if (obj not in dirty_objects and 
            obj.modifiers and 
            obj.mode != "EDIT" and
            any(update.is_updated_geometry or update.is_updated_transform 
                for update in depsgraph.updates 
                if update.id == obj or update.id == obj.data)):
            dirty_objects.add((obj, analysis_mode))

    # 3. Process all dirty objects - HANDLER drives the analysis flow
    if dirty_objects:
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        for obj, analysis_mode in dirty_objects:
            # Invalidate cache and trigger analysis
            overlay_controller.analysis_engine.invalidate_cache(obj.name)
            
            # Get enabled features and colors
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            enabled_features = []
            feature_colors = {}
            
            for category, features in FEATURE_DATA.items():
                for feature in features:
                    f_id = feature["id"]
                    if getattr(props, f"{f_id}_enabled", False):
                        enabled_features.append(f_id)
                        feature_colors[f_id] = tuple(getattr(props, f"{f_id}_color"))
            
            # Perform analysis and get GPU data
            gpu_results = overlay_controller.analysis_engine.analyze_and_format_mesh(obj, enabled_features, feature_colors, analysis_mode)
            
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

    # 4. Trigger redraws
    if dirty_objects or selection_changed:
        tag_redraw_viewports()


def _get_analysis_mode(obj):
    """Determine the analysis mode for the object"""
    if obj.mode == "EDIT":
        # Check for Geometry Nodes in Edit Mode
        has_geometry_nodes = any(mod.type == "NODES" for mod in obj.modifiers)
        return "EDIT_GEOMETRY_NODES" if has_geometry_nodes else "EDIT"
    else:
        return "OBJECT"


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
    elif hasattr(self, 'bl_rna') and hasattr(context, 'rna'):
        # Try to get property from RNA
        try:
            property_name = context.rna.bl_rna.name
        except:
            pass
    
    # Check if this is a color property change
    is_color_property = property_name and 'color' in property_name.lower()
    
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
        # For color changes, we only need to update GPU colors, not re-analyze geometry
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
        
        for obj_name in overlay_controller.displayed_objects:
            # Get current render data for this object
            if obj_name in overlay_controller.render_pipeline.render_data:
                obj_render_data = overlay_controller.render_pipeline.render_data[obj_name]
                
                # Update colors for each feature that has render data
                for feature_id, render_data in obj_render_data.items():
                    # Get the new color for this feature
                    new_color = tuple(getattr(props, f"{feature_id}_color"))
                    
                    # Update only the colors in the render data
                    render_data.colors[:] = np.full_like(render_data.colors, new_color, dtype=np.float32)
                
                # Mark object as dirty to rebuild GPU batches with new colors
                overlay_controller.render_pipeline._dirty_objects.add(obj_name)
        
        # Trigger redraw
        tag_redraw_viewports()
    else:
        # For other visual properties (offset, sizes), we need to rebuild GPU batches
        # Mark all displayed objects as dirty to force batch rebuild
        for obj_name in overlay_controller.displayed_objects:
            overlay_controller.render_pipeline._dirty_objects.add(obj_name)
        # Trigger redraw
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

import bpy

from bpy.app.handlers import persistent
from .overlay_controller import overlay_controller
from .panels import Mesh_Analysis_Overlay_Panel
from .config_manager import config_manager
from .render_pipeline import PrimitiveType
from .utils import (
    managed_bmesh,
    empty_f32,
    collect_enabled_features,
    prof_scope,
)


@persistent
def update_analysis_overlay(scene, depsgraph):
    with prof_scope("depsgraph"):
        return _update_analysis_overlay_inner(scene, depsgraph)

def _update_analysis_overlay_inner(scene, depsgraph):
    """Depsgraph callback.

    - EDIT mode: always re-analyze displayed objects (realtime guarantee,
      including undo/selection ticks). Forces classification via explicit
      invalidation; identical pipeline content still skips GPU rebuilds.
    - OBJECT mode: only on evaluated-geometry updates (transform-only and
      idle ticks do no work). Modifier objects always refresh.
    """
    if not overlay_controller.is_running:
        return

    try:
        current_names = {
            obj.name for obj in bpy.context.selected_objects if obj.type == "MESH"
        }
    except Exception:
        return
    selection_changed = current_names != overlay_controller.displayed_objects

    just_updated = set()
    if selection_changed:
        try:
            overlay_controller.update_all_selected()
            just_updated = set(overlay_controller.displayed_objects)
            Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        except Exception:
            pass

    displayed = []
    for name in list(overlay_controller.displayed_objects):
        try:
            obj = bpy.data.objects.get(name)
        except Exception:
            obj = None
        if obj is not None:
            displayed.append(obj)

    candidates = []
    for obj in displayed:
        if obj.name in just_updated:
            continue
        try:
            is_edit = obj.mode == "EDIT"
        except Exception:
            continue
        if is_edit:
            candidates.append(obj)
            continue
        # OBJECT mode: modifiers always dirty; otherwise geometry-only.
        try:
            has_modifiers = len(obj.modifiers) > 0
        except Exception:
            has_modifiers = False
        if has_modifiers:
            candidates.append(obj)
            continue
        try:
            for update in depsgraph.updates:
                update_orig = getattr(update.id, "original", update.id)
                if update_orig == obj or update_orig == obj.data:
                    if update.is_updated_geometry:
                        candidates.append(obj)
                        break
        except Exception:
            pass

    updated_any = False
    for obj in candidates:
        try:
            props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
            metadata = config_manager.get_metadata()
            enabled_features, feature_colors, _all = collect_enabled_features(props, metadata)
        except Exception:
            continue
        # No enabled features: ensure no stale pipeline data, no analysis cost.
        if not enabled_features:
            try:
                present = overlay_controller.render_pipeline.render_data.get(obj.name, {})
                if present:
                    for f_id in list(present.keys()):
                        overlay_controller.render_pipeline.update_feature_data(
                            obj.name, f_id,
                            empty_f32(),
                            empty_f32(),
                            empty_f32(),
                            PrimitiveType.POINTS,
                        )
                    updated_any = True
            except Exception:
                pass
            continue
        try:
            with managed_bmesh(obj, depsgraph) as bm:
                if bm is None:
                    continue
                # Engine cache is version-aware (topo_sig + pos_hash); no forced
                # invalidate here so idle depsgraph ticks stay no-ops.
                gpu_results = overlay_controller.analysis_engine.analyze_and_format_mesh_with_bmesh(
                    obj, enabled_features, feature_colors, bm
                )
                if overlay_controller.push_gpu_results(obj.name, enabled_features, gpu_results):
                    updated_any = True
        except Exception:
            pass

    if updated_any or selection_changed:
        if updated_any:
            Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        tag_redraw_viewports()


def update_overlay_enabled_toggles(self, context):
    with prof_scope("toggle"):
        return _update_overlay_enabled_toggles_inner(self, context)

def _update_overlay_enabled_toggles_inner(self, context):
    """Callback for feature property toggles."""
    if not overlay_controller.is_running:
        return
    # Just refresh selection/visibility - engine handles caching
    overlay_controller.update_all_selected()
    # Feature set changed: panel stats are keyed per-object and would
    # otherwise stay stale until selection/overlay restart.
    try:
        Mesh_Analysis_Overlay_Panel.clear_stats_cache()
    except Exception:
        pass
    tag_redraw_viewports()
    if context and hasattr(context, "area") and context.area:
        try:
            context.area.tag_redraw()
        except Exception:
            pass


def update_overlay_properties(self, context):
    """Callback for visual property updates (offset, size, etc.)"""
    if not overlay_controller.is_running:
        return

    property_name = None
    if context is not None and hasattr(context, 'property'):
        property_name = context.property
        if isinstance(property_name, tuple) and len(property_name) >= 2:
            property_name = property_name[1]
            if '.' in property_name:
                property_name = property_name.split('.')[-1]
    elif context is not None and hasattr(context, 'property_name'):
        property_name = context.property_name

    is_color_property = (
        property_name and
        (
            property_name.endswith('_color') or
            'color' in property_name.lower()
        )
    )

    threshold_changed = (
        property_name == 'non_planar_threshold'
    )

    if threshold_changed:
        for obj_name in overlay_controller.displayed_objects:
            try:
                overlay_controller.analysis_engine.invalidate_cache(obj_name, ['non_planar_faces'])
            except Exception:
                pass
        overlay_controller.update_all_selected()
        try:
            Mesh_Analysis_Overlay_Panel.clear_stats_cache()
        except Exception:
            pass
        tag_redraw_viewports()
    elif is_color_property:
        _update_colors_realtime(property_name)
    else:
        for obj_name in overlay_controller.displayed_objects:
            try:
                overlay_controller.render_pipeline._dirty_objects.add(obj_name)
            except Exception:
                pass
        tag_redraw_viewports()


def _update_colors_realtime(changed_property_name: str):
    """Optimized real-time color update without triggering reanalysis"""
    try:
        props = bpy.context.scene.Mesh_Analysis_Overlay_Properties
    except Exception:
        return

    if changed_property_name.endswith('_color'):
        feature_id = changed_property_name[:-6]
    else:
        # Unknown property: mark everything dirty instead of guessing a feature.
        try:
            for obj_name in overlay_controller.displayed_objects:
                try:
                    overlay_controller.render_pipeline._dirty_objects.add(obj_name)
                except Exception:
                    pass
        except Exception:
            pass
        tag_redraw_viewports()
        return

    if not feature_id:
        return

    try:
        new_color = tuple(getattr(props, f"{feature_id}_color"))
    except Exception:
        return

    for obj_name in overlay_controller.displayed_objects:
        try:
            overlay_controller.render_pipeline.update_feature_colors_only(obj_name, feature_id, new_color)
        except Exception:
            continue

    tag_redraw_viewports()


def tag_redraw_viewports():
    """Trigger redraw for all 3D viewports"""
    try:
        for window in bpy.context.window_manager.windows:
            try:
                screen = window.screen
            except Exception:
                continue
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    try:
                        area.tag_redraw()
                    except Exception:
                        continue
    except Exception:
        pass


def register():
    if update_analysis_overlay not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(update_analysis_overlay)


def unregister():
    if update_analysis_overlay in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_analysis_overlay)

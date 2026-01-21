# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    FloatProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from . import handlers
from .config_manager import config_manager
from .preferences import get_addon_name

def get_default_color(feature_name):
    """Get default color from preferences or config"""
    try:
        # Try to get from addon preferences first
        addon_name = get_addon_name()
        prefs = bpy.context.preferences.addons[addon_name].preferences
        color_attr = f"{feature_name}_color"
        if hasattr(prefs, color_attr):
            return getattr(prefs, color_attr)
    except:
        pass
    
    # Fallback to config file
    config = config_manager.load_config(use_preferences=True)
    return tuple(config.get("colors", {}).get(feature_name, [1.0, 0.0, 0.0, 0.5]))

def get_default_overlay_setting(setting_name):
    """Get default overlay setting from preferences or config"""
    try:
        # Try to get from addon preferences first
        addon_name = get_addon_name()
        prefs = bpy.context.preferences.addons[addon_name].preferences
        pref_attr = f"default_{setting_name}"
        if hasattr(prefs, pref_attr):
            return getattr(prefs, pref_attr)
    except:
        pass
    
    # Fallback to config file
    config = config_manager.load_config(use_preferences=True)
    return config.get("overlay_settings", {}).get(setting_name, 0.01)


class Mesh_Analysis_Overlay_Props(PropertyGroup):
    # FACE PROPERTIES
    tri_faces_enabled: BoolProperty(
        name="Show Triangles",
        description="Show triangle overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    tri_faces_color: FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    quad_faces_enabled: BoolProperty(
        name="Show Quads",
        description="Show quad overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    quad_faces_color: FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    ngon_faces_enabled: BoolProperty(
        name="Show N-Gons",
        description="Show n-gon overlays",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    ngon_faces_color: FloatVectorProperty(
        name="N-Gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    non_planar_faces_enabled: BoolProperty(
        name="Show Non-Planar Faces",
        description="Show faces that are not planar",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_planar_faces_color: FloatVectorProperty(
        name="Non-Planar Faces Color",
        subtype="COLOR",
        default=(1.0, 0.7, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    degenerate_faces_enabled: BoolProperty(
        name="Show Degenerate Faces",
        description="Show faces with zero area or invalid geometry",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    degenerate_faces_color: FloatVectorProperty(
        name="Degenerate Faces Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    # EDGE PROPERTIES
    non_manifold_e_edges_enabled: BoolProperty(
        name="Show Non-Manifold Edges",
        description="Show non-manifold edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_manifold_e_edges_color: FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    sharp_edges_enabled: BoolProperty(
        name="Show Sharp Edges",
        description="Show sharp edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    sharp_edges_color: FloatVectorProperty(
        name="Sharp Edges Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    seam_edges_enabled: BoolProperty(
        name="Show Seam Edges",
        description="Show UV seam edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    seam_edges_color: FloatVectorProperty(
        name="Seam Edges Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    boundary_edges_enabled: BoolProperty(
        name="Show Boundary Edges",
        description="Display edges that are on mesh boundaries",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    boundary_edges_color: FloatVectorProperty(
        name="Boundary Edges Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    # VERTEX PROPERTIES
    single_vertices_enabled: BoolProperty(
        name="Show Single Vertices",
        description="Show single vertex indicators",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    single_vertices_color: FloatVectorProperty(
        name="Single Vertices Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    non_manifold_v_vertices_enabled: BoolProperty(
        name="Show Non-Manifold Vertices",
        description="Show non-manifold vertices",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    non_manifold_v_vertices_color: FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    n_pole_vertices_enabled: BoolProperty(
        name="Show N-Poles (3)",
        description="Show vertices with 3 edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    n_pole_vertices_color: FloatVectorProperty(
        name="N-Poles (3) Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    e_pole_vertices_enabled: BoolProperty(
        name="Show E-Poles (5)",
        description="Show vertices with 5 edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    e_pole_vertices_color: FloatVectorProperty(
        name="E-Poles (5) Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )
    
    high_pole_vertices_enabled: BoolProperty(
        name="Show High-Poles (6+)",
        description="Show vertices with 6 or more edges",
        default=False,
        update=handlers.update_overlay_enabled_toggles,
    )
    high_pole_vertices_color: FloatVectorProperty(
        name="High-Poles (6+) Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=handlers.update_overlay_properties,
    )

    # SETTINGS VALUES
    overlay_offset: FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.01,
        precision=4,
        update=handlers.update_overlay_properties,
    )
    overlay_vertex_radius: FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=5.0,
        min=1.0,
        max=50.0,
        update=handlers.update_overlay_properties,
    )
    overlay_edge_width: FloatProperty(
        name="Overlay Edge Width",
        description="Width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=10.0,
        update=handlers.update_overlay_properties,
    )

    non_planar_threshold: FloatProperty(
        name="Non-Planar Threshold",
        description="Maximum angle deviation (in degrees) from face plane before considering it non-planar",
        default=0.0,
        min=0.0001,
        max=90.0,
        precision=4,
        update=handlers.update_overlay_properties,
    )


def register():
    bpy.utils.register_class(Mesh_Analysis_Overlay_Props)
    bpy.types.Scene.Mesh_Analysis_Overlay_Properties = PointerProperty(
        type=Mesh_Analysis_Overlay_Props
    )
    
    # Initialize properties with defaults for new blend files
    def load_handler(dummy):
        context = bpy.context
        if hasattr(context.scene, 'Mesh_Analysis_Overlay_Properties'):
            props = context.scene.Mesh_Analysis_Overlay_Properties
            # Only set defaults if properties are at their initial values
            # This prevents overwriting user changes when loading existing files
            if props.tri_faces_color == (1.0, 0.0, 0.0, 0.5):  # Check if at default
                apply_preference_defaults(context)
    
    def apply_preference_defaults(context):
        props = context.scene.Mesh_Analysis_Overlay_Properties
        try:
            addon_name = get_addon_name()
            prefs = context.preferences.addons[addon_name].preferences
            
            # Apply color defaults
            color_mappings = [
                (props.tri_faces_color, prefs.tri_faces_color),
                (props.quad_faces_color, prefs.quad_faces_color),
                (props.ngon_faces_color, prefs.ngon_faces_color),
                (props.non_planar_faces_color, prefs.non_planar_faces_color),
                (props.degenerate_faces_color, prefs.degenerate_faces_color),
                (props.non_manifold_e_edges_color, prefs.non_manifold_edges_color),
                (props.sharp_edges_color, prefs.sharp_edges_color),
                (props.seam_edges_color, prefs.seam_edges_color),
                (props.boundary_edges_color, prefs.boundary_edges_color),
                (props.single_vertices_color, prefs.single_vertices_color),
                (props.non_manifold_v_vertices_color, prefs.non_manifold_vertices_color),
                (props.n_pole_vertices_color, prefs.n_pole_vertices_color),
                (props.e_pole_vertices_color, prefs.e_pole_vertices_color),
                (props.high_pole_vertices_color, prefs.high_pole_vertices_color)
            ]
            
            for prop_array, pref_color in color_mappings:
                for i in range(4):
                    prop_array[i] = pref_color[i]
            
            # Apply overlay setting defaults
            props.overlay_offset = prefs.default_overlay_offset
            props.overlay_vertex_radius = prefs.default_overlay_vertex_radius
            props.overlay_edge_width = prefs.default_overlay_edge_width
            props.non_planar_threshold = prefs.default_non_planar_threshold
            
        except:
            # Fallback to config file if preferences not available
            pass
    
    bpy.app.handlers.load_post.append(load_handler)


def unregister():
    # Remove load handler
    if hasattr(bpy.app, 'handlers') and hasattr(bpy.app.handlers, 'load_post'):
        bpy.app.handlers.load_post.clear()
    
    del bpy.types.Scene.Mesh_Analysis_Overlay_Properties
    bpy.utils.unregister_class(Mesh_Analysis_Overlay_Props)

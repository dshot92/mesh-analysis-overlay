import bpy
import json
import os
from bpy.props import FloatVectorProperty, FloatProperty
from bpy.types import AddonPreferences, Operator
from .config_manager import config_manager

def get_addon_name():
    """Get the correct addon name, handling both regular addons and extensions"""
    # __package__ IS the addon name for Blender extensions
    return __package__

def update_preference_defaults(self, context):
    """Automatically save preferences when they change"""
    # Create config from current preferences
    config = {
        "colors": {},
        "overlay_settings": {
            "overlay_offset": self.default_overlay_offset,
            "overlay_vertex_radius": self.default_overlay_vertex_radius,
            "overlay_edge_width": self.default_overlay_edge_width,
            "non_planar_threshold": self.default_non_planar_threshold
        },
        "metadata": config_manager.get_metadata() # Preserve metadata
    }
    
    # Save colors
    for prop_name in self.__annotations__:
        if prop_name.endswith('_color'):
            feature_name = prop_name.replace('_color', '')
            config["colors"][feature_name] = list(getattr(self, prop_name))
    
    config_manager.save_preferences(config)


class MESH_ANALYSIS_OT_reset_to_defaults(Operator):
    """Reset all properties to factory defaults (reloads CONFIG_DEFAULT.json)"""
    bl_idname = "mesh_analysis.reset_to_defaults"
    bl_label = "Reset to Factory Defaults"
    
    def execute(self, context):
        # 1. Restore factory defaults in the config manager
        config_manager.restore_factory_defaults()
        
        # 2. Reload the addon preferences from the newly restored CONFIG_PREFERENCE.json
        # (which is now a copy of CONFIG_DEFAULT.json)
        config = config_manager.load_config(use_preferences=True)
        
        addon_name = get_addon_name()
        prefs = context.preferences.addons[addon_name].preferences
        
        # Apply colors to preferences
        colors = config.get("colors", {})
        for feature_id, color in colors.items():
            color_prop_name = f"{feature_id}_color"
            if hasattr(prefs, color_prop_name):
                setattr(prefs, color_prop_name, color)
        
        # Apply settings to preferences
        settings = config.get("overlay_settings", {})
        prefs.default_overlay_offset = settings.get("overlay_offset", 0.01)
        prefs.default_overlay_vertex_radius = settings.get("overlay_vertex_radius", 5.0)
        prefs.default_overlay_edge_width = settings.get("overlay_edge_width", 5.0)
        prefs.default_non_planar_threshold = settings.get("non_planar_threshold", 0.0)
        
        # 3. Apply to current scene properties as well
        if hasattr(context.scene, 'Mesh_Analysis_Overlay_Properties'):
            props = context.scene.Mesh_Analysis_Overlay_Properties
            
            # Apply colors to scene props
            for feature_id, color in colors.items():
                # Note: properties.py might use slightly different IDs for color props if they have _color suffix
                # We need to be careful with the mapping. 
                # In properties.py, they are e.g. tri_faces_color
                prop_name = f"{feature_id}_color"
                if hasattr(props, prop_name):
                    color_array = getattr(props, prop_name)
                    for i in range(4):
                        color_array[i] = color[i]
            
            # Apply settings to scene props
            props.overlay_offset = settings.get("overlay_offset", 0.01)
            props.overlay_vertex_radius = settings.get("overlay_vertex_radius", 5.0)
            props.overlay_edge_width = settings.get("overlay_edge_width", 5.0)
            props.non_planar_threshold = settings.get("non_planar_threshold", 0.0)

        self.report({'INFO'}, "Reset to factory defaults")
        return {'FINISHED'}


class MeshAnalysisOverlayPreferences(AddonPreferences):
    bl_idname = __package__
    
    # Color properties for defaults
    tri_faces_color: FloatVectorProperty(
        name="Triangles Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    quad_faces_color: FloatVectorProperty(
        name="Quads Color",
        subtype="COLOR",
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    ngon_faces_color: FloatVectorProperty(
        name="N-Gons Color",
        subtype="COLOR",
        default=(0.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    non_planar_faces_color: FloatVectorProperty(
        name="Non-Planar Faces Color",
        subtype="COLOR",
        default=(1.0, 0.7, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    degenerate_faces_color: FloatVectorProperty(
        name="Degenerate Faces Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    non_manifold_edges_color: FloatVectorProperty(
        name="Non-Manifold Edges Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    sharp_edges_color: FloatVectorProperty(
        name="Sharp Edges Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    seam_edges_color: FloatVectorProperty(
        name="Seam Edges Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    boundary_edges_color: FloatVectorProperty(
        name="Boundary Edges Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    single_vertices_color: FloatVectorProperty(
        name="Single Vertices Color",
        subtype="COLOR",
        default=(1.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    non_manifold_vertices_color: FloatVectorProperty(
        name="Non-Manifold Vertices Color",
        subtype="COLOR",
        default=(1.0, 0.0, 0.5, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    n_pole_vertices_color: FloatVectorProperty(
        name="N-Poles (3) Color",
        subtype="COLOR",
        default=(1.0, 0.5, 0.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    e_pole_vertices_color: FloatVectorProperty(
        name="E-Poles (5) Color",
        subtype="COLOR",
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    high_pole_vertices_color: FloatVectorProperty(
        name="High-Poles (6+) Color",
        subtype="COLOR",
        default=(1.0, 0.0, 1.0, 0.5),
        size=4,
        min=0.0,
        max=1.0,
        update=update_preference_defaults,
    )
    
    # Overlay setting defaults
    default_overlay_offset: FloatProperty(
        name="Default Overlay Offset",
        description="Default distance to offset the overlay faces",
        default=0.01,
        precision=4,
        update=update_preference_defaults,
    )
    default_overlay_vertex_radius: FloatProperty(
        name="Default Vertex Radius",
        description="Default size of the overlay vertex indicators",
        default=5.0,
        min=1.0,
        max=50.0,
        update=update_preference_defaults,
    )
    default_overlay_edge_width: FloatProperty(
        name="Default Edge Width",
        description="Default width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=10.0,
        update=update_preference_defaults,
    )
    default_non_planar_threshold: FloatProperty(
        name="Default Non-Planar Threshold",
        description="Default maximum angle deviation (in degrees) from face plane before considering it non-planar",
        default=0.0,
        min=0.0001,
        max=90.0,
        precision=4,
        update=update_preference_defaults,
    )
    
    def draw(self, context):
        layout = self.layout
        
        # Colors section
        box = layout.box()
        box.label(text="Default Colors", icon="COLOR")
        
        # All colors with labels on same row
        col = box.column(align=True)
        
        # Face colors
        row = col.row()
        row.label(text="Triangles:")
        row.prop(self, "tri_faces_color", text="")
        
        row = col.row()
        row.label(text="Quads:")
        row.prop(self, "quad_faces_color", text="")
        
        row = col.row()
        row.label(text="N-Gons:")
        row.prop(self, "ngon_faces_color", text="")
        
        row = col.row()
        row.label(text="Non-Planar:")
        row.prop(self, "non_planar_faces_color", text="")
        
        row = col.row()
        row.label(text="Degenerate:")
        row.prop(self, "degenerate_faces_color", text="")
        
        # Edge colors
        row = col.row()
        row.label(text="Non-Manifold:")
        row.prop(self, "non_manifold_edges_color", text="")
        
        row = col.row()
        row.label(text="Sharp:")
        row.prop(self, "sharp_edges_color", text="")
        
        row = col.row()
        row.label(text="Seam:")
        row.prop(self, "seam_edges_color", text="")
        
        row = col.row()
        row.label(text="Boundary:")
        row.prop(self, "boundary_edges_color", text="")
        
        # Vertex colors
        row = col.row()
        row.label(text="Single:")
        row.prop(self, "single_vertices_color", text="")
        
        row = col.row()
        row.label(text="Non-Manifold:")
        row.prop(self, "non_manifold_vertices_color", text="")
        
        row = col.row()
        row.label(text="N-Poles:")
        row.prop(self, "n_pole_vertices_color", text="")
        
        row = col.row()
        row.label(text="E-Poles:")
        row.prop(self, "e_pole_vertices_color", text="")
        
        row = col.row()
        row.label(text="High-Poles:")
        row.prop(self, "high_pole_vertices_color", text="")
        
        # Overlay settings section
        box = layout.box()
        box.label(text="Default Overlay Settings", icon="SETTINGS")
        
        col = box.column(align=True)
        col.prop(self, "default_overlay_offset")
        col.prop(self, "default_overlay_vertex_radius")
        col.prop(self, "default_overlay_edge_width")
        col.prop(self, "default_non_planar_threshold")
        
        # Actions
        box = layout.box()
        row = box.row()
        row.operator("mesh_analysis.reset_to_defaults", icon="LOOP_BACK")


def register():
    bpy.utils.register_class(MESH_ANALYSIS_OT_reset_to_defaults)
    bpy.utils.register_class(MeshAnalysisOverlayPreferences)


def unregister():
    bpy.utils.unregister_class(MESH_ANALYSIS_OT_reset_to_defaults)
    bpy.utils.unregister_class(MeshAnalysisOverlayPreferences)

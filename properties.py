# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.props import BoolProperty, FloatVectorProperty, FloatProperty
from bpy.types import PropertyGroup
from . import handlers
from .feature_data import FEATURE_DATA


class Mesh_Analysis_Overlay_Props(PropertyGroup):
    # Dynamically create properties from FEATURE_DATA
    for category, features in FEATURE_DATA.items():
        for feature in features:
            exec(
                f"""
{feature['id']}_enabled: BoolProperty(
    name="Show {feature['label']}",
    description="{feature['description']}",
    default=False,
    update=handlers.update_overlay_enabled_toggles,
)
{feature['id']}_color: FloatVectorProperty(
    name="{feature['label']} Color",
    subtype="COLOR",
    default={feature['default_color']},
    size=4,
    min=0.0,
    max=1.0,
)
"""
            )

    # SETTINGS VALUES
    overlay_offset: FloatProperty(
        name="Overlay Face Offset",
        description="Distance to offset the overlay faces",
        default=0.01,
        precision=4,
        min=0.0,
        # update=handlers.update_overlay_offset,
    )
    overlay_vertex_radius: FloatProperty(
        name="Overlay Vertex Radius",
        description="Size of the overlay vertex indicators",
        default=5.0,
        min=1.0,
        max=50.0,
    )
    overlay_edge_width: FloatProperty(
        name="Overlay Edge Width",
        description="Width of the overlay edge indicators",
        default=5.0,
        min=1.0,
        max=50.0,
    )

    non_planar_threshold: FloatProperty(
        name="Non-Planar Threshold",
        description="Maximum angle deviation (in degrees) from face plane before considering it non-planar",
        default=0.0,
        min=0.0001,
        max=90.0,
        precision=4,
        update=handlers.update_non_planar_threshold,
    )


classes = (Mesh_Analysis_Overlay_Props,)


def register():
    for bl_class in classes:
        bpy.utils.register_class(bl_class)
    bpy.types.Scene.Mesh_Analysis_Overlay_Properties = bpy.props.PointerProperty(
        type=Mesh_Analysis_Overlay_Props
    )


def unregister():
    bpy.utils.unregister_class(Mesh_Analysis_Overlay_Props)
    del bpy.types.Scene.Mesh_Analysis_Overlay_Properties
